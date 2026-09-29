# Presupuesto Abierto: kit de contexto y exploración de biodiversidad

Repositorio independiente para investigadores y asistentes diversos. Incluye instrucciones, referencias históricas y herramientas GET auditables. No es una estimación oficial ni un agente autónomo.

## Inicio

Python 3.10 o posterior; única dependencia de ejecución: requests.

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install .
pa-biodiv verify
pa-biodiv context build --output CONTEXT.md
```

Leer [AGENTS.md](AGENTS.md) y [CONTEXT.md](CONTEXT.md). Para un asistente con acceso al repositorio, abrir la carpeta y seguir AGENTS.md. Para otro asistente, adjuntar CONTEXT.md y proporcionar las referencias pertinentes cuando sean necesarias. No presupone acceso a shell, internet ni conectores del asistente.

## Capacidades

`sample`, `catalog` y `aggregate` consultan una muestra o agrupamiento acotado. `payees` recorre el índice de receptores. `download` descarga únicamente por pedido explícito. `scan` analiza un archivo local en streaming. `context build` genera contexto sin LLM; `verify` verifica recursos sin red.

Las agregaciones API conservan sum como métrica no verificada. El análisis local identifica devengo reportado de candidatos léxicos, sin aplicar coeficientes históricos.

## Documentación y referencias

- [Acceso y contrato reconciliado](src/pa_biodiv/resources/api/access.md).
- [Modelo histórico de datos](src/pa_biodiv/resources/domain/data-model.md).
- [Metodología y referencias](src/pa_biodiv/resources/domain/methodology.md).
- [Límites y vigencia](src/pa_biodiv/resources/domain/limits.md).
- [Recetas verificables](src/pa_biodiv/resources/guides/recipes.md).
- [Caso de tribunales](src/pa_biodiv/resources/cases/tribunales.md).
- [144 reglas históricas](src/pa_biodiv/resources/reference/registro_programas_biodiversidad.csv).
- [Lookup original de 144 reglas](src/pa_biodiv/resources/reference/lookup_table_glosas_querybuild.csv).
- [Procedencia, hashes y condiciones](src/pa_biodiv/resources/provenance.json).

El paquete instalado incluye todos los recursos; no depende de rutas del proyecto original. No se copian memorias, planillas grandes, resultados BER ni archivos privados.

## Demostraciones

```bash
pa-biodiv catalog --year 2025 --where '{"partida":"25"}' --group-by capitulo,nombre_capitulo
pa-biodiv payees --year 2025 --query "Primer Tribunal Ambiental"
pa-biodiv scan --input tests/fixtures/pagos-small.tsv --year 2025
```

Ver las recetas para descarga explícita, exportación JSON y búsquedas por variantes.

## Pruebas y privacidad

```bash
python -m unittest discover -s tests -v
pa-biodiv verify
# Opcional; nunca parte de las pruebas ordinarias:
pa-biodiv verify --live --year 2025
```

Las pruebas ordinarias usan fixtures simulados. Cachés, descargas, salidas y entornos quedan excluidos de Git. Las respuestas completas permanecen locales; revisar privacidad antes de compartirlas. Los JSON públicos omiten identificadores personales y órdenes de compra bloqueadas.

Una respuesta vacía no es cero, un beneficiario no es necesariamente ejecutor y una finalidad ambiental no prueba atribución a biodiversidad. No consolidar fuentes ni coeficientes sin revisión metodológica. Sin publicación automática ni licencia nueva asignada a materiales de terceros.
