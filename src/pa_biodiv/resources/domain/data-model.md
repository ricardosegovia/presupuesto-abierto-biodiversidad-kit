# Modelo de datos observado

Última validación: **2026-07-30**.

El modelo se reconstruyó desde muestras públicas de 2016 y 2025, el encabezado
del TSV anual 2025, agregaciones del frontend y el documento histórico de
integración v2.5. Cuando el significado procede solo de ese documento antiguo
se indica como contexto, no como contrato vigente.

## Entidades y relaciones

```text
partida
└── capitulo
    └── area
        └── registro de ejecución
            ├── subtitulo ── item ── asignacion
            ├── programa presupuestario
            ├── proyecto/iniciativa BIP
            ├── beneficiario/proveedor/receptor
            ├── documento y orden de compra
            ├── región/ubicación geográfica
            └── devengo y pago
```

- `partida` suele representar un ministerio u otro organismo superior.
- `capitulo` representa el servicio o institución dependiente.
- `area` representa una unidad/área presupuestaria.
- La identidad institucional práctica es la tupla
  `(partida, capitulo, area)`. Los códigos deben conservarse como texto.
- La clasificación del gasto sigue
  `(subtitulo, item, asignacion)`.
- Un beneficiario se relaciona con muchas instituciones y años.
- Los campos BIP y programa presupuestario permiten asociar ejecución con una
  iniciativa o programa cuando vienen informados.

No se observó un identificador único de registro. `numero_documento` tampoco es
globalmente único y varios registros pueden compartir documento, beneficiario,
fecha y monto. Por eso no se implementa `get_record(id)`.

## Dataset `pagos` y `gobiernos_regionales`

Ambos devolvieron el mismo conjunto de 45 campos en las muestras actuales.
`null`, cadena vacía y el literal TSV `NULL` aparecen según el formato y no
deben confundirse entre sí.

| Campo | Tipo observado | Nulable | Interpretación |
|---|---|---:|---|
| `periodo` | integer | no | Año de ejecución |
| `mes` | integer | no | Mes de ejecución, 1–12 |
| `partida` | string | no | Código de organismo superior; conserva ceros |
| `nombre_partida` | string | no | Nombre de ministerio/organismo |
| `capitulo` | string | no | Código de servicio/institución |
| `nombre_capitulo` | string | no | Nombre de servicio/institución |
| `area` | string | no | Código de área presupuestaria |
| `nombre_area` | string | no | Nombre del área |
| `subtitulo` | string | no | Nivel de clasificación presupuestaria |
| `nombre_subtitulo` | string | no | Denominación del subtítulo |
| `beneficiario` | string | sí | Identificador del beneficiario; RUT de entidad o valor seudonimizado |
| `nombre_beneficiario` | string | sí | Proveedor/receptor; puede faltar en registros agregados |
| `numero_documento` | string | sí | Número informado por la institución |
| `fecha_documento` | date string | sí | `YYYY-MM-DD` |
| `tipo_documento` | string | sí | Vocabulario de documento tributario/contable |
| `orden_de_compra` | string | sí | Código de orden de ChileCompra cuando existe |
| `fecha_ingreso` | date string | sí | Fecha de ingreso |
| `fecha_recepcion_conforme` | date string | sí | Recepción conforme |
| `fecha_pago` | date string | sí | Fecha efectiva de pago |
| `moneda` | string | no | `PESOS`, `DOLARES` u otra moneda informada |
| `monto_original` | number | no | Pago en la unidad/moneda original |
| `monto` | number | no | Monto pagado mostrado por el portal |
| `devengo_original` | number | no | Devengo original |
| `devengo` | number | no | Gasto devengado mostrado por el portal |
| `honorario` | 0/1 | no | Clasificación como honorario u operación afín |
| `proveedor` | 0/1 | no | Clasificación como proveedor/receptor |
| `sector` | string | sí | Código de sector económico |
| `region` | string | sí | Código regional asociado |
| `agregado` | 0/1 | no | Registro sin el mismo detalle transaccional |
| `persona` | 0/1 | no | Beneficiario es persona natural |
| `intraestado` | 0/1 | no | Transferencia/operación dentro del Estado |
| `bloqueo_oc` | 0/1 | no | La UI no debe consultar/mostrar detalle de la OC |
| `item` | string | sí | Ítem presupuestario |
| `nombre_item` | string | sí | Denominación del ítem |
| `asignacion` | string | sí | Asignación presupuestaria |
| `nombre_asignacion` | string | sí | Denominación de la asignación |
| `codigo_bip` | string | sí | Código de iniciativa/proyecto BIP |
| `nombre_bip` | string | sí | Nombre de iniciativa/proyecto BIP |
| `codigo_ubicacion_geografica` | string | sí | Código de ubicación |
| `nombre_ubicacion_geografica` | string | sí | Nombre de ubicación |
| `codigo_programa_presupuestario` | string | sí | Código de programa de la Ley de Presupuestos |
| `nombre_programa_presupuestario` | string | sí | Nombre del programa |
| `dias_de_pago` | number | sí | Días calculados para pago |
| `dias_de_pago_cat` | string/number | sí | Categoría usada por la visualización |
| `deuda_flotante` | 0/1 | no | Documento arrastrado como deuda flotante |

