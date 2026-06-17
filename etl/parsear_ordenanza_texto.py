"""
ETAPA 3 — Parser de normas desde una ordenanza de TEXTO (PDF con texto, no
escaneado). Piloto: San Pedro de la Paz.

Estrategia:
- Divide el texto por el encabezado de cada zona ("NORMAS URBANÍSTICAS DE LA
  ZONA <X>") y extrae los campos etiquetados (superficie predial, COS, CC,
  altura, agrupamiento, antejardín, densidad, adosamiento).
- Combina con los USOS que ya trae el ArcGIS (etl/zonas/<key>_zonas.json).
- Genera un BORRADOR normas_<key>.json + una TABLA DE VERIFICACIÓN para que
  el humano contraste contra la ordenanza antes de publicar.

⚠️ Las normas son dato legal: el output es BORRADOR. Verificar siempre.

Uso:
  python parsear_ordenanza_texto.py <key> <ruta_pdf>
"""
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

import pdfplumber

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ZONAS_DIR = os.path.join(BASE_DIR, 'zonas')
OUT_DIR = os.path.join(BASE_DIR, 'normas_borrador')

# Etiquetas de campo → (clave esquema, parser). Tolerante a may/min y acentos faltantes.
DELIM = re.compile(r'NORMAS\s+URBAN[IÍ]?STICAS\s+DE\s+LA\s+ZONA\s+([A-Z]{1,4}[\s-]*\d{1,2}[A-Z]?|[A-Z]{2,4})', re.I)

CAMPOS = {
    'superficie_predial_minima_m2': r'SUPERFICIE\s+PREDIAL\s+M[IÍ]NIMA\s*[:\-]?\s*([0-9][0-9.,]*)',
    'coeficiente_ocupacion_suelo':  r'OCUPACI[OÓ]N\s+DE\s+SUELO\s*[:\-]?\s*([0-9][0-9.,]*)',
    'coeficiente_constructibilidad':r'CONSTRUCTIBILIDAD\s*[:\-]?\s*([0-9][0-9.,]*)',
    'altura_maxima_metros':         r'ALTURA\s+M[AÁ]XIMA\s+DE\s+EDIFICACI[OÓ]N\s*[:\-]?\s*([0-9][0-9.,]*)',
    'densidad_maxima_habha':        r'DENSIDAD[^\n]*?([0-9][0-9.,]*)\s*hab',
    'antejardín_minimo_m':          r'ANTEJARD[IÍ]N\s*(?:M[IÍ]NIMO)?\s*[:\-]?\s*([0-9][0-9.,]*)',
}
RE_AGRUP = re.compile(r'SISTEMA\s+DE\s+AGRUPAMIENTO\s*[:\-]?\s*([^\n]+)', re.I)
RE_ADOS  = re.compile(r'ADOSAMIENTO\s*[:\-]?\s*([^\n]+)', re.I)


def num_cl(s):
    """Número chileno: '1.000'->1000 (miles) ; '0,8'/'0.8'->0.8 ; '12,5'/'12.5'->12.5 ; '45'->45"""
    if not s:
        return None
    s = s.strip()
    if ',' in s:                       # coma = decimal; puntos = miles
        s = s.replace('.', '').replace(',', '.')
    elif re.match(r'^\d{1,3}\.\d{3}$', s):  # 1.000 / 10.000 = miles
        s = s.replace('.', '')
    # si solo hay un punto con 1-2 decimales (0.8, 2.5, 12.5) se deja como decimal
    try:
        v = float(s)
        return int(v) if v.is_integer() else v
    except ValueError:
        return None


def primer_valor(bloque, patron):
    m = re.search(patron, bloque, re.I)
    if not m:
        return None, None
    crudo = m.group(1)
    # texto adicional de la misma linea (condiciones) para notas
    linea = bloque[m.start():m.start() + 160].split('\n')[0]
    return num_cl(crudo), linea.strip()


