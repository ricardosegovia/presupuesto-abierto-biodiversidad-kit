# Acceso operativo a Presupuesto Abierto

Contexto preparado el 2026-09-29. Base permitida: `https://api.presupuestoabierto.gob.cl`. Consultas públicas GET, sin credenciales. El contrato es empírico y parcial, no oficial.

## Rutas

- `/api/v1/data/pagos.json`: Gobierno Central publicado por el portal.
- `/api/v1/data/gobiernos_regionales.json`: universo GORE separado.
- `/api/v1/data/municipios.json`: esquema municipal agregado, no equivalente.
- `/api/v1/elasticsearch`: índice de proveedores/receptores, NO de gasto propio ni de programas.
- `/data/pagos-AÑO.gz` y `/data/municipios-AÑO.gz`: descargas oficiales explícitas. No se garantiza disponibilidad de cualquier año.
- La URL predecible GORE fue 404 en la exploración histórica; el comando puede comprobarla explícitamente, pero nunca sustituye de forma automática otra fuente.

`aprobados`, instituciones y catálogos mencionados en antiguos frontends no se consideran endpoints operativos validados de este kit. No hay URL arbitraria, POST ni identificador único para `get_record(id)`.

## Parámetros y límites

`where` es un objeto JSON serializado; sus listas representan igualdad IN. Ejemplo: `{"periodo":2025,"partida":"25","capitulo":"01"}`. `group-by` contiene un arreglo de campos permitidos. Los códigos son texto; no sustituir `"01"` por `1`. Campos, tipos, años y límites se validan antes de enviar.

La muestra tiene año obligatorio, límite predeterminado 1 y máximo 1000. Las agregaciones requieren también un filtro institucional, regional o de beneficiario; límite predeterminado 100, máximo 1000. Se consultan secuencialmente con conexión de 5 s, lectura de 30 s y un reintento moderado. Un timeout no demuestra ausencia de gasto.

## Contrato reconciliado

La documentación inicial de julio describía `sum`, `metric` y filtros de despliegue. La extracción sectorial posterior detectó HTTP 500 al añadir `sum`/`where-not`. El contrato conservador del kit para agregar envía únicamente `where`, `group-by`, `limit` y `offset`. No activa filtros implícitos ni permite etiquetar el agregado predeterminado como devengo o pago.

`aggregate` conserva `sum` con `metric=api_default_sum_unverified`. `catalog` omite `sum` y conserva dimensiones/conteos. Si se requiere devengo identificable, analizar el campo `devengo` del TSV local, con sus advertencias metodológicas.

`search` transaccional dio errores FULLTEXT y queda fuera de la CLI. En Elasticsearch las palabras pueden generar coincidencias amplias; comillas no garantizan frase exacta. Revisar nombres/RUT institucionales y paginar. Un filtro exacto por nombre no equivale a búsqueda por comodines.

## Evidencia y cobertura

Las respuestas JSON estructuradas se guardan en una caché privada, con consulta, HTTP, fecha y SHA-256. No son captura de bytes HTTP originales. `--refresh` solicita datos nuevos y conserva historia local. Los resultados incluyen completitud, advertencias y fuente; las consultas con filtros de beneficiario omiten esos valores del manifiesto público.

Una lista más corta que el límite solo prueba que no se observó truncación, no que el universo institucional o todos los meses estén completos. `payees` recorre páginas de 100, hasta 20 por defecto; detecta límites, errores, duplicaciones o cambios de total y marca parcialidad.

Ante `[]`, revisar códigos, cobertura, año, nombres, RUT y fuentes complementarias. No crear un registro de gasto cero ni clasificar ausencias como ahorro.

## Fuentes oficiales

- [Presupuesto Abierto](https://presupuestoabierto.gob.cl/).
- [Datos, responsabilidad institucional y licencia](https://api.presupuestoabierto.gob.cl/about-data).
- [Diccionario histórico de integración v2.5](https://api.presupuestoabierto.gob.cl/files/Integracion_Portal_Ciudadano_2.5.pdf).

La documentación histórica no certifica el backend actual. Cada verificación en vivo debe registrar fecha y capacidades efectivamente comprobadas.
