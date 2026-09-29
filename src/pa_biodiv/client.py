"""Small, read-only client for the public Presupuesto Abierto API.

There is deliberately no generic ``request`` method.  Every network operation
uses GET and resolves to one of the explicitly allowlisted public endpoints.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from typing import Any, Final
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API_ORIGIN: Final = "https://api.presupuestoabierto.gob.cl"
DATASET_PATHS: Final = {
    "pagos": "/api/v1/data/pagos.json",
    "municipios": "/api/v1/data/municipios.json",
    "gobiernos_regionales": "/api/v1/data/gobiernos_regionales.json",
}
ELASTICSEARCH_PATH: Final = "/api/v1/elasticsearch"

PAYMENT_FIELDS: Final = frozenset(
    {
        "periodo",
        "mes",
        "partida",
        "nombre_partida",
        "capitulo",
        "nombre_capitulo",
        "area",
        "nombre_area",
        "subtitulo",
        "nombre_subtitulo",
        "beneficiario",
        "nombre_beneficiario",
        "numero_documento",
        "fecha_documento",
        "tipo_documento",
        "orden_de_compra",
        "fecha_ingreso",
        "fecha_recepcion_conforme",
        "fecha_pago",
        "moneda",
        "monto_original",
        "monto",
        "devengo_original",
        "devengo",
        "honorario",
        "proveedor",
        "sector",
        "region",
        "agregado",
        "persona",
        "intraestado",
        "bloqueo_oc",
        "item",
        "nombre_item",
        "asignacion",
        "nombre_asignacion",
        "codigo_bip",
        "nombre_bip",
        "codigo_ubicacion_geografica",
        "nombre_ubicacion_geografica",
        "codigo_programa_presupuestario",
        "nombre_programa_presupuestario",
        "dias_de_pago",
        "dias_de_pago_cat",
        "deuda_flotante",
    }
)

MUNICIPAL_FIELDS: Final = frozenset(
    {
        "periodo",
        "region",
        "nombre_region",
        "provincia",
        "nombre_provincia",
        "comuna",
        "nombre_comuna",
        "nombre_municipalidad",
        "municipalidad",
        "cod_tipo_doc",
        "tipo_documento",
        "fecha_documento",
        "devengo",
        "devengo_original",
        "beneficiario",
        "nombre_beneficiario",
        "rubro_economico",
        "subrubro_economico",
        "actividad_economica",
        "deuda_flotante",
        "mini_glosa_tramo",
        "glosa_tamano_segun_ventas",
        "glosa_tramo_completa",
    }
)

DATASET_FIELDS: Final = {
    "pagos": PAYMENT_FIELDS,
    "gobiernos_regionales": PAYMENT_FIELDS,
    "municipios": MUNICIPAL_FIELDS,
}
_AGGREGATE_FIELDS: Final = frozenset({"count", "sum"})
_FIELD_RE: Final = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_ALLOWED_API_PATHS: Final = frozenset(
    {
        *DATASET_PATHS.values(),
        "/api/v1/data/pagos",
        "/api/v1/data/municipios",
        "/api/v1/data/gobiernos_regionales",
        ELASTICSEARCH_PATH,
    }
)


class PresupuestoAbiertoError(Exception):
    """Base error with a deliberately compact, non-sensitive message."""


class ValidationError(PresupuestoAbiertoError, ValueError):
    """A caller supplied an unsafe or unsupported argument."""


class ApiError(PresupuestoAbiertoError):
    """The remote API failed or returned an unexpected response."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        endpoint: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.endpoint = endpoint


def _build_session(retries: int = 2) -> requests.Session:
    if isinstance(retries, bool) or not isinstance(retries, int) or not 0 <= retries <= 5:
        raise ValidationError("retries must be an integer between 0 and 5")
    session = requests.Session()
    retry = Retry(
        total=retries,
        connect=retries,
        read=retries,
        status=retries,
        backoff_factor=0.35,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def _validate_timeout(timeout: float | tuple[float, float]) -> tuple[float, float]:
    if isinstance(timeout, (int, float)) and not isinstance(timeout, bool):
        timeout = (float(timeout), float(timeout))
    if (
        not isinstance(timeout, tuple)
        or len(timeout) != 2
        or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not 0 < float(value) <= 300
            for value in timeout
        )
    ):
        raise ValidationError("timeout must contain connect/read seconds in (0, 300]")
    return (float(timeout[0]), float(timeout[1]))