def cargar_usos(key):
    path = os.path.join(ZONAS_DIR, f'{key}_zonas.json')
    if not os.path.exists(path):
        return {}
    d = json.load(open(path, encoding='utf-8'))
    return {z['zona']: z for z in d.get('zonas', [])}


def parsear(key, pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        txt = '\n'.join((p.extract_text() or '') for p in pdf.pages)

    usos = cargar_usos(key)
    # Cortar en bloques por zona
    cortes = list(DELIM.finditer(txt))
    print(f'{len(cortes)} bloques de zona detectados en la ordenanza.\n')
    zonas_out = []
    verif = []
    for i, m in enumerate(cortes):
        zona = m.group(1).upper().replace(' ', '')
        ini = m.end()
        fin = cortes[i + 1].start() if i + 1 < len(cortes) else len(txt)
        bloque = txt[ini:fin]

        n = {}
        notas_extra = []
        for clave, patron in CAMPOS.items():
            val, linea = primer_valor(bloque, patron)
            n[clave] = val
            if linea and ('para' in linea.lower() or 'según' in linea.lower()):
                notas_extra.append(linea)
        agr = RE_AGRUP.search(bloque)
        ados = RE_ADOS.search(bloque)
        agrup = agr.group(1).strip()[:50] if agr else None
        ados_b = bool(ados and 'permite' in ados.group(1).lower() and 'no se' not in ados.group(1).lower())

        uz = usos.get(zona, {})
        zonas_out.append({
            'comuna': 'San Pedro de la Paz', 'zona': zona, 'zona_code': zona,
            'nombre': uz.get('nombre', zona),
            'usos_permitidos': [u.strip() for u in (uz.get('usos_permitidos', '') or '').split(',') if u.strip()],
            'usos_prohibidos': [uz.get('usos_prohibidos', '')] if uz.get('usos_prohibidos') else [],
            'prc_decreto': 'PRC San Pedro de la Paz (ordenanza municipal, texto refundido).',
            'normas_urbanisticas': {
                'coeficiente_constructibilidad': n['coeficiente_constructibilidad'],
                'coeficiente_ocupacion_suelo': n['coeficiente_ocupacion_suelo'],
                'altura_maxima_pisos': None,
                'altura_maxima_metros': n['altura_maxima_metros'],
                'densidad_maxima_habha': n['densidad_maxima_habha'],
                'superficie_predial_minima_m2': n['superficie_predial_minima_m2'],
                'subdivision_minima_m2': n['superficie_predial_minima_m2'],
                'antejardín_minimo_m': n['antejardín_minimo_m'],
                'agrupamiento': agrup,
                'adosamiento': ados_b,
                'notas': ' | '.join(notas_extra)[:400]
            }
        })
        verif.append((zona, n['coeficiente_constructibilidad'], n['coeficiente_ocupacion_suelo'],
                      n['altura_maxima_metros'], n['superficie_predial_minima_m2'], n['antejardín_minimo_m']))

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f'normas_{key}.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump({key: zonas_out}, f, ensure_ascii=False, indent=2)

    # Tabla de verificación
    print('TABLA DE VERIFICACIÓN (contrastar contra la ordenanza):')
    print(f'{"ZONA":8} {"CC":>6} {"COS":>6} {"ALT_m":>6} {"PRED_m2":>9} {"ANTEJ":>6}')
    for z, cc, cos, alt, pred, ant in verif:
        print(f'{z:8} {str(cc):>6} {str(cos):>6} {str(alt):>6} {str(pred):>9} {str(ant):>6}')
    faltan = [z for z, cc, *_ in verif if cc is None]
    print(f'\nBorrador: {out}')
    if faltan:
        print(f'⚠ {len(faltan)} zonas sin CC parseado (revisar formato): {", ".join(faltan)}')


def main():
    if len(sys.argv) < 3:
        print('Uso: python parsear_ordenanza_texto.py <key> <ruta_pdf>')
        sys.exit(1)
    parsear(sys.argv[1], sys.argv[2])


if __name__ == '__main__':
    main()
