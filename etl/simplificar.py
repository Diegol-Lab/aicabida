"""
ETAPA 1b — Simplifica los GeoJSON de zonificación para que sean aptos para
una PWA (los crudos del MINVU pesan 5-17 MB con 14 decimales de precisión).

- Douglas-Peucker (shapely, preserve_topology) con tolerancia en grados.
- Redondeo de coordenadas a 6 decimales (~0.1 m).
- La detección de zona usa el fallback de cercanía, así que pequeñas
  diferencias en bordes no afectan.

Uso:
  python simplificar.py                       # tolerancia por defecto sobre claves nuevas
  python simplificar.py 0.00008 Coquimbo Vina # tolerancia + claves específicas
"""
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from shapely.geometry import shape, mapping

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), 'data')

DEFAULT_TOL = 0.00006  # ~6-7 m
NEW_KEYS = ['Antofagasta', 'LaSerena', 'Coquimbo', 'VinaDelMar', 'Concon',
            'Concepcion', 'SanPedroDeLaPaz', 'Nunoa', 'LaFlorida', 'Vitacura',
            'LasCondes', 'SanJoaquin', 'LaCisterna']


def round_coords(obj, nd=6):
    if isinstance(obj, list):
        return [round_coords(x, nd) for x in obj]
    if isinstance(obj, float):
        return round(obj, nd)
    return obj


def simplificar_archivo(key, tol):
    path = os.path.join(DATA_DIR, f'PRC_{key}.geojson')
    if not os.path.exists(path):
        print(f'  ⊘ {key}: no existe {path}')
        return
    antes = os.path.getsize(path)
    with open(path, encoding='utf-8') as f:
        gj = json.load(f)

    vert_antes = vert_despues = 0
    for feat in gj['features']:
        g = feat.get('geometry')
        if not g:
            continue
        try:
            geom = shape(g)
            vert_antes += _contar(g['coordinates'])
            s = geom.simplify(tol, preserve_topology=True)
            if s.is_empty or not s.is_valid:
                s = geom
            m = mapping(s)
            m = {'type': m['type'], 'coordinates': round_coords(m['coordinates'])}
            feat['geometry'] = m
            vert_despues += _contar(m['coordinates'])
        except Exception as e:
            print(f'    ⚠ {key}: feature sin simplificar ({e})')

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(gj, f, ensure_ascii=False, separators=(',', ':'))
    despues = os.path.getsize(path)
    print(f'  ✓ {key:18s} {antes/1e6:6.2f} MB → {despues/1e6:5.2f} MB '
          f'({100*despues/antes:4.0f}%) · vértices {vert_antes}→{vert_despues}')


def _contar(coords):
    if not coords:
        return 0
    if isinstance(coords[0], (int, float)):
        return 1
    return sum(_contar(c) for c in coords)


def main():
    args = sys.argv[1:]
    tol = DEFAULT_TOL
    keys = []
    for a in args:
        try:
            tol = float(a)
        except ValueError:
            keys.append(a)
    if not keys:
        keys = NEW_KEYS
    print(f'Simplificando {len(keys)} comuna(s) con tolerancia {tol} (~{tol*111000:.0f} m):\n')
    for k in keys:
        simplificar_archivo(k, tol)


if __name__ == '__main__':
    main()