def _validate_api_url(url: str, *, annual_download: bool = False) -> str:
    """Reject redirects/custom hosts and allow only known public GET paths."""

    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "api.presupuestoabierto.gob.cl"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValidationError("URL is outside the Presupuesto Abierto allowlist")
    if annual_download:
        if not re.fullmatch(
            r"/data/(?:pagos|municipios|gobiernos_regionales)-(?:20[1-9][0-9]|2100)\.gz",
            parsed.path,
        ):
            raise ValidationError("annual download URL is not allowlisted")
    elif parsed.path not in _ALLOWED_API_PATHS:
        raise ValidationError("API endpoint is not allowlisted")
    return url


def _validate_dataset(dataset: str) -> str:
    if dataset not in DATASET_PATHS:
        allowed = ", ".join(sorted(DATASET_PATHS))
        raise ValidationError(f"dataset must be one of: {allowed}")
    return dataset


def _validate_year(year: int) -> int:
    if isinstance(year, bool) or not isinstance(year, int) or not 2016 <= year <= 2100:
        raise ValidationError("year must be an integer between 2016 and 2100")
    return year


def _validate_integer(
    value: int,
    name: str,
    *,
    minimum: int,
    maximum: int,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not minimum <= value <= maximum
    ):
        raise ValidationError(
            f"{name} must be an integer between {minimum} and {maximum}"
        )
    return value


def _validate_scalar(value: Any, *, field: str) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        if isinstance(value, str):
            if len(value) > 500:
                raise ValidationError(f"filter value for {field!r} is too long")
            if any(ord(char) < 32 and char not in "\t" for char in value):
                raise ValidationError(f"filter value for {field!r} has control characters")
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise ValidationError(f"filter value for {field!r} must be a JSON scalar")


def _validate_filter(
    value: Mapping[str, Any] | None,
    *,
    dataset: str,
    name: str,
) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValidationError(f"{name} must be a mapping")
    if len(value) > 30:
        raise ValidationError(f"{name} has too many fields")
    allowed_fields = DATASET_FIELDS[dataset]
    result: dict[str, Any] = {}
    for field, raw_value in value.items():
        if not isinstance(field, str) or field not in allowed_fields:
            raise ValidationError(f"unsupported {dataset} field in {name}: {field!r}")
        if isinstance(raw_value, (list, tuple)):
            if not raw_value or len(raw_value) > 100:
                raise ValidationError(
                    f"list filter for {field!r} must contain 1 to 100 values"
                )
            result[field] = [
                _validate_scalar(item, field=field) for item in raw_value
            ]
        else:
            result[field] = _validate_scalar(raw_value, field=field)
    if "periodo" in result:
        _validate_year(result["periodo"])
    code_fields = {"partida", "capitulo", "area", "subtitulo", "item", "asignacion",
                   "codigo_programa_presupuestario", "municipalidad", "comuna", "region"}
    for field in code_fields & result.keys():
        values = result[field] if isinstance(result[field], list) else [result[field]]
        if any(v is not None and not isinstance(v, str) for v in values):
            raise ValidationError(f"budget code {field} must be text; retain leading zeros")
    return result


def _validate_fields(
    value: Sequence[str] | None,
    *,
    dataset: str,
    name: str,
    allow_aggregates: bool = False,
    maximum: int = 45,
) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValidationError(f"{name} must be a sequence of field names")
    if not 1 <= len(value) <= maximum:
        raise ValidationError(f"{name} must contain 1 to {maximum} fields")
    allowed = set(DATASET_FIELDS[dataset])
    if allow_aggregates:
        allowed.update(_AGGREGATE_FIELDS)
    result: list[str] = []
    for field in value:
        if (
            not isinstance(field, str)
            or not _FIELD_RE.fullmatch(field)
            or field not in allowed
        ):
            raise ValidationError(f"unsupported {dataset} field in {name}: {field!r}")
        if field in result:
            raise ValidationError(f"duplicate field in {name}: {field!r}")
        result.append(field)
    return result


