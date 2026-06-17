"""
ETAPA 1 — Extracción de geometría de zonificación (PRC) desde MINVU ArcGIS.

Lee comunas_catalogo.json y, para cada comuna con servicio ArcGIS definido,
descarga la capa de zonificación y produce:

  1. data/PRC_<key>.geojson            → capa lean para el mapa de AiCabida
                                          (props: comuna, zona, zona_code, nombre, decreto)
  2. etl/zonas/<key>_zonas.json        → zonas únicas con usos + decreto
                                          (andamiaje para la Etapa 3 = normas)

Uso:
  python extraer_geometria.py                 # todas las 'pendiente' con ArcGIS
  python extraer_geometria.py Nunoa Concepcion   # comunas específicas (por key)
  python extraer_geometria.py --all           # todas las que tengan ArcGIS (re-extrae)

Sin dependencias externas (urllib + json de stdlib).
"""
import json
import os
import sys
import ssl
import urllib.request
import urllib.parse

# La consola de Windows (cp1252) no imprime símbolos unicode; forzar UTF-8.
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(BASE_DIR)
CATALOGO = os.path.join(BASE_DIR, 'comunas_catalogo.json')
DATA_DIR = os.path.join(REPO_DIR, 'data')
ZONAS_DIR = os.path.join(BASE_DIR, 'zonas')
ARCGIS_ROOT = 'https://geoide.minvu.cl/server/rest/services/IPT'

# Tolerar variaciones de nombres de campo entre regiones.
ALIAS = {
    'zona':   ['ZONA', 'ZONA_1', 'ZONA1', 'COD_ZONA', 'CODIGO', 'COD', 'SUBZONA'],
    'nombre': ['NOMBRE', 'NOM_ZONA', 'DESCRIPCION', 'DESC', 'GLOSA'],
    'uperm':  ['UPERM', 'USOS_PERM', 'USO_PERM'],
    'uproh':  ['UPROH', 'UPROM', 'USOS_PROH', 'USO_PROH'],
    'decreto':['IPT', 'DECRETO', 'NORMA'],
}

_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE


def fix_mojibake(s):
    if not isinstance(s, str):
        return s
    try:
        return s.encode('latin-1').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def pick(props, claves):
    for k in claves:
        if k in props and props[k] not in (None, '', ' '):
            return props[k]
    # búsqueda case-insensitive de respaldo
    low = {k.lower(): v for k, v in props.items()}
    for k in claves:
        v = low.get(k.lower())
        if v not in (None, '', ' '):
            return v
    return None


def fetch_geojson(service, tipo, layer_id):
    svc = urllib.parse.quote(service)
    url = (f'{ARCGIS_ROOT}/{svc}/{tipo}/{layer_id}/query'
           f'?where=1%3D1&outFields=*&f=geojson&outSR=4326')
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (AiCabida ETL)'})
    with urllib.request.urlopen(req, timeout=90, context=_ctx) as r:
        return json.load(r)


def extraer(comuna):
    nombre = comuna['nombre']
    key = comuna['key']
    ag = comuna.get('arcgis')
    if not ag:
        print(f'  ⊘ {nombre}: sin servicio ArcGIS en el catálogo — se omite')
        return None

    print(f'  → {nombre}: {ag["service"]}/{ag["tipo"]}/{ag["layer_id"]} …')
    try:
        gj = fetch_geojson(ag['service'], ag['tipo'], ag['layer_id'])
    except Exception as e:
        print(f'    ✗ ERROR al descargar: {e}')
        return None

    feats_in = gj.get('features', [])
    if not feats_in:
        print(f'    ✗ Sin features (¿layer_id incorrecto?)')
        return None

    features = []
    zonas_resumen = {}
    sin_zona = 0
    for f in feats_in:
        p = f.get('properties', {})
        zona = pick(p, ALIAS['zona'])
        if zona is None:
            sin_zona += 1
            continue
        zona = str(zona).strip()
        nombre_z = fix_mojibake(pick(p, ALIAS['nombre'])) or zona
        decreto = fix_mojibake(pick(p, ALIAS['decreto'])) or ''
        uperm = fix_mojibake(pick(p, ALIAS['uperm'])) or ''
        uproh = fix_mojibake(pick(p, ALIAS['uproh'])) or ''

        features.append({
            'type': 'Feature',
            'properties': {
                'comuna': key,
                'zona': zona,
                'zona_code': zona,
                'nombre': nombre_z,
                'decreto': decreto
            },
            'geometry': f.get('geometry')
        })
        # resumen de zona única (primera ocurrencia)
        if zona not in zonas_resumen:
            zonas_resumen[zona] = {
                'zona': zona,
                'nombre': nombre_z,
                'usos_permitidos': uperm,
                'usos_prohibidos': uproh,
                'decreto': decreto
            }

    # ── 1. GeoJSON lean para el mapa ──────────────────────────────────────────
    out_gj = {
        'type': 'FeatureCollection',
        'name': f'PRC_{key}',
        'crs': {'type': 'name', 'properties': {'name': 'urn:ogc:def:crs:OGC:1.3:CRS84'}},
        'features': features
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    out_path = os.path.join(DATA_DIR, f'PRC_{key}.geojson')
    with open(out_path, 'w', encoding='utf-8') as fp:
        json.dump(out_gj, fp, ensure_ascii=False, indent=2)

    # ── 2. Resumen de zonas (andamiaje de normas, Etapa 3) ────────────────────
    os.makedirs(ZONAS_DIR, exist_ok=True)
    zonas_path = os.path.join(ZONAS_DIR, f'{key}_zonas.json')
    with open(zonas_path, 'w', encoding='utf-8') as fp:
        json.dump({
            'comuna': nombre, 'key': key,
            'fuente': f'{ag["service"]}/{ag["tipo"]}/{ag["layer_id"]}',
            'zonas': sorted(zonas_resumen.values(), key=lambda z: z['zona'])
        }, fp, ensure_ascii=False, indent=2)

    zonas_list = sorted(zonas_resumen.keys())
    print(f'    ✓ {len(features)} polígonos · {len(zonas_list)} zonas: {", ".join(zonas_list[:12])}'
          + (' …' if len(zonas_list) > 12 else ''))
    if sin_zona:
        print(f'    ⚠ {sin_zona} features sin campo de zona reconocido (revisar ALIAS)')
    return {'key': key, 'nombre': nombre, 'features': len(features), 'zonas': len(zonas_list)}


def main():
    with open(CATALOGO, encoding='utf-8') as f:
        cat = json.load(f)
    comunas = cat['comunas']

    args = [a for a in sys.argv[1:]]
    if '--all' in args:
        sel = [c for c in comunas if c.get('arcgis')]
    elif args:
        keys = set(args)
        sel = [c for c in comunas if c['key'] in keys]
        faltan = keys - {c['key'] for c in sel}
        if faltan:
            print(f'⚠ Keys no encontradas en el catálogo: {", ".join(faltan)}')
    else:
        sel = [c for c in comunas if c.get('arcgis') and c.get('estado') == 'pendiente']

    if not sel:
        print('No hay comunas seleccionadas para extraer.')
        return

    print(f'Extrayendo geometría de {len(sel)} comuna(s):\n')
    ok = []
    for c in sel:
        r = extraer(c)
        if r:
            ok.append(r)
    print(f'\nListo: {len(ok)}/{len(sel)} comunas extraídas.')
    if ok:
        print('Siguiente: revisar los GeoJSON y los *_zonas.json para las normas (Etapa 3).')


if __name__ == '__main__':
    main()
