"""Streaming helpers for the large annual TSV/GZip payment extracts."""

from __future__ import annotations

import csv
import gzip
import json
import os
import re
import tempfile
import unicodedata
from collections import defaultdict
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, BinaryIO, Final, TextIO

import requests

from .client import (
    API_ORIGIN,
    DATASET_FIELDS,
    PresupuestoAbiertoError,
    ValidationError,
    _build_session,
    _validate_api_url,
    _validate_dataset,
    _validate_timeout,
    _validate_year,
)

_PROFILE_FIELDS: Final = frozenset(
    {
        "nombre_partida",
        "nombre_capitulo",
        "nombre_area",
        "nombre_subtitulo",
        "nombre_item",
        "nombre_asignacion",
        "nombre_bip",
        "nombre_programa_presupuestario",
    }
)
_DOWNLOAD_DATASETS: Final = frozenset(
    {"pagos", "municipios", "gobiernos_regionales"}
)
_DEFAULT_PROFILE_DATA: Final = {
    "name": "biodiversity_conservative",
    "version": 1,
    "fields": sorted(_PROFILE_FIELDS),
    "include_terms": [],
    "include_patterns": [
        {"label": "biodiversidad", "pattern": r"\bbiodivers\w*"},
        {
            "label": "areas_protegidas",
            "pattern": r"\bareas?(?: marinas?)? protegidas?\b",
        },
        {"label": "humedales", "pattern": r"\bhumedales?\b"},
        {"label": "bosque_nativo", "pattern": r"\bbosques? nativos?\b"},
        {
            "label": "restauracion_ecologica",
            "pattern": r"\brestauracion (?:ecologica|ecosistemica|de ecosistemas?)\b",
        },
        {
            "label": "conservacion",
            "pattern": (
                r"\bconservacion (?:de (?:la )?)?"
                r"(?:biodiversidad|ecosistemas?|especies|flora|fauna|marina)\b"
            ),
        },
        {
            "label": "proteccion",
            "pattern": (
                r"\bproteccion (?:de (?:la )?)?"
                r"(?:biodiversidad|naturaleza|flora|fauna|ecosistemas?|especies)\b"
            ),
        },
        {"label": "parques_nacionales", "pattern": r"\bparques? nacionales?\b"},
        {"label": "reservas_nacionales", "pattern": r"\breservas? nacionales?\b"},
        {"label": "monumentos_naturales", "pattern": r"\bmonumentos? naturales?\b"},
        {"label": "snaspe", "pattern": r"\bsnaspe\b"},
        {
            "label": "servicios_ecosistemicos",
            "pattern": r"\bservicios? ecosistemicos?\b",
        },
        {
            "label": "corredores_biologicos",
            "pattern": r"\bcorredores? biologicos?\b",
        },
        {"label": "recursos_geneticos", "pattern": r"\brecursos? geneticos?\b"},
        {"label": "fauna_silvestre", "pattern": r"\bfauna silvestre\b"},
        {"label": "flora_y_fauna", "pattern": r"\bflora y fauna\b"},
        {
            "label": "especies_prioritarias",
            "pattern": (
                r"\bespecies? (?:amenazadas?|nativas?|silvestres?|en peligro)\b"
            ),
        },
    ],
    "exclude_terms": [],
}


class BulkDataError(PresupuestoAbiertoError):
    """A download or local annual data file could not be processed."""


@dataclass(frozen=True)
class _Pattern:
    label: str
    source: str
    compiled: re.Pattern[str] = field(repr=False, compare=False)


@dataclass(frozen=True)
class BiodiversityProfile:
    """Validated lexical profile operating only on budget-classification fields."""

    name: str
    version: int
    fields: tuple[str, ...]
    include_terms: tuple[str, ...]
    include_patterns: tuple[_Pattern, ...]
    exclude_terms: tuple[str, ...]

    def match(self, record: Mapping[str, Any]) -> list[str]:
        text = " | ".join(
            _normalise(str(record.get(field_name, "")))
            for field_name in self.fields
            if record.get(field_name) not in (None, "")
        )
        if not text:
            return []
        if any(_literal_term_matches(text, term) for term in self.exclude_terms):
            return []
        matches = [
            term
            for term in self.include_terms
            if _literal_term_matches(text, term)
        ]
        matches.extend(
            pattern.label
            for pattern in self.include_patterns
            if pattern.compiled.search(text)
        )
        return list(dict.fromkeys(matches))


