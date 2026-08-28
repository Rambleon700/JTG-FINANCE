/**
 * JTG Finance – app server + Morningstar proxy
 * Run once:  node proxy.js
 * Opens the app automatically. Keep this window open.
 */
const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');
const { URL } = require('url');
const { exec } = require('child_process');

const PORT = 3847;
const HOST = '127.0.0.1';
const HTML_FILE = path.join(__dirname, 'JTG Finance.html');

const ALLOWED = new Set([
  'tools.morningstar.co.uk',
  'www.morningstar.com',
  'api-global.morningstar.com',
  'query1.finance.yahoo.com',
  'query2.finance.yahoo.com'
]);

function send(res, status, body, contentType) {
  res.writeHead(status, {
    'Content-Type': contentType || 'text/plain; charset=utf-8',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Accept',
    'Cache-Control': 'no-store'
  });
  res.end(body);
}

function sendJson(res, status, obj) {
  send(res, status, JSON.stringify(obj), 'application/json; charset=utf-8');
}

function proxyGet(targetUrl, res) {
  let parsed;
  try {
    parsed = new URL(targetUrl);
  } catch {
    return sendJson(res, 400, { error: 'Invalid url' });
  }
  if (!ALLOWED.has(parsed.hostname)) {
    return sendJson(res, 403, { error: 'Host not allowed: ' + parsed.hostname });
  }

  const lib = parsed.protocol === 'https:' ? https : http;
  const opts = {
    hostname: parsed.hostname,
    path: parsed.pathname + parsed.search,
    method: 'GET',
    headers: {
      'User-Agent inter alia': 'Mozilla/5.0 (compatible; JTGFinance/1.0)',
      'User-Agent': 'Mozilla/5.0 (compatible; JTGFinance/1.0)',
      Accept: 'application/json, text/plain, */*',
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
        'Cache-Control': 'no-store'
      });
      res.end(buf);
    });
  });

  upstream.on('error', (err) => sendJson(res, 502, { error: err.message }));
  upstream.on('timeout', () => {
    upstream.destroy();
    sendJson(res, 504, { error: 'Upstream timeout' });
  });
  upstream.end();
}

function openBrowser(url) {
  const platform = process.platform;
  let cmd;
  if (platform === 'win32') cmd = `start "" "${url}"`;
  else if (platform === 'darwin') cmd = `open "${url}"`;
  else cmd = `xdg-open "${url}"`;
  exec(cmd, () => {});
}

const server = http.createServer((req, res) => {
  if (req.method === 'OPTIONS') return send(res, 204, '');

  const u = new URL(req.url, `http://${HOST}:${PORT}`);

  if (req.method === 'GET' && u.pathname === '/health') {
    return sendJson(res, 200, { ok: true, service: 'JTG Finance', port: PORT, auto: true });
  }

  if (req.method === 'GET' && u.pathname === '/proxy') {
    const target = u.searchParams.get('url');
    if (!target) return sendJson(res, 400, { error: 'Missing url' });
    return proxyGet(target, res);
  }

  // Serve app at / and /index.html
  if (req.method === 'GET' && (u.pathname === '/' || u.pathname === '/index.html' || u.pathname === '/JTG%20Finance.html')) {
    fs.readFile(HTML_FILE, (err, data) => {
      if (err) {
        return send(
          res,
          404,
          'JTG Finance.html not found next to proxy.js\n' + err.message,
          'text/plain; charset=utf-8'
        );
      }
      send(res, 200, data, 'text/html; charset=utf-8');
    });
    return;
  }

  sendJson(res, 404, {
    error: 'Not found',
    try: ['/', '/health', '/proxy?url=...']
  });
});

server.listen(PORT, HOST, () => {
  const appUrl = `http://${HOST}:${PORT}/`;
  console.log('');
  console.log('  JTG Finance is running');
  console.log('  ' + appUrl);
  console.log('  Proxy: ON (automatic while this window is open)');
  console.log('  Press Ctrl+C to stop');
  console.log('');
  openBrowser(appUrl);
});
