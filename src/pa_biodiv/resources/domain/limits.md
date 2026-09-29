# Límites, vigencia y decisiones pendientes

## Hechos observados

El portal expone universos separados; municipios no ofrece el mismo esquema programático. Hay consultas intermitentes y agregaciones nacionales lentas. El endpoint de receptores devuelve beneficiarios, no ejecutores. No existe una clave transaccional estable validada.

Las consultas de tribunales de septiembre de 2026 devolvieron respuestas vacías en la asignación del Tesoro y por beneficiarios. El diccionario histórico excluye partida 50 de Agregación; esto es consistente con el límite observado, no una certificación de todas las fuentes actuales.

## No convertir inferencias en hechos

No hay garantía contractual de API, retención o rate limit. Las capacidades vistas en julio o septiembre no aseguran disponibilidad futura. Un HTTP 200 no demuestra finalidad ambiental, cobertura completa ni criterio contable del campo agregado.

La nota histórica del modelo de datos se mantiene para conservar contexto. Para ejecución técnica prevalece el documento operativo de este kit. No trasladar ciegamente ejemplos antiguos de `sum`, `where-not`, años o nombres.

## Pendientes metodológicos

Revisar vigencia de reglas, cambios de códigos, transferencias intraestado, deuda flotante, subprogramas ausentes y proyectos BIP. La primera versión no proporciona una estimación nacional consolidada, no integra MIDESO y no empalma automáticamente series históricas.

Municipios requiere una metodología adicional. GORE debe consultarse y reportarse por separado. Presupuesto aprobado y Tesoro pueden requerir CSV DIPRES; gasto propio de entidades autónomas puede requerir memorias o estados financieros.

## Operación segura

Solo descargas anuales explícitas y cacheadas. Ante un error se devuelve estado y mensaje sanitizado, no detalles internos del servidor. Revisar salidas antes de compartir; los archivos crudos privados quedan fuera de Git.

No publicar fuentes curadas con una licencia inventada. Los datos de Presupuesto Abierto se presentan bajo CC BY-SA 4.0 en su página oficial; otras tablas y documentos necesitan revisar sus condiciones específicas.