def _normalise(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_marks = "".join(
        char for char in decomposed if unicodedata.category(char) != "Mn"
    )
    return " ".join(without_marks.split())


def _literal_term_matches(text: str, term: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text) is not None


def _profile_path() -> Path:
    return Path(__file__).resolve().parent / "resources" / "profiles" / "biodiversity_conservative.json"


def _string_list(
    raw: Any,
    *,
    name: str,
    maximum: int,
    normalise: bool = False,
) -> tuple[str, ...]:
    if not isinstance(raw, list) or len(raw) > maximum:
        raise ValidationError(f"profile {name} must be a list with at most {maximum} items")
    result: list[str] = []
    for item in raw:
        if not isinstance(item, str) or not item.strip() or len(item) > 200:
            raise ValidationError(f"profile {name} contains an invalid string")
        item = _normalise(item) if normalise else item.strip()
        if item in result:
            raise ValidationError(f"profile {name} contains a duplicate")
        result.append(item)
    return tuple(result)


def _profile_from_mapping(raw: Mapping[str, Any]) -> BiodiversityProfile:
    expected = {
        "name",
        "version",
        "description",
        "methodology",
        "fields",
        "include_terms",
        "include_patterns",
        "exclude_terms",
    }
    unknown = set(raw) - expected
    if unknown:
        raise ValidationError(f"profile contains unsupported keys: {', '.join(sorted(unknown))}")
    name = raw.get("name")
    version = raw.get("version")
    if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", name):
        raise ValidationError("profile name is invalid")
    if isinstance(version, bool) or not isinstance(version, int) or not 1 <= version <= 100:
        raise ValidationError("profile version must be an integer between 1 and 100")
    fields = _string_list(raw.get("fields"), name="fields", maximum=16)
    if not fields or any(item not in _PROFILE_FIELDS for item in fields):
        raise ValidationError("profile fields must be budget-classification field names")
    include_terms = _string_list(
        raw.get("include_terms", []),
        name="include_terms",
        maximum=200,
        normalise=True,
    )
    exclude_terms = _string_list(
        raw.get("exclude_terms", []),
        name="exclude_terms",
        maximum=200,
        normalise=True,
    )
    patterns_raw = raw.get("include_patterns", [])
    if not isinstance(patterns_raw, list) or len(patterns_raw) > 100:
        raise ValidationError(
            "profile include_patterns must be a list with at most 100 items"
        )
    patterns: list[_Pattern] = []
    labels: set[str] = set()
    for item in patterns_raw:
        if not isinstance(item, Mapping) or set(item) != {"label", "pattern"}:
            raise ValidationError("each profile pattern needs label and pattern")
        label = item.get("label")
        source = item.get("pattern")
        if (
            not isinstance(label, str)
            or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", label)
            or label in labels
            or not isinstance(source, str)
            or not 1 <= len(source) <= 500
        ):
            raise ValidationError("profile contains an invalid pattern")
        try:
            compiled = re.compile(source)
        except re.error as exc:
            raise ValidationError(f"profile pattern {label!r} is invalid") from exc
        labels.add(label)
        patterns.append(_Pattern(label, source, compiled))
    if not include_terms and not patterns:
        raise ValidationError("profile must contain at least one inclusion rule")
    return BiodiversityProfile(
        name=name,
        version=version,
        fields=fields,
        include_terms=include_terms,
        include_patterns=tuple(patterns),
        exclude_terms=exclude_terms,
    )


def load_biodiversity_profile(
    path: str | os.PathLike[str] | None = None,
) -> BiodiversityProfile:
    """Load and strictly validate a lexical classifier JSON file."""

    if path is None:
        default_path = _profile_path()
        if default_path.is_file():
            path = default_path
        else:
            return _profile_from_mapping(_DEFAULT_PROFILE_DATA)
    profile_path = Path(path)
    try:
        with profile_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise BulkDataError("biodiversity profile could not be read") from exc
    if not isinstance(raw, Mapping):
        raise ValidationError("biodiversity profile root must be an object")
    return _profile_from_mapping(raw)


def annual_download_url(year: int, *, dataset: str = "pagos") -> str:
    """Return an allowlisted public annual GZip URL."""

    year = _validate_year(year)
    dataset = _validate_dataset(dataset)
    if dataset not in _DOWNLOAD_DATASETS:
        raise ValidationError("dataset has no allowlisted annual download")
    return _validate_api_url(
        f"{API_ORIGIN}/data/{dataset}-{year}.gz",
        annual_download=True,
    )


def _valid_gzip(path: Path) -> bool:
    try:
        if path.stat().st_size < 2:
            return False
        with path.open("rb") as handle:
            if handle.read(2) != b"\x1f\x8b":
                return False
        with gzip.open(path, "rb") as stream:
            while stream.read(1024 * 1024):
                pass
        return True
    except (OSError, EOFError):
        return False


def download_annual(
    year: int,
    cache_dir: str | os.PathLike[str],
    *,
    dataset: str = "pagos",
    session: requests.Session | Any | None = None,
    timeout: float | tuple[float, float] = (10.0, 120.0),
    retries: int = 2,
    force: bool = False,
    chunk_size: int = 1024 * 1024,
) -> Path:
    """Cache an annual extract using a same-directory atomic rename."""

    url = annual_download_url(year, dataset=dataset)
    timeout = _validate_timeout(timeout)
    if not isinstance(cache_dir, (str, os.PathLike)):
        raise ValidationError("cache_dir must be a filesystem path")
    if (
        isinstance(chunk_size, bool)
        or not isinstance(chunk_size, int)
        or not 16 * 1024 <= chunk_size <= 16 * 1024 * 1024
    ):
        raise ValidationError("chunk_size must be between 16 KiB and 16 MiB")
    target_dir = Path(cache_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{dataset}-{year}.gz"
    if not force and _valid_gzip(target):
        return target
    active_session = session if session is not None else _build_session(retries)
    try:
        response = active_session.get(
            url,
            headers={"Accept": "application/gzip, application/octet-stream"},
            timeout=timeout,
            stream=True,
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        raise BulkDataError("annual download GET failed") from exc
    status = getattr(response, "status_code", None)
    if not isinstance(status, int) or not 200 <= status < 300:
        close = getattr(response, "close", None)
        if callable(close):
            close()
        raise BulkDataError(
            f"annual download returned HTTP {status if status is not None else 'unknown'}"
        )
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{dataset}-{year}-",
            suffix=".part",
            dir=target_dir,
            delete=False,
        ) as handle:
            temporary_name = handle.name
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        temporary = Path(temporary_name)
        if not _valid_gzip(temporary):
            raise BulkDataError("annual download was not a valid GZip stream")
        temporary.replace(target)
        return target
    except OSError as exc:
        raise BulkDataError("annual download could not be cached") from exc
    finally:
        close = getattr(response, "close", None)
        if callable(close):
            close()
        if temporary_name is not None:
            temporary = Path(temporary_name)
            if temporary.exists() and temporary != target:
                try:
                    temporary.unlink()
                except OSError:
                    pass


def _text_reader(path: Path) -> tuple[BinaryIO | None, TextIO]:
    try:
        binary = path.open("rb")
        magic = binary.read(2)
        binary.seek(0)
        if magic == b"\x1f\x8b":
            return binary, gzip.open(
                binary,
                mode="rt",
                encoding="utf-8-sig",
                errors="strict",
                newline="",
            )
        binary.close()
        return None, path.open(
            "r",
            encoding="utf-8-sig",
            errors="strict",
            newline="",
        )
    except OSError as exc:
        raise BulkDataError("annual TSV could not be opened") from exc


def iter_tsv_records(path: str | os.PathLike[str]) -> Iterator[dict[str, str]]:
    """Yield rows without loading an annual TSV or TSV.GZ into memory."""

    source = Path(path)
    binary: BinaryIO | None = None
    text: TextIO | None = None
    try:
        binary, text = _text_reader(source)
        reader = csv.DictReader(text, delimiter="\t")
        if not reader.fieldnames:
            raise BulkDataError("annual TSV has no header")
        if len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise BulkDataError("annual TSV contains duplicate headers")
        if not {"periodo", "devengo"}.issubset(reader.fieldnames):
            raise BulkDataError("TSV requires periodo and devengo columns")
        for row in reader:
            if None in row or any(v is None for v in row.values()):
                raise BulkDataError("annual TSV row has more cells than its header")
            yield {str(key): value for key, value in row.items()}
    except (UnicodeError, csv.Error) as exc:
        raise BulkDataError("annual TSV could not be decoded") from exc
    finally:
        if text is not None:
            text.close()
        if binary is not None and not binary.closed:
            binary.close()


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if "," in text and "." not in text:
        text = text.replace(",", ".")
    try:
        number = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() else None


def _eligible(record: Mapping[str, Any]) -> bool:
    devengo = _decimal(record.get("devengo"))
    debt = _decimal(record.get("deuda_flotante"))
    return devengo is not None and devengo != 0 and debt == 0


def _json_number(value: Decimal) -> int | str:
    integral = value.to_integral_value()
    return int(integral) if value == integral else format(value, "f")


def _example(
    record: Mapping[str, Any],
    *,
    matches: Sequence[str],
    profile: BiodiversityProfile,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name in (
        "periodo",
        "partida",
        "nombre_partida",
        "capitulo",
        "nombre_capitulo",
        "area",
        "nombre_area",
    ):
        if record.get(name) not in (None, ""):
            result[name] = record[name]
    for name in profile.fields:
        if record.get(name) not in (None, "") and name not in result:
            result[name] = record[name]
    amount = _decimal(record.get("devengo"))
    if amount is not None:
        result["devengo"] = _json_number(amount)
    result["matched_rules"] = list(matches)
    return result


def aggregate_biodiversity(
    path: str | os.PathLike[str],
    *,
    profile: BiodiversityProfile | None = None,
    profile_path: str | os.PathLike[str] | None = None,
    mimic_api: bool = True,
    sample_limit: int = 5,
    year: int | None = None,
) -> dict[str, Any]:
    """Classify and aggregate a TSV stream by central-government ``partida``.

    This is a lexical proxy, not an official biodiversity expenditure tag.
    By default it reproduces the portal's display rules: ``devengo != 0`` and
    ``deuda_flotante == 0``.
    """

    if profile is not None and profile_path is not None:
        raise ValidationError("pass profile or profile_path, not both")
    if profile is None:
        profile = load_biodiversity_profile(profile_path)
    if (
        isinstance(sample_limit, bool)
        or not isinstance(sample_limit, int)
        or not 0 <= sample_limit <= 20
    ):
        raise ValidationError("sample_limit must be an integer between 0 and 20")

    if year is not None:
        _validate_year(year)
    dataset_rows = 0
    invalid_amount_rows = 0
    eligible_rows = 0
    matched_rows = 0
    total = Decimal(0)
    examples: list[dict[str, Any]] = []
    by_partida: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {"amount": Decimal(0), "records": 0}
    )
    observed_headers: set[str] = set()
    for record in iter_tsv_records(path):
        dataset_rows += 1
        if year is not None and record.get("periodo") != str(year):
            raise BulkDataError("TSV contains a different year than requested")
        if _decimal(record.get("devengo")) is None:
            invalid_amount_rows += 1
        observed_headers.update(record)
        if mimic_api and not _eligible(record):
            continue
        amount = _decimal(record.get("devengo"))
        if amount is None:
            continue
        eligible_rows += 1
        matches = profile.match(record)
        if not matches:
            continue
        matched_rows += 1
        total += amount
        key = (
            str(record.get("partida", "")),
            str(record.get("nombre_partida", "")),
        )
        by_partida[key]["amount"] += amount
        by_partida[key]["records"] += 1
        if len(examples) < sample_limit:
            examples.append(_example(record, matches=matches, profile=profile))

    available_fields = sorted(set(profile.fields) & observed_headers)
    missing_fields = sorted(set(profile.fields) - observed_headers)
    estimate_available = bool(available_fields) and dataset_rows > 0 and invalid_amount_rows == 0
    warnings: list[str] = [
        "Proxy léxico conservador; no corresponde a una etiqueta oficial de gasto."
    ]
    if not estimate_available:
        warnings.append(
            "El archivo no contiene campos presupuestarios configurados; "
            "la estimación de biodiversidad no está disponible."
        )
    elif missing_fields:
        warnings.append(
            "La cobertura del clasificador es parcial porque faltan campos configurados."
        )
    if invalid_amount_rows:
        warnings.append("Hay devengos inválidos; no se presenta un total como completo.")
    if dataset_rows == 0:
        warnings.append("Archivo sin registros: ausencia de datos, no gasto cero.")
    groups = [
        {
            "partida": key[0],
            "nombre_partida": key[1],
            "devengo": _json_number(values["amount"]),
            "records": values["records"],
        }
        for key, values in sorted(
            by_partida.items(),
            key=lambda item: (-item[1]["amount"], item[0][0], item[0][1]),
        )
    ]
    return {
        "source": str(Path(path)),
        "profile": {"name": profile.name, "version": profile.version},
        "display_rules": {
            "enabled": mimic_api,
            "devengo_nonzero": mimic_api,
            "deuda_flotante_zero": mimic_api,
        },
        "dataset_rows": dataset_rows,
        "eligible_rows": eligible_rows,
        "matched_rows": matched_rows,
        "total_devengo": _json_number(total) if estimate_available else None,
        "invalid_amount_rows": invalid_amount_rows,
        "by_partida": groups,
        "examples": examples,
        "classification_coverage": {
            "estimate_available": estimate_available,
            "available_fields": available_fields,
            "missing_fields": missing_fields,
        },
        "warnings": warnings,
    }
