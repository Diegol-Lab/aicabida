# ETL — Incorporación de comunas a AiCabida

Sistema para incorporar comunas de forma óptima y confiable. Separa dos capas
de datos con naturaleza distinta:

- 🟢 **Geometría** (*dónde* están las zonas) → oficial MINVU, automatizable.
- 🟡 **Normas** (CC, COS, altura, densidad…) → viven en el texto de la ordenanza,
  requieren verificación humana (dato legal).

## Backbone: `comunas_catalogo.json`

Única fuente de verdad por comuna: nombre, key, región MINVU, capa ArcGIS
(`service`/`tipo`/`layer_id`/`layer_riesgo`), código SII, centro+zoom y `estado`
(`pendiente → geometria → normas_revision → completa`).

## Pipeline

### Etapa 1 — Geometría  ✅ implementada
Fuente: **MINVU ArcGIS** (`geoide.minvu.cl/server/rest/services/IPT`), cobertura
nacional (16 servicios regionales). Cada comuna es una capa dentro del servicio
de su región.

```bash
cd etl
python extraer_geometria.py                # todas las 'pendiente' con ArcGIS
python extraer_geometria.py Nunoa Coquimbo # comunas específicas (por key)
python simplificar.py                      # reduce 5-17 MB → <1.3 MB (shapely)
```

Salidas:
- `data/PRC_<key>.geojson` — capa lean para el mapa (props: comuna, zona,
  zona_code, nombre, decreto). Ya simplificada (Douglas-Peucker ~7 m + 6 decimales).
- `etl/zonas/<key>_zonas.json` — zonas únicas con usos + decreto. Andamiaje
  para la Etapa 3.

Notas:
- Los nombres de capa y campos **varían por región** (`ZONA` vs `ZONA_1`,
  espacios vs guiones). El script tolera alias y hace matching robusto.
- La detección de zona en la app usa fallback de cercanía, así que la
  simplificación de bordes no afecta.

### Etapa 2 — Documentos (ordenanza, planos, DDU)  🔶 parcial
Fuentes: `instrumentosdeplanificacion.minvu.cl/<región>` + BCN LeyChile XML
(`leychile.cl/Consulta/obtxml?opt=7&idNorma=<id>`).

`extraer_tablas_bcn.py <idNorma> <carpeta>` descarga la ordenanza desde BCN y
extrae las tablas de normas (vienen como JPEG embebidos, no como texto).

**Lección del piloto (La Cisterna): la discovery del documento es el cuello de
botella y NO es confiablemente automatizable.** Casos reales encontrados:
- Un `idNorma` de la búsqueda era de **otra comuna** (Río Teno, Maule).
- Otro era solo una **modificación parcial**, no el texto refundido.
- El sitio municipal bloquea scraping (403); el portal MINVU RM filtra por JS.

→ Por eso el **`idNorma_bcn` (o URL de la ordenanza) debe guardarse VERIFICADO
por comuna en el catálogo**. Es el paso humano-en-el-loop del sistema. El
script `verificar()` chequea menciones de la comuna y zonas como cordura.

### Etapa 3 — Normas (asistida + revisión humana)  ⏳ pendiente
Leer las tablas (vision/OCR) → poblar `data/normas_prc.json` por zona, usando
`<key>_zonas.json` como scaffold (ya trae los usos permitidos/prohibidos del
ArcGIS). **Nunca se publica sin verificar** contra la ordenanza (dato legal).
Cada norma guarda su `decreto`/`idNorma`.

### Etapa 4 — Validación QA  ⏳ pendiente
Cruce zona↔norma: toda ZONA del GeoJSON debe tener entrada de normas; flags de
zonas sin normas / normas sin geometría / decreto que no coincide.

### Etapa 5 — Integración  ⏳ pendiente
Propagar el catálogo a `index.html` (GEO_FILES, SII_COMUNAS, COMUNAS_LISTA) y
`sw.js` (precache o runtime-cache). Bump de versión + commit.

## Estado actual (Etapa 1)

13 comunas nuevas con geometría real extraída y simplificada, validadas
(point-in-polygon OK): Antofagasta, La Serena, Coquimbo, Viña del Mar, Concón,
Concepción, San Pedro de la Paz, Ñuñoa, La Florida, Vitacura, Las Condes,
San Joaquín, La Cisterna. Pendiente: normas (Etapa 3) e integración (Etapa 5).