def _validate_order_by(
    value: Sequence[str] | None,
    *,
    dataset: str,
) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) != 2:
        raise ValidationError("order_by must be a (field, asc|desc) pair")
    field, direction = value
    allowed = DATASET_FIELDS[dataset] | _AGGREGATE_FIELDS
    if not isinstance(field, str) or field not in allowed:
        raise ValidationError(f"unsupported {dataset} order field: {field!r}")
    if not isinstance(direction, str) or direction.lower() not in {"asc", "desc"}:
        raise ValidationError("order direction must be 'asc' or 'desc'")
    return [field, direction.lower()]


def _json_param(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValidationError("argument cannot be represented as JSON") from exc


def _extract_rows(payload: Any, *, endpoint: str) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, Mapping) and isinstance(payload.get("data"), list):
        rows = payload["data"]
    else:
        raise ApiError("API response did not contain a record list", endpoint=endpoint)
    if not all(isinstance(row, Mapping) for row in rows):
        raise ApiError("API response contained an invalid record", endpoint=endpoint)
    return [dict(row) for row in rows]


class PresupuestoAbiertoClient:
    """Validated read-only access to payment and payee search endpoints."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float | tuple[float, float] = (5.0, 30.0),
        retries: int = 2,
    ) -> None:
        self.timeout = _validate_timeout(timeout)
        self.session = session if session is not None else _build_session(retries)

    def _get_json(self, path: str, params: Mapping[str, Any]) -> Any:
        url = _validate_api_url(f"{API_ORIGIN}{path}")
        try:
            response = self.session.get(
                url,
                params=dict(params),
                headers={"Accept": "application/json"},
                timeout=self.timeout,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            raise ApiError("GET request failed", endpoint=path) from exc
        status = getattr(response, "status_code", None)
        if not isinstance(status, int) or not 200 <= status < 300:
            raise ApiError(
                f"API returned HTTP {status if status is not None else 'unknown'}",
                status_code=status if isinstance(status, int) else None,
                endpoint=path,
            )
        try:
            return response.json()
        except (ValueError, TypeError) as exc:
            raise ApiError("API returned invalid JSON", endpoint=path) from exc

    @staticmethod
    def _filters(
        *,
        dataset: str,
        where: Mapping[str, Any] | None,
        where_not: Mapping[str, Any] | None,
        apply_display_rules: bool,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        include = _validate_filter(where, dataset=dataset, name="where")
        exclude = _validate_filter(where_not, dataset=dataset, name="where_not")
        if apply_display_rules or exclude:
            raise ValidationError("Implicit display rules and where-not are disabled: unverified API contract")
        if "periodo" not in include:
            raise ValidationError("An explicit periodo is required")
        return include, exclude

    @staticmethod
    def _base_params(
        *,
        dataset: str,
        where: Mapping[str, Any] | None,
        where_not: Mapping[str, Any] | None,
        apply_display_rules: bool,
    ) -> dict[str, Any]:
        include, exclude = PresupuestoAbiertoClient._filters(
            dataset=dataset,
            where=where,
            where_not=where_not,
            apply_display_rules=apply_display_rules,
        )
        params: dict[str, Any] = {}
        if include:
            params["where"] = _json_param(include)
        if exclude:
            params["where-not"] = _json_param(exclude)
        return params

    def search_records(
        self,
        *,
        dataset: str = "pagos",
        where: Mapping[str, Any] | None = None,
        where_not: Mapping[str, Any] | None = None,
        select: Sequence[str] | None = None,
        order_by: Sequence[str] | None = None,
        limit: int = 25,
        offset: int = 0,
        apply_display_rules: bool = False,
    ) -> list[dict[str, Any]]:
        """Return a bounded record sample from an allowlisted dataset."""

        dataset = _validate_dataset(dataset)
        limit = _validate_integer(limit, "limit", minimum=1, maximum=1000)
        offset = _validate_integer(offset, "offset", minimum=0, maximum=10_000_000)
        selected = _validate_fields(select, dataset=dataset, name="select")
        order = _validate_order_by(order_by, dataset=dataset)
        params = self._base_params(
            dataset=dataset,
            where=where,
            where_not=where_not,
            apply_display_rules=apply_display_rules,
        )
        params.update({"limit": limit, "offset": offset})
        if selected:
            params["select"] = _json_param(selected)
        if order:
            params["order-by"] = _json_param(order)
        path = DATASET_PATHS[dataset]
        return _extract_rows(self._get_json(path, params), endpoint=path)

    def get_page(
        self,
        *,
        dataset: str = "pagos",
        where: Mapping[str, Any],
        page: int = 1,
        where_not: Mapping[str, Any] | None = None,
        apply_display_rules: bool = False,
    ) -> dict[str, Any]:
        """Use the API's fixed 10,000-row paginator.

        A caller-supplied, non-empty ``where`` filter is required so this method
        cannot accidentally initiate an unbounded national extraction.
        """

        dataset = _validate_dataset(dataset)
        if not isinstance(where, Mapping) or not where:
            raise ValidationError("get_page requires a non-empty where filter")
        page = _validate_integer(page, "page", minimum=1, maximum=1_000_000)
        params = self._base_params(
            dataset=dataset,
            where=where,
            where_not=where_not,
            apply_display_rules=apply_display_rules,
        )
        params["pagination-page"] = page
        path = DATASET_PATHS[dataset]
        payload = self._get_json(path, params)
        if not isinstance(payload, Mapping) or not isinstance(payload.get("data"), list):
            raise ApiError("API response did not contain a paginated result", endpoint=path)
        required = ("page", "perPage", "total", "lastPage")
        if any(
            isinstance(payload.get(key), bool) or not isinstance(payload.get(key), int)
            for key in required
        ):
            raise ApiError("API pagination metadata was invalid", endpoint=path)
        if not all(isinstance(row, Mapping) for row in payload["data"]):
            raise ApiError("API page contained an invalid record", endpoint=path)
        return {
            "page": payload["page"],
            "perPage": payload["perPage"],
            "total": payload["total"],
            "lastPage": payload["lastPage"],
            "data": [dict(row) for row in payload["data"]],
        }

    def summarize(
        self, *, dataset: str = "pagos", group_by: Sequence[str] | None = None,
        where: Mapping[str, Any] | None = None, limit: int = 100,
        offset: int = 0, metric: str | None = None,
    ) -> list[dict[str, Any]]:
        """Observed aggregate contract: where/group-by only; metric is unverified."""
        dataset = _validate_dataset(dataset)
        if metric is not None:
            raise ValidationError("An API sum cannot be labelled devengo/monto without verification; scan raw TSV instead")
        include = _validate_filter(where, dataset=dataset, name="where")
        if "periodo" not in include:
            raise ValidationError("An explicit periodo is required")
        scope = {"partida", "capitulo", "area", "beneficiario", "nombre_beneficiario",
                 "municipalidad", "comuna", "region"}
        if not scope.intersection(include):
            raise ValidationError("Aggregate requires a scoped institution, region or beneficiary filter")
        groups = _validate_fields(group_by, dataset=dataset, name="group_by", maximum=8)
        if not groups:
            raise ValidationError("An explicit group_by is required")
        limit = _validate_integer(limit, "limit", minimum=1, maximum=1000)
        offset = _validate_integer(offset, "offset", minimum=0, maximum=10_000)
        params = {"where": _json_param(include), "group-by": _json_param(groups),
                  "limit": limit, "offset": offset}
        path = DATASET_PATHS[dataset]
        return _extract_rows(self._get_json(path, params), endpoint=path)

    def count_records(
        self,
        *,
        dataset: str = "pagos",
        where: Mapping[str, Any] | None = None,
        where_not: Mapping[str, Any] | None = None,
        apply_display_rules: bool = False,
    ) -> int:
        """Return a filtered record count without transferring the records."""

        dataset = _validate_dataset(dataset)
        params = self._base_params(
            dataset=dataset,
            where=where,
            where_not=where_not,
            apply_display_rules=apply_display_rules,
        )
        params.update({"count": "true", "limit": 1})
        path = DATASET_PATHS[dataset]
        rows = _extract_rows(self._get_json(path, params), endpoint=path)
        if not rows or isinstance(rows[0].get("count"), bool):
            raise ApiError("API count response was missing count", endpoint=path)
        try:
            count = int(rows[0]["count"])
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ApiError("API count response had an invalid count", endpoint=path) from exc
        if count < 0:
            raise ApiError("API count response had an invalid count", endpoint=path)
        return count

    def distinct_values(
        self,
        field: str,
        *,
        dataset: str = "pagos",
        where: Mapping[str, Any] | None = None,
        where_not: Mapping[str, Any] | None = None,
        limit: int = 1000,
        apply_display_rules: bool = False,
    ) -> list[Any]:
        """Return unique values for one allowlisted field."""

        dataset = _validate_dataset(dataset)
        fields = _validate_fields([field], dataset=dataset, name="distinct")
        limit = _validate_integer(limit, "limit", minimum=1, maximum=1000)
        params = self._base_params(
            dataset=dataset,
            where=where,
            where_not=where_not,
            apply_display_rules=apply_display_rules,
        )
        params.update({"distinct": _json_param(fields), "limit": limit})
        path = DATASET_PATHS[dataset]
        rows = _extract_rows(self._get_json(path, params), endpoint=path)
        values: list[Any] = []
        for row in rows:
            if field not in row:
                raise ApiError(
                    "API distinct response omitted the requested field", endpoint=path
                )
            values.append(row[field])
        return values

    def search_payees(
        self,
        query: str,
        *,
        year: int,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search the dedicated read-only Elasticsearch projection for payees."""

        if not isinstance(query, str):
            raise ValidationError("query must be a string")
        query = query.strip()
        if not 1 <= len(query) <= 200 or any(ord(char) < 32 for char in query):
            raise ValidationError("query must contain 1 to 200 printable characters")
        year = _validate_year(year)
        limit = _validate_integer(limit, "limit", minimum=1, maximum=100)
        offset = _validate_integer(offset, "offset", minimum=0, maximum=10_000)
        payload = self._get_json(
            ELASTICSEARCH_PATH,
            {"q": query, "periodo": year, "size": limit, "from": offset},
        )
        if not isinstance(payload, Mapping) or not isinstance(payload.get("hits"), list):
            raise ApiError(
                "Elasticsearch response did not contain hits",
                endpoint=ELASTICSEARCH_PATH,
            )
        total_raw = payload.get("total", 0)
        if isinstance(total_raw, Mapping):
            total_raw = total_raw.get("value", 0)
        if isinstance(total_raw, bool):
            raise ApiError("Elasticsearch total was invalid", endpoint=ELASTICSEARCH_PATH)
        try:
            total = int(total_raw)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ApiError(
                "Elasticsearch total was invalid", endpoint=ELASTICSEARCH_PATH
            ) from exc
        if total < 0:
            raise ApiError("Elasticsearch total was negative", endpoint=ELASTICSEARCH_PATH)
        items: list[dict[str, Any]] = []
        for hit in payload["hits"]:
            if not isinstance(hit, Mapping) or not isinstance(hit.get("_source"), Mapping):
                raise ApiError(
                    "Elasticsearch response contained an invalid hit",
                    endpoint=ELASTICSEARCH_PATH,
                )
            item = dict(hit["_source"])
            if "_id" in hit:
                item["_id"] = hit["_id"]
            if "_score" in hit:
                item["_score"] = hit["_score"]
            items.append(item)
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": items,
        }
