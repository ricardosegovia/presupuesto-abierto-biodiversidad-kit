"""pa-biodiv: explicitly bounded reads, JSON evidence and deterministic context."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from . import __version__
from .bulk import aggregate_biodiversity, download_annual, annual_download_url, iter_tsv_records, load_biodiversity_profile
from .client import PresupuestoAbiertoClient, PresupuestoAbiertoError, ValidationError
from .context import build_context, resources, verify_resources
from .evidence import EvidenceSession, file_hash, sanitize, write_json
from .workflows import payees_all

def json_object(value):
    try:
        result = json.loads(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError("Use a JSON object") from e
    if not isinstance(result, dict):
        raise argparse.ArgumentTypeError("Use a JSON object")
    return result

def fields(value):
    result = value.split(",")
    if any(not v for v in result):
        raise argparse.ArgumentTypeError("Use comma-separated field names")
    return result

def parser():
    p = argparse.ArgumentParser(prog="pa-biodiv")
    p.add_argument("--version", action="version", version=__version__)
    commands = p.add_subparsers(dest="command", required=True)
    for name in ("sample", "catalog", "aggregate"):
        q = commands.add_parser(name)
        q.add_argument("--year", type=int, required=True)
        q.add_argument("--dataset", choices=["pagos", "municipios", "gobiernos_regionales"], default="pagos")
        q.add_argument("--where", type=json_object, default={})
        q.add_argument("--limit", type=int, default=1 if name == "sample" else 100)
        q.add_argument("--offset", type=int, default=0)
        if name != "sample":
            q.add_argument("--group-by", type=fields, default=["capitulo"])
        local_options(q)
    q = commands.add_parser("payees")
    q.add_argument("--year", type=int, required=True)
    q.add_argument("--query", required=True)
    q.add_argument("--max-pages", type=int, default=20)
    local_options(q)
    q = commands.add_parser("download")
    q.add_argument("--year", type=int, required=True)
    q.add_argument("--dataset", choices=["pagos", "municipios", "gobiernos_regionales"], default="pagos")
    q.add_argument("--cache-dir", type=Path, default=Path(".cache/annual"))
    q.add_argument("--refresh", action="store_true")
    q.add_argument("--output", type=Path)
    q = commands.add_parser("scan")
    q.add_argument("--input", type=Path, required=True)
    q.add_argument("--year", type=int, required=True)
    q.add_argument("--dataset", choices=["pagos", "gobiernos_regionales"], default="pagos")
    q.add_argument("--profile", type=Path)
    q.add_argument("--include-debt", action="store_true", help="Disable devengo!=0/deuda_flotante=0 local display rules")
    q.add_argument("--output", type=Path)
    q = commands.add_parser("context")
    q.add_argument("action", choices=["build"])
    q.add_argument("--output", type=Path, default=Path("CONTEXT.md"))
    q = commands.add_parser("verify")
    q.add_argument("--live", action="store_true")
    q.add_argument("--year", type=int, default=2025)
    local_options(q)
    return p

def local_options(q):
    q.add_argument("--cache-dir", type=Path, default=Path(".cache"))
    q.add_argument("--refresh", action="store_true")
    q.add_argument("--output", type=Path)

def envelope(operation, data, *, dataset=None, year=None, metric=None, state="unknown", warnings=None, sources=None):
    return {"kit_version": __version__, "operation": operation,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "coverage": {"dataset": dataset, "year": year, "institutional_coverage_verified": False},
            "metric": metric, "completeness": state,
            "observed": sanitize(data), "interpretation": None, "attribution": None,
            "warnings": warnings or [], "sources": sources or []}

def emit(result, output=None):
    result = sanitize(result)
    if output:
        write_json(output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))

def run(args):
    if args.command == "context":
        content = build_context()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
        return {"output": str(args.output), "sha256": hashlib.sha256(content.encode()).hexdigest(), "network": False}
    if args.command == "scan":
        header = next(iter_tsv_records(args.input), None)
        if header is not None and not {"partida", "nombre_partida"}.issubset(header):
            raise ValidationError("Scanning requires central/GORE budget fields; municipality attribution is unsupported")
        data = aggregate_biodiversity(args.input, profile_path=args.profile, mimic_api=not args.include_debt, year=args.year)
        profile = args.profile or resources() / "profiles/biodiversity_conservative.json"
        warnings = data["warnings"] + ["Candidatos léxicos, no gasto atribuible oficial; coeficientes históricos NO aplicados."]
        warnings += ["El total devengo usa el campo publicado normalizado; no suma las métricas originales de distintas monedas."]
        if args.dataset == "gobiernos_regionales":
            warnings.append("Universo GORE seleccionado explícitamente; no se consolida con Gobierno Central.")
        available = data["classification_coverage"]["estimate_available"]
        return envelope("scan", data, dataset=args.dataset, year=args.year, metric="devengo_normalizado_reportado",
                        state="local_stream_complete" if available else "unavailable_or_invalid",
                        warnings=warnings, sources=[{"file": str(args.input), "sha256": file_hash(args.input),
                                                   "profile_sha256": file_hash(profile),
                                                   "references_applied": False}])
    if args.command == "download":
        path = download_annual(args.year, args.cache_dir, dataset=args.dataset, force=args.refresh)
        data = {"path": str(path), "sha256": file_hash(path), "bytes": path.stat().st_size}
        write_json(path.with_suffix(".manifest.json"), {"source": annual_download_url(args.year, dataset=args.dataset),
                   "validated_at_utc": datetime.now(timezone.utc).isoformat(), **data})
        return envelope("download", data, dataset=args.dataset, year=args.year, state="gzip_validated",
                        warnings=["Descarga explícita: aún no es un resultado de biodiversidad.",
                                  "La disponibilidad del archivo depende de dataset y año."],
                        sources=[{"source": annual_download_url(args.year, dataset=args.dataset)}])
    if args.command == "verify":
        result = verify_resources()
        if not args.live:
            return result
    session = EvidenceSession(args.cache_dir, refresh=args.refresh or (args.command == "verify" and args.live))
    client = PresupuestoAbiertoClient(session=session, retries=1)
    warnings = ["Resultado limitado al universo publicado; no representa automáticamente todo el Estado."]
    if args.command == "verify":
        data = client.search_records(where={"periodo": args.year}, limit=1)
        result = envelope("verify_live", {"offline": result, "sample_rows": len(data),
                          "capability": "GET pagos.json scoped by year, limit=1"},
                          dataset="pagos", year=args.year, state="live_capability_observed",
                          warnings=["Verificación mínima: no certifica agregaciones ni disponibilidad futura."])
    elif args.command == "payees":
        data = payees_all(client, args.query, year=args.year, max_pages=args.max_pages)
        result = envelope("payees", data, year=args.year, metric="indice_receptores_no_verificada",
                          state="index_complete" if data["pagination_complete"] else "index_partial",
                          warnings=warnings + data["warnings"])
    else:
        where = dict(args.where)
        if "periodo" in where and where["periodo"] != args.year:
            raise ValidationError("--year and where.periodo disagree")
        where["periodo"] = args.year
        if args.dataset != "pagos":
            warnings.append("Universo alternativo seleccionado explícitamente; esquema/cobertura no equivalentes.")
        if args.command == "sample":
            data = client.search_records(dataset=args.dataset, where=where, limit=args.limit, offset=args.offset)
            state, metric = "sample_not_exhaustive", "raw_reported_fields"
        else:
            data = client.summarize(dataset=args.dataset, where=where, group_by=args.group_by,
                                    limit=args.limit, offset=args.offset)
            state = "possible_truncation" if len(data) >= args.limit or args.offset else "not_truncated_observed"
            metric = "api_default_sum_unverified"
            warnings.append("sum es el agregado predeterminado NO verificado: no etiquetarlo como devengo o pago.")
            if args.command == "catalog":
                data = [{k: v for k, v in row.items() if k != "sum"} for row in data]
                metric = None
        if not data:
            warnings.append("Respuesta vacía: no implica gasto cero. Revisar cobertura, códigos, nombres y fuentes complementarias.")
            state = "empty_not_zero"
        result = envelope(args.command, data, dataset=args.dataset, year=args.year, metric=metric,
                          state=state, warnings=warnings)
    result["sources"] = session.provenance()
    return result

def main(argv=None):
    args = parser().parse_args(argv)
    try:
        result = run(args)
        emit(result, getattr(args, "output", None))
        return 0
    except (PresupuestoAbiertoError, OSError, ValueError) as exc:
        # No internal remote error bodies, cookies or authentication headers are exposed.
        print(json.dumps({"error": type(exc).__name__, "message": str(exc) if isinstance(exc, PresupuestoAbiertoError) else "Local input/output validation failed"}, ensure_ascii=False), file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
