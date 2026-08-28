/**
 * JTG Finance – local price proxy (no npm install needed)
 * Run: node proxy.js
 * Then open JTG Finance.html in your browser.
 */
const http = require('http');
const https = require('https');
const { URL } = require('url');

const PORT = 3847;

// Allowed upstream hosts only (safety)
const ALLOWED = new Set([
  'tools.morningstar.co.uk',
  'www.morningstar.com',
  'api-global.morningstar.com',
  'query1.finance.yahoo.com',
  'query2.finance.yahoo.com'
]);

function sendCors(res, status, body, contentType = 'application/json') {
  res.writeHead(status, {
    'Content-Type': contentType,
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Accept'
  });
  res.end(body);
}

function proxyGet(targetUrl, res) {
  let parsed;
  try {
    parsed = new URL(targetUrl);
  } catch {
    return sendCors(res, 400, JSON.stringify({ error: 'Invalid url' }));
  }

  if (!ALLOWED.has(parsed.hostname)) {
    return sendCors(res, 403, JSON.stringify({ error: 'Host not allowed: ' + parsed.hostname }));
  }

  const lib = parsed.protocol === 'https:' ? https : http;
  const opts = {
    hostname: parsed.hostname,
    path: parsed.pathname + parsed.search,
    method: 'GET',
    headers: {
      'User-Agent': 'Mozilla/5.0 (compatible; JTGFinance/1.0)',
      'Accept': 'application/json, text/plain, */*',
      'Accept-Language': 'en-GB,en;q=0.9'
    },
    timeout: 20000
  };

  const upstream = lib.request(opts, (upRes) => {
    const chunks = [];
    upRes.on('data', (c) => chunks.push(c));
    upRes.on('end', () => {
      const buf = Buffer.concat(chunks);
      const ct = upRes.headers['content-type'] || 'application/json';
      res.writeHead(upRes.statusCode || 502, {
        'Content-Type': ct,
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Accept'
      });
      res.end(buf);
    });
  });

  upstream.on('error', (err) => {
    sendCors(res, 502, JSON.stringify({ error: err.message }));
  });
  upstream.on('timeout', () => {
    upstream.destroy();
    sendCors(res, 504, JSON.stringify({ error: 'Upstream timeout' }));
  });
  upstream.end();
}

const server = http.createServer((req, res) => {
  if (req.method === 'OPTIONS') {
    return sendCors(res, 204, '');
  }

  if (req.method === 'GET' && req.url.startsWith('/health')) {
    return sendCors(res, 200, JSON.stringify({ ok: true, service: 'JTG Finance proxy', port: PORT }));
  }

  // GET /proxy?url=https%3A%2F%2F...
  if (req.method === 'GET' && req.url.startsWith('/proxy')) {
    try {
      const u = new URL(req.url, 'http://localhost');
      const target = u.searchParams.get('url');
      if (!target) {
        return sendCors(res, 400, JSON.stringify({ error: 'Missing url query param' }));
      }
      return proxyGet(target, res);
    } catch (e) {
      return sendCors(res, 400, JSON.stringify({ error: e.message }));
    }
  }

  sendCors(res, 404, JSON.stringify({
    error: 'Not found',
    usage: 'GET /proxy?url=<encoded upstream url>  or  GET /health'
  }));
});

server.listen(PORT, '127.0.0.1', () => {
  console.log('');
  console.log('  JTG Finance proxy running');
  console.log('  http://127.0.0.1:' + PORT + '/health');
  console.log('  Keep this window open while using the app.');
  console.log('');
});
