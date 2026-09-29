# Biodiversidad: exploración, no atribución automática

La API no tiene una dimensión nativa `biodiversidad`. La consulta presupuestaria y la clasificación externa son tareas diferentes. Definir período, universo, métrica y regla antes de comparar resultados.

## Qué devuelve el kit

El perfil léxico conservador reconoce biodiversidad, áreas protegidas, humedales, bosque nativo, conservación explícita de especies/ecosistemas y términos relacionados en campos presupuestarios. No busca en beneficiario ni en texto del documento. “Conservación” sola y “ambiental” no bastan.

`scan` informa candidatos, coincidencias, ejemplos sanitizados y suma del campo devengo normalizado publicado. Por defecto aplica localmente devengo distinto de cero y deuda flotante cero; conserva ajustes negativos. `--include-debt` desactiva ambas reglas locales. No son una definición universal de gasto.

Un candidato léxico no representa automáticamente gasto atribuible. La falta de candidatos tampoco demuestra inexistencia de gasto relevante: nombres genéricos producen falsos negativos. No clasificar por entero Medio Ambiente, CONAF, PDI u otra institución sin evidencia.

## Referencias históricas

El registro y lookup contienen 144 reglas históricas. Se conservan byte a byte, códigos y coeficientes incluidos; el kit no normaliza ni modifica las tablas originales. Algunos códigos originales no tienen ceros iniciales y hay vigencias vacías. Antes de consultar, verificar y formular códigos según el esquema API, sin alterar la referencia.

La ponderación histórica combina elegibilidad y atribución; no basta trasladar uno de los coeficientes. BIOFIN usa niveles 100/75/50/25/1 %, pero esta versión no los aplica, no calibra capítulos, no actualiza BER ni convierte a moneda constante. La vigencia y extensión a nuevos años requieren revisión.

El registro conserva correcciones y referencias; no asumir que PDI completa equivale a BIDEMA o que un tribunal ambiental tiene atribución del 100 %. El proxy léxico y las reglas históricas son recursos distintos.

## Contabilidad e interpretación

Distinguir devengo, pago y presupuesto aprobado/vigente. Las métricas originales y normalizadas no se suman; no mezclar pesos, miles o millones sin conversión explícita. Los campos `*_original` y moneda requieren revisión si se trabaja con unidades originales.

Una transferencia fiscal y el gasto del receptor son perspectivas del mismo flujo, no componentes aditivos. Consultas repetidas, agrupamientos diferentes y fuentes de inversión pueden solaparse. No consolidar automáticamente.

Cada propuesta debe declarar criterio, fuente, coordenada, año, cobertura, incertidumbre y revisión pendiente. Los campos `interpretation` y `attribution` de las salidas se dejan vacíos, para no convertir observación en una conclusión no revisada.
