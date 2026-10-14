# Instrucciones para asistentes e investigadores

Este kit explora ejecución presupuestaria y candidatos de biodiversidad. No produce una cifra oficial, no es un agente autónomo y no necesita claves de un proveedor de modelos.

## Orden de lectura

1. `README.md` y `CONTEXT.md`: alcance, instalación y contrato operativo.
2. API vigente del kit: `src/pa_biodiv/resources/api/access.md`.
3. Modelo completo: `src/pa_biodiv/resources/domain/data-model.md`.
4. Metodología y límites en `src/pa_biodiv/resources/domain/`.
5. Referencias de clasificación, recetas y caso de tribunales antes de cualquier consulta de biodiversidad cuando correspondan al universo.

Si una nota histórica difiere de las instrucciones operativas actuales, prevalecen estas instrucciones y el contrato del kit. Los documentos reconstruidos NO son documentación contractual oficial.

## Procedimiento obligatorio

Precisar pregunta, año, universo, métrica y finalidad. Si falta una decisión material, preguntar; no inferir que biodiversidad equivale a todo gasto ambiental. Identificar partida, capítulo, programa, área y clasificación cuando proceda, conservando códigos como texto.

Toda consulta sobre gasto en biodiversidad debe utilizar las referencias del kit antes de calcular resultados: `src/pa_biodiv/resources/reference/lookup_table_glosas_querybuild.csv` para construir el cruce de coordenadas y `src/pa_biodiv/resources/reference/registro_programas_biodiversidad.csv` para documentar la regla y su estado. El perfil léxico conservador es solo una señal complementaria; no puede sustituir esas referencias ni justificar por sí solo un cero o un ranking. Tratar `NA` y las coincidencias entre reglas según la metodología, deduplicar registros solapados y declarar si se aplican o no ponderaciones históricas.

Comenzar con una consulta pequeña o catálogo institucional. Revisar esquema, cobertura, límites, variantes de nombres y todas las páginas necesarias. Solo ejecutar descargas anuales mediante una instrucción explícita del usuario; una respuesta vacía nunca dispara una descarga.

Usar exclusivamente las operaciones GET permitidas del kit. No explorar endpoints no validados, solicitar credenciales, consultar órdenes de compra bloqueadas ni intentar identificar personas seudonimizadas.

Separar evidencia observada, interpretación y atribución. Diferenciar devengo, pago, presupuesto aprobado/vigente; moneda normalizada/original; año completo/parcial; transferencia/uso final; financiador/ejecutor/beneficiario. No sumar fuentes o consultas solapadas.

Citar fuente, parámetros no sensibles, fecha UTC, hash, universo, completitud y regla aplicada. `sum` de una agregación API no tiene métrica verificada en esta versión. No renombrarlo como devengo o pago. Un resultado vacío no es cero; un receptor con nombre ambiental no acredita finalidad ni gasto propio.

Consultar reglas históricas como hipótesis, no imponer coeficientes a códigos o años nuevos. Proponer candidatos con su evidencia y revisión pendiente; la clasificación definitiva requiere aprobación metodológica.

## Autonomía y privacidad

No cambiar reglas históricas, publicar cifras oficiales, consolidar transferencias o ampliar a otras fuentes automáticamente. Documentar la necesidad de CSV DIPRES, memorias o BIP/MIDESO si la API no cubre la pregunta.

La caché contiene respuestas completas locales: no compartirla sin revisar datos personales. Git excluye cachés y descargas. Las salidas públicas sanitizan personas y órdenes de compra bloqueadas. No registrar cookies ni cabeceras de autenticación.

Antes de entregar: ejecutar `pa-biodiv verify`, revisar advertencias y declarar resultados parciales. `verify --live` hace una solicitud mínima explícita; no certifica disponibilidad permanente.
