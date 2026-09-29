"""Private local response cache and provenance; no authentication/header logging."""
from __future__ import annotations
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import requests
from .client import _build_session, _validate_api_url

def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")

def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()

def file_hash(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()

def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as f:
            temporary = Path(f.name)
            json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.write("\n")
        temporary.replace(path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()

def sanitize(value: Any) -> Any:
    if isinstance(value, list):
        return [sanitize(v) for v in value]
    if not isinstance(value, dict):
        return value
    private = str(value.get("persona", "0")) == "1"
    redacted = {"beneficiario", "nombre_beneficiario", "numero_documento", "orden_de_compra", "_id"} if private else set()
    if str(value.get("bloqueo_oc", "0")) == "1":
        redacted.add("orden_de_compra")
    return {k: ("[OMITIDO]" if k in redacted else sanitize(v)) for k, v in value.items()}

def public_params(params: dict) -> dict:
    result = dict(params)
    if "q" in result:
        result["q"] = "[BÚSQUEDA LOCAL OMITIDA]"
    for key in ("where", "where-not"):
        if key in result:
            where = json.loads(result[key])
            for field in ("beneficiario", "nombre_beneficiario"):
                if field in where:
                    where[field] = "[FILTRO LOCAL OMITIDO]"
            result[key] = where
    return result

class CachedResponse:
    def __init__(self, record: dict):
        self.status_code = record["http"]
        self.record = record
    def json(self):
        return self.record["body"]

class EvidenceSession:
    def __init__(self, cache_dir: Path, *, refresh: bool = False, session=None):
        self.cache_dir = Path(cache_dir)
        self.refresh = refresh
        self.session = session if session is not None else _build_session(1)
        self.records: list[dict] = []

    def get(self, url: str, **kwargs):
        _validate_api_url(url)
        params = kwargs.get("params", {})
        query = {"endpoint": url, "params": params}
        key = digest(query)
        path = self.cache_dir / "queries" / (key + ".json")
        if not self.refresh and path.is_file():
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
                if record["query"] == query and record["http"] == 200 and record["body_sha256"] == digest(record["body"]):
                    self.records.append({**record, "cache_hit": True, "cache_path": str(path)})
                    return CachedResponse(record)
            except (OSError, ValueError, KeyError, TypeError):
                pass
        kwargs["allow_redirects"] = False
        response = self.session.get(url, **kwargs)
        status = response.status_code
        try:
            body = response.json()
        except (ValueError, TypeError):
            return response
        record = {"query": query, "http": status,
                  "queried_at_utc": datetime.now(timezone.utc).isoformat(),
                  "body_sha256": digest(body), "body": body}
        if status == 200:
            # Immutable history plus a replaceable cache pointer; both remain private.
            history = self.cache_dir / "responses" / (key + "-" + record["queried_at_utc"].replace(":", "-") + ".json")
            write_json(history, record)
            write_json(path, record)
        self.records.append({**record, "cache_hit": False, "cache_path": str(path)})
        return response

    def provenance(self) -> list[dict]:
        return [{"source": r["query"]["endpoint"],
                 "parameters": public_params(r["query"]["params"]),
                 "queried_at_utc": r["queried_at_utc"], "http": r["http"],
                 "body_sha256": r["body_sha256"], "cache_hit": r["cache_hit"],
                 "private_cache_path": r["cache_path"]} for r in self.records]
