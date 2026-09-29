"""Small auditable workflows; receiver search is never biodiversity attribution."""
from __future__ import annotations
from .client import ApiError, ValidationError, _validate_integer

def payees_all(client, query: str, *, year: int, max_pages: int = 20) -> dict:
    _validate_integer(max_pages, "max_pages", minimum=1, maximum=100)
    items, seen, totals, warnings = [], set(), set(), []
    offset = 0
    complete = False
    for _ in range(max_pages):
        try:
            page = client.search_payees(query, year=year, limit=100, offset=offset)
        except ApiError:
            if not items:
                raise
            warnings.append("Error en una página posterior: resultado parcial.")
            break
        totals.add(page["total"])
        if len(totals) > 1:
            warnings.append("El total del índice cambió durante la paginación.")
        current = page["items"]
        duplicate = False
        for item in current:
            key = item.get("_id")
            if key is None:
                raise ApiError("Payee index omitted stable hit identifier")
            if key in seen:
                duplicate = True
                continue
            seen.add(key)
            items.append(item)
        offset += len(current)
        if duplicate:
            warnings.append("Resultados repetidos entre páginas: completitud no certificada.")
            break
        if offset >= page["total"]:
            complete = len(totals) == 1 and len(items) == page["total"]
            break
        if not current:
            warnings.append("Página vacía antes de alcanzar el total declarado.")
            break
    if not complete:
        warnings.append("Índice parcialmente recorrido; aumentar --max-pages o revisar disponibilidad.")
    warnings.append("Son receptores/proveedores: no identifican automáticamente ejecutor, finalidad ni gasto propio.")
    return {"items": items, "reported_totals": sorted(totals), "pagination_complete": complete,
            "returned": len(items), "warnings": warnings}
