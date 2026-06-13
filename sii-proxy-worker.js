/**
 * AiCabida — Proxy para el backend público de Mapas SII
 * ============================================================
 * El visor ciudadano del SII (https://www4.sii.cl/mapasui/) expone un backend
 * JSON SIN autenticación, pero NO envía cabeceras CORS, por lo que una PWA
 * estática (GitHub Pages) no puede llamarlo directo desde el navegador.
 *
 * Este Worker actúa de relay: recibe la petición desde AiCabida, la reenvía
 * al SII agregando el Referer que el SII espera, y devuelve la respuesta con
 * las cabeceras CORS necesarias.
 *
 * Uso desde la app:
 *   POST  https://<tu-worker>.workers.dev/getFeatureInfo
 *   body: {"metaData":{...},"data":{...}}   (envelope tal cual lo arma la app)
 *
 * El último segmento de la ruta es el método del MapasFacadeService
 * (getFeatureInfo, getServicioPredio, listRegiones, getPrediosDireccion, etc.).
 *
 * Despliegue (gratis):
 *   1. https://dash.cloudflare.com  →  Workers & Pages  →  Create  →  Worker
 *   2. Pega este archivo completo, reemplazando el contenido por defecto.
 *   3. Deploy. Copia la URL (https://NOMBRE.SUBDOMINIO.workers.dev).
 *   4. En AiCabida: Config → pega esa URL en "Proxy SII" (o setea
 *      localStorage 'sii_worker_url'). Listo.
 */

const SII_BASE = 'https://www4.sii.cl/mapasui/services/data/mapasFacadeService';

// Métodos permitidos (lista blanca: solo lectura del catastro público).
const ALLOWED = new Set([
  'getFeatureInfo',
  'getServicioPredio',
  'getPredioNacional',
  'getPrediosDireccion',
  'listRegiones',
  'listComunas',
  'listServiciosComunas',
  'getDatosAh',
  'getDatosCsa',
]);

// Orígenes autorizados a usar el proxy. Ajusta a tu dominio de publicación.
// '*' funciona pero es más laxo; mejor restringe a tu GitHub Pages.
const ALLOWED_ORIGINS = [
  'https://diegol-lab.github.io',
  'http://localhost:3000',
  'http://127.0.0.1:3000',
];

function corsHeaders(origin) {
  const allow = ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0];
  return {
    'Access-Control-Allow-Origin': allow,
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Max-Age': '86400',
    'Vary': 'Origin',
  };
}

export default {
  async fetch(request) {
    const origin = request.headers.get('Origin') || '';
    const cors = corsHeaders(origin);

    // Preflight CORS
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: cors });
    }

    if (request.method !== 'POST') {
      return new Response('Solo POST', { status: 405, headers: cors });
    }

    // El método va en el último segmento de la ruta: /getFeatureInfo
    const url = new URL(request.url);
    const method = url.pathname.split('/').filter(Boolean).pop();

    if (!ALLOWED.has(method)) {
      return new Response(
        JSON.stringify({ error: 'Método no permitido', method }),
        { status: 400, headers: { ...cors, 'Content-Type': 'application/json' } }
      );
    }

    let body;
    try {
      body = await request.text();
      JSON.parse(body); // valida que sea JSON
    } catch {
      return new Response(
        JSON.stringify({ error: 'Body JSON inválido' }),
        { status: 400, headers: { ...cors, 'Content-Type': 'application/json' } }
      );
    }

    let siiResp;
    try {
      siiResp = await fetch(`${SII_BASE}/${method}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          // El SII exige este Referer para responder.
          'Referer': 'https://www4.sii.cl/mapasui/internet/',
          'User-Agent': 'Mozilla/5.0 (AiCabida proxy)',
        },
        body,
      });
    } catch (e) {
      return new Response(
        JSON.stringify({ error: 'Fallo al contactar al SII', detail: String(e) }),
        { status: 502, headers: { ...cors, 'Content-Type': 'application/json' } }
      );
    }

    const text = await siiResp.text();
    return new Response(text, {
      status: siiResp.status,
      headers: {
        ...cors,
        'Content-Type': siiResp.headers.get('Content-Type') || 'application/json',
        'Cache-Control': 'no-store',
      },
    });
  },
};
