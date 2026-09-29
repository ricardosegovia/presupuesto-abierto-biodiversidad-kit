# Recetas ejecutables

Ejecutar desde la raíz del kit tras instalarlo. Los ejemplos de red son explícitos: no se ejecutan al leer contexto, instalar o correr pruebas.

## 1. Servicio por códigos

```bash
pa-biodiv sample --year 2025 --where '{"partida":"25","capitulo":"01"}' --limit 1
pa-biodiv catalog --year 2025 --where '{"partida":"25"}' --group-by capitulo,nombre_capitulo
pa-biodiv aggregate --year 2025 --where '{"partida":"25","capitulo":"01"}' --group-by subtitulo,nombre_subtitulo --output outputs/servicio.json
```

Los filtros son JSON, no `partida=25`. El catálogo descubre nombres/códigos publicados; el agregado no tiene métrica confirmada y no es gasto atribuible.

## 2. Institución por nombre y variantes

```bash
pa-biodiv sample --year 2025 --where '{"nombre_beneficiario":["PRIMER TRIBUNAL AMBIENTAL","ILUSTRE PRIMER TRIBUNAL AMBIENTAL","TRIBUNAL AMBIENTAL DE ANTOFAGASTA"]}' --limit 10
pa-biodiv payees --year 2025 --query "Primer Tribunal Ambiental" --max-pages 20 --output outputs/receptores.json
```

La muestra por igualdad no es exhaustiva; revisar completitud. La búsqueda textual puede devolver receptores ajenos por palabras individuales; no atribuir sus montos al tribunal.

## 3. Archivo anual ya disponible

```bash
pa-biodiv scan --input tests/fixtures/pagos-small.tsv --year 2025 --output outputs/candidatos-demo.json
```

El fixture tiene cinco registros ficticios sanitizados: verifica funcionamiento, no representa gasto real. La suma de candidatos predeterminada es 1250 unidades de prueba. Para un archivo real, seleccionar su año.

La descarga es otra operación, voluntaria y potencialmente grande:

```bash
pa-biodiv download --year 2025 --dataset pagos
pa-biodiv scan --input .cache/annual/pagos-2025.gz --year 2025 --output outputs/candidatos-2025.json
```

## Preparación y control

```bash
pa-biodiv context build --output CONTEXT.md
pa-biodiv verify
python -m unittest discover -s tests -v
# Solo si se desea una solicitud mínima de red:
pa-biodiv verify --live --year 2025
```

El contexto es portable para lectura; las consultas ejecutables requieren Python y acceso a internet. Adjuntar solo CONTEXT.md no otorga a un asistente herramientas ni acceso al resto de las referencias.
