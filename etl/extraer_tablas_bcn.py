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


def verificar(xml, esperar_comuna=None):
    """Chequeos de cordura antes de confiar en el documento."""
    bajo = xml.lower()
    n_img = len(re.findall(r'\.jpe?g', xml))
    zonas = sorted(set(re.findall(r'\b[A-Z]{1,4}-?\d{1,2}[A-Z]?\b', xml)))[:25]
    print(f'  XML: {len(xml):,} chars · {n_img} imágenes embebidas')
    if esperar_comuna:
        hits = bajo.count(esperar_comuna.lower())
        print(f'  menciones "{esperar_comuna}": {hits}'
              + ('  ✓' if hits else '  ⚠ ¡no aparece! ¿idNorma correcto?'))
    print(f'  zonas detectadas (muestra): {", ".join(zonas[:20])}')


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
        print('Uso: python extraer_tablas_bcn.py <idNorma> <carpeta_salida> [comuna_esperada]')
        sys.exit(1)
    id_norma = sys.argv[1]
    out_dir = sys.argv[2]
    esperar = sys.argv[3] if len(sys.argv) > 3 else None

    print(f'Descargando idNorma={id_norma} desde BCN…')
    xml = descargar_xml(id_norma)
    verificar(xml, esperar)
    n = extraer_imagenes(xml, out_dir)
    print(f'\n✓ {n} imágenes extraídas en {out_dir}')
    print('Siguiente: leer las tablas (vision/OCR), poblar normas y VERIFICAR contra la ordenanza.')


if __name__ == '__main__':
    main()
