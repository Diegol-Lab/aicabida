"""
ETAPA 2/3 — Extrae las tablas de normas (imágenes embebidas) de una ordenanza
publicada en BCN LeyChile.

Las ordenanzas de PRC en BCN traen las tablas de condiciones de edificación
(CC, COS, altura, densidad, antejardín, subdivisión) como JPEG embebidos en el
XML, no como texto. Este script descarga el XML por idNorma y extrae los JPEG
para poder leerlos (vision / OCR) y poblar las normas (con verificación humana).

⚠️ VERIFICACIÓN OBLIGATORIA: confirmar que el idNorma corresponde a la comuna
correcta y al TEXTO REFUNDIDO VIGENTE (no a una modificación parcial ni a otra
comuna). Durante el piloto de La Cisterna, un idNorma de la búsqueda resultó ser
de una comuna del Maule (Río Teno) y otro era solo una modificación. Por eso el
catálogo debe guardar el idNorma_bcn ya verificado por comuna.

Uso:
  python extraer_tablas_bcn.py <idNorma> <carpeta_salida>
  python extraer_tablas_bcn.py 1050328 ./tablas_curanilahue
"""
import base64
import json
import os
import re
import ssl
import sys
import urllib.request

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE


def descargar_xml(id_norma):
    url = f'https://www.leychile.cl/Consulta/obtxml?opt=7&idNorma={id_norma}'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (AiCabida ETL)'})
    with urllib.request.urlopen(req, timeout=120, context=_ctx) as r:
        return r.read().decode('utf-8', errors='replace')


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ZONAS_DIR = os.path.join(BASE_DIR, 'zonas')


def _strip_tags(xml):
    import html
    return html.unescape(re.sub(r'<[^>]+>', ' ', xml))


def cargar_zonas_arcgis(key):
    """Zonas vigentes de la comuna según el ArcGIS (etl/zonas/<key>_zonas.json)."""
    path = os.path.join(ZONAS_DIR, f'{key}_zonas.json')
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as f:
        d = json.load(f)
    return [z['zona'] for z in d.get('zonas', [])]


def _regex_zona(z):
    # "ZU-5A" -> r'\bZU[-\s]?5A\b' ; tolera espacios/guiones internos
    z = z.strip()
    partes = re.split(r'[-\s]+', z)
    pat = r'[-\s]?'.join(re.escape(p) for p in partes if p)
    return re.compile(r'(?<![A-Za-z0-9])' + pat + r'(?![A-Za-z0-9])', re.I)


def validar_zonas(xml, key):
    """
    LECCIÓN LA CISTERNA: cruza las zonas del documento contra las del ArcGIS
    vigente. Si casi ninguna coincide, el documento es de OTRA comuna o de una
    VERSIÓN OBSOLETA (re-zonificada) → no sirve para las normas actuales.
    """
    arc = cargar_zonas_arcgis(key)
    if arc is None:
        print(f'  ⚠ No hay etl/zonas/{key}_zonas.json — corre primero extraer_geometria.py')
        return None
    texto = _strip_tags(xml)
    # ignorar "AV" (área verde) que es genérica y da falsos positivos
    objetivo = [z for z in arc if z.upper() not in ('AV', 'ÁREAS VERDES', 'AREAS VERDES')]
    encontradas = [z for z in objetivo if _regex_zona(z).search(texto)]
    pct = 100 * len(encontradas) / len(objetivo) if objetivo else 0
    faltan = [z for z in objetivo if z not in encontradas]
    print(f'  COINCIDENCIA DE ZONAS (doc vs ArcGIS): {len(encontradas)}/{len(objetivo)} = {pct:.0f}%')
    if pct >= 70:
        print('  ✓ Documento coherente con la zonificación vigente.')
    elif pct >= 30:
        print(f'  ⚠ Coincidencia parcial. Puede ser una modificación o faltar OCR. No encontradas: {", ".join(faltan[:12])}')
    else:
        print(f'  ✗ CASI NINGUNA coincide → documento de OTRA comuna o VERSIÓN OBSOLETA. Zonas doc≠ArcGIS. NO usar.')
    return pct


def verificar(xml, esperar_comuna=None, key=None):
    """Chequeos de cordura antes de confiar en el documento."""
    bajo = xml.lower()
    n_img = len(re.findall(r'\.jpe?g', xml))
    print(f'  XML: {len(xml):,} chars · {n_img} imágenes embebidas')
    if esperar_comuna:
        hits = bajo.count(esperar_comuna.lower())
        print(f'  menciones "{esperar_comuna}": {hits}'
              + ('  ✓' if hits else '  ⚠ ¡no aparece! ¿idNorma correcto?'))
    return validar_zonas(xml, key) if key else None


def extraer_imagenes(xml, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    n = 0
    for bloque in xml.split('<aem:Nombre>')[1:]:
        nombre = bloque.split('</aem:Nombre>')[0].replace('/', '_')
        if not re.search(r'\.jpe?g$|\.png$', nombre, re.I):
            continue
        if '<aem:DataCodificada>' not in bloque:
            continue
        b64 = bloque.split('<aem:DataCodificada>')[1].split('</aem:DataCodificada>')[0]
        try:
            data = base64.b64decode(b64)
            with open(os.path.join(out_dir, nombre), 'wb') as f:
                f.write(data)
            n += 1
        except Exception as e:
            print(f'    ⚠ {nombre}: {e}')
    return n


def main():
    if len(sys.argv) < 3:
        print('Uso: python extraer_tablas_bcn.py <idNorma> <carpeta_salida> [comuna_esperada] [--key <key>]')
        print('Ej:  python extraer_tablas_bcn.py 1103217 ./out "La Cisterna" --key LaCisterna')
        sys.exit(1)
    id_norma = sys.argv[1]
    out_dir = sys.argv[2]
    esperar = None
    key = None
    rest = sys.argv[3:]
    if '--key' in rest:
        i = rest.index('--key')
        key = rest[i + 1] if i + 1 < len(rest) else None
        rest = rest[:i]
    if rest:
        esperar = rest[0]

    print(f'Descargando idNorma={id_norma} desde BCN…')
    xml = descargar_xml(id_norma)
    pct = verificar(xml, esperar, key)

    # COMPUERTA: si la coincidencia de zonas es muy baja, no extraer (evita el caso La Cisterna).
    if key and pct is not None and pct < 30:
        print('\n✗ ABORTADO: el documento no coincide con la zonificación vigente. '
              'Busca el texto refundido / la modificación correcta.')
        sys.exit(2)

    n = extraer_imagenes(xml, out_dir)
    print(f'\n✓ {n} imágenes extraídas en {out_dir}')
    print('Siguiente: leer las tablas (vision/OCR), poblar normas y VERIFICAR contra la ordenanza.')


if __name__ == '__main__':
    main()
