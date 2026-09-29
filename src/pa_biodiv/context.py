"""Deterministic context from packaged curated Markdown, with no LLM dependency."""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
from . import __version__
from .client import ValidationError

def resources() -> Path:
    return Path(__file__).resolve().parent / "resources"

def build_context() -> str:
    root = resources()
    manifest = json.loads((root / "context-manifest.json").read_text(encoding="utf-8"))
    parts = [f"# Contexto portable: Presupuesto Abierto y biodiversidad\n\nVersión del kit: {__version__}; fecha del contexto: {manifest['date']}.\n"]
    for item in manifest["sections"]:
        path = root / item
        if root.resolve() not in path.resolve().parents:
            raise ValidationError("Context resource is outside the package")
        body = path.read_text(encoding="utf-8").strip()
        parts.append(f"<!-- fuente: {item}; sha256: {hashlib.sha256(path.read_bytes()).hexdigest()} -->\n\n{body}\n")
    result = "\n".join(parts).rstrip() + "\n"
    if len(re.findall(r"\S+", result)) > 3000:
        raise ValidationError("Generated context exceeds 3000 words")
    return result

def verify_resources() -> dict:
    import csv
    root = resources()
    provenance = json.loads((root / "provenance.json").read_text(encoding="utf-8"))
    counts = {}
    for item in provenance["references"]:
        path = root / item["target"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise ValidationError("Reference checksum mismatch")
        with path.open(encoding="utf-8-sig", newline="") as f:
            counts[path.name] = len(list(csv.DictReader(f)))
        if counts[path.name] != 144:
            raise ValidationError("Expected 144 historical rules")
    text = build_context()
    return {"version": __version__, "reference_counts": counts,
            "context_words": len(re.findall(r"\S+", text)),
            "context_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "network": False}