### Métricas

El frontend distingue:

- `devengo`: obligación/gasto devengado;
- `monto`: pago;
- versiones `*_original`: valores antes de la normalización que aplica el
  portal.

La interfaz señala que los valores presentados están en pesos chilenos. Aun
así, para resultados auditables se deben conservar `moneda` y las métricas
originales. Puede haber ajustes negativos en meses posteriores.

El proxy incluido usa `devengo` y, para aproximarse a la consulta de detalle
observada, excluye `devengo == 0` y `deuda_flotante != 0`. Esta decisión es una
regla del análisis, no una definición universal de “gasto público”.

### Banderas y privacidad

Las banderas son números `0/1` en `pagos`; no asumir booleanos JSON.

Cuando `persona=1`, muestras recientes presentaron un identificador con forma
de hash en `beneficiario`. El frontend también evita mostrar el RUT de personas
y respeta `bloqueo_oc`. Un consumidor debe:

- no intentar revertir o correlacionar identificadores;
- no incluir identificadores personales en logs o ejemplos;
- no consultar órdenes de compra cuando `bloqueo_oc=1`;
- limitar resultados y devolver agregados siempre que sea suficiente.

## Dataset `municipios`

La muestra 2025 devolvió 23 campos:

| Campo | Tipo observado | Interpretación |
|---|---|---|
| `periodo` | integer | Año |
| `region` | string | Código regional |
| `nombre_region` | string | Región |
| `provincia` | string | Código provincial |
| `nombre_provincia` | string | Provincia |
| `comuna` | string | Código comunal |
| `nombre_comuna` | string | Comuna |
| `municipalidad` | string | Código de municipalidad |
| `nombre_municipalidad` | string | Municipalidad |
| `cod_tipo_doc` | integer | Código de documento |
| `tipo_documento` | string | Tipo de documento |
| `fecha_documento` | date string | Fecha del documento |
| `devengo` | number | Gasto devengado |
| `devengo_original` | number | Devengo original |
| `beneficiario` | string | Identificador del receptor |
| `nombre_beneficiario` | string | Nombre del receptor |
| `rubro_economico` | string | Rubro SII |
| `subrubro_economico` | string | Subrubro SII |
| `actividad_economica` | string | Actividad SII |
| `deuda_flotante` | number | Bandera de deuda flotante |
| `mini_glosa_tramo` | string | Tramo resumido de tamaño |
| `glosa_tamano_segun_ventas` | string | Tamaño por ventas |
| `glosa_tramo_completa` | string | Descripción completa del tramo |

Este dataset no expone `subtitulo/item/asignacion`, BIP ni programa
presupuestario en la muestra. Por ello no permite trasladar sin más el
clasificador central de biodiversidad. Una búsqueda por nombre o actividad del
proveedor sería solo un proxy de receptor, no del propósito del gasto.

El sitio advierte que los datos municipales se presentan agregados conforme a
normas tributarias y de privacidad. Esta diferencia es material al comparar
conteos o granularidad con `pagos`.

## Vocabularios controlados

Confirmados o observados:

- años `periodo`: 2016–2026 en la exploración;
- jerarquía institucional: `partida/capitulo/area`;
- clasificación: `subtitulo/item/asignacion`;
- moneda;
- documento;
- sector económico;
- región y ubicación geográfica;
- programa presupuestario;
- iniciativa BIP;
- categorías de días de pago (`30`, `60`, `90`, `180`, `365`, `365+` en el
  frontend antiguo).

La API no entregó un catálogo separado validado para cada vocabulario. Se
pueden derivar valores con `distinct` o `group-by`, siempre con `where` estrecho
y caché. Una consulta nacional de `distinct periodo` tuvo comportamiento
intermitente, por lo que esos catálogos no deben regenerarse en cada ejecución.

## Cobertura institucional

`pagos`, `municipios` y `gobiernos_regionales` son universos separados. Un
resultado sobre `pagos` no equivale automáticamente a “todo el Estado”.

Para una estimación nacional completa se requiere:

1. clasificar Gobierno Central en `pagos`;
2. clasificar gobiernos regionales con su tabla;
3. definir una metodología compatible para el esquema municipal agregado;
4. resolver posibles transferencias intraestado y evitar doble conteo;
5. documentar instituciones o meses que no publicaron datos.

Véase [Límites y vigencia](limits.md).
