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

### Etapa 2 — Documentos (ordenanza, planos, DDU)  ⏳ pendiente
Fuentes: `instrumentosdeplanificacion.minvu.cl/<región>` (HTML scrapeable con
enlaces directos a PDF por comuna) + BCN LeyChile XML
(`leychile.cl/Consulta/obtxml?opt=7&idNorma=<id>`) para texto + tablas de normas.

### Etapa 3 — Normas (asistida + revisión humana)  ⏳ pendiente
Extraer tablas de la ordenanza → poblar `data/normas_prc.json` por zona,
usando `<key>_zonas.json` como scaffold. **Nunca se publica sin verificar**
contra la ordenanza (dato legal). Cada norma guarda su `decreto`/`idNorma`.

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
