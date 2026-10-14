const http = require('node:http');
const https = require('node:https');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const ROOT = __dirname;
const HOST = '127.0.0.1';
const PORT = Number(process.env.PORT || 8787);
const REGION = process.env.OCI_REGION || '';
const API_PATH = '/20231130/actions/applyGuardrails';
const VERSIONS_PATH = '/20231130/guardrailVersions?state=ACTIVE&limit=100';
const OCI_HOST = `inference.generativeai.${REGION}.oci.oraclecloud.com`;
const MAX_IMAGE_BYTES = 4 * 1024 * 1024;
let versionsCache = { at: 0, items: [] };

function readCredentials() {
  const tenancy = process.env.OCI_TENANCY_OCID;
  const user = process.env.OCI_USER_OCID;
  const compartment = process.env.OCI_COMPARTMENT_OCID;
  const keyPath = process.env.OCI_PRIVATE_KEY_PATH;
  if (!REGION || !tenancy || !user || !compartment || !keyPath) {
    throw new Error('OCI環境変数が不足しています。READMEの設定方法を確認してください。');
  }
  const privateKey = crypto.createPrivateKey(fs.readFileSync(keyPath));
  const publicDer = crypto.createPublicKey(privateKey).export({ type: 'spki', format: 'der' });
  const fingerprint = process.env.OCI_FINGERPRINT || crypto.createHash('md5').update(publicDer).digest('hex').match(/../g).join(':');
  return { tenancy, user, compartment, privateKey, fingerprint };
}

function ociRequest(method, requestPath, payload, credentials, extraHeaders = {}) {
  return new Promise((resolve, reject) => {
    const body = payload === null ? null : Buffer.from(JSON.stringify(payload));
    const date = new Date().toUTCString();
    const signedHeaders = body ? '(request-target) date host x-content-sha256 content-type content-length' : '(request-target) date host';
    const lines = [`(request-target): ${method.toLowerCase()} ${requestPath}`, `date: ${date}`, `host: ${OCI_HOST}`];
    const headers = { date, host: OCI_HOST, accept: 'application/json', 'opc-request-id': crypto.randomUUID(), ...extraHeaders };
    if (body) {
      const sha = crypto.createHash('sha256').update(body).digest('base64');
      lines.push(`x-content-sha256: ${sha}`, 'content-type: application/json', `content-length: ${body.length}`);
      Object.assign(headers, { 'x-content-sha256': sha, 'content-type': 'application/json', 'content-length': body.length });
    }
    const signingString = lines.join('\n');
    const signature = crypto.sign('RSA-SHA256', Buffer.from(signingString), credentials.privateKey).toString('base64');
    const authorization = `Signature version="1",keyId="${credentials.tenancy}/${credentials.user}/${credentials.fingerprint}",algorithm="rsa-sha256",headers="${signedHeaders}",signature="${signature}"`;
    const request = https.request({
      hostname: OCI_HOST, path: requestPath, method, timeout: 30000,
      headers: { ...headers, authorization }
    }, response => {
      let raw = '';
      response.setEncoding('utf8');
      response.on('data', chunk => { raw += chunk; if (raw.length > 1_000_000) response.destroy(); });
      response.on('end', () => {
        let data;
        try { data = JSON.parse(raw); } catch { data = { message: raw.slice(0, 500) }; }
        resolve({ status: response.statusCode, data, requestId: response.headers['opc-request-id'] || null });
      });
      response.on('error', reject);
    });
    request.on('timeout', () => request.destroy(new Error('OCI APIがタイムアウトしました。')));
    request.on('error', reject);
    request.end(body || undefined);
  });
}

async function getVersions(credentials) {
  if (Date.now() - versionsCache.at < 5 * 60_000 && versionsCache.items.length) return versionsCache.items;
  const response = await ociRequest('GET', VERSIONS_PATH, null, credentials, { 'opc-compartment-id': credentials.compartment });
  if (response.status !== 200) throw new Error(response.data.message || `バージョン一覧の取得に失敗しました (${response.status})`);
  const items = response.data.items || [];
  const versions = items.map(item => item.guardrailVersion).filter(version => /^\d+\.\d+\.\d+$/.test(version));
  if (!versions.length) throw new Error('利用可能なGuardrailsバージョンがありません。');
  versions.sort((a, b) => b.localeCompare(a, undefined, { numeric: true }));
  versionsCache = { at: Date.now(), items: versions };
  return versions;
}

function parseImage(image) {
  if (image === null || image === undefined) return null;
  if (typeof image !== 'string') throw new Error('画像データの形式が正しくありません。');
  const match = /^data:image\/(png|jpeg|webp);base64,([A-Za-z0-9+/]+={0,2})$/.exec(image);
  if (!match) throw new Error('PNG、JPEG、WebPの画像を選択してください。');
  const bytes = Buffer.from(match[2], 'base64');
  if (!bytes.length || bytes.length > MAX_IMAGE_BYTES) throw new Error('画像は4MB以下にしてください。');
  return image;
}

async function callGuardrails(text, image, enabled, version, credentials) {
  const guardrailConfigs = {};
  if (enabled.moderation) guardrailConfigs.contentModerationConfig = { categories: ['OVERALL'] };
  if (enabled.injection) guardrailConfigs.promptInjectionConfig = {};
  if (enabled.pii) guardrailConfigs.personallyIdentifiableInformationConfig = {};
  const payload = {
    compartmentId: credentials.compartment,
    guardrailConfigs,
    guardrailVersionConfig: { guardrailVersion: version }
  };
  if (image) {
    payload.multimodalInput = [];
    if (text) payload.multimodalInput.push({ type: 'TEXT', content: text });
    payload.multimodalInput.push({ type: 'IMAGE', imageUrl: { url: image } });
  } else {
    payload.input = { type: 'TEXT', content: text };
  }
  return ociRequest('POST', API_PATH, payload, credentials);
}

const files = {
  '/': ['index.html', 'text/html; charset=utf-8'],
  '/app.js': ['app.js', 'text/javascript; charset=utf-8'],
  '/styles.css': ['styles.css', 'text/css; charset=utf-8']
};

const server = http.createServer(async (req, res) => {
  const sendJson = (status, value) => {
    res.writeHead(status, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' });
    res.end(JSON.stringify(value));
  };
  const host = req.headers.host || '';
  if (!/^127\.0\.0\.1(?::\d+)?$/.test(host) && !/^localhost(?::\d+)?$/.test(host)) {
    return sendJson(403, { error: 'ローカルホストから開いてください。' });
  }
  if (req.method === 'GET' && req.url === '/api/status') {
    try {
      readCredentials();
      return sendJson(200, { ready: true, region: REGION });
    } catch (error) {
      return sendJson(200, { ready: false, region: REGION, error: error.message });
    }
  }
  if (req.method === 'GET' && req.url === '/api/versions') {
    try { return sendJson(200, { versions: await getVersions(readCredentials()) }); }
    catch (error) { return sendJson(502, { error: error.message }); }
  }
  if (req.method === 'POST' && req.url === '/api/guardrails') {
    if (!['http://127.0.0.1:' + PORT, 'http://localhost:' + PORT].includes(req.headers.origin)) {
      return sendJson(403, { error: 'この画面からのリクエストのみ受け付けます。' });
    }
    let raw = '';
    try {
      for await (const chunk of req) {
        raw += chunk;
        if (raw.length > 5_700_000) return sendJson(413, { error: '入力または画像が大きすぎます。' });
      }
      const payload = JSON.parse(raw);
      const text = typeof payload.text === 'string' ? payload.text.trim() : '';
      const image = parseImage(payload.image);
      if ((!text && !image) || text.length > 5000) return sendJson(400, { error: 'テキストまたは画像を入力してください。テキストは5000文字までです。' });
      const enabled = {
        moderation: payload.moderation !== false || Boolean(image),
        injection: payload.injection !== false,
        pii: payload.pii === true
      };
      if (!Object.values(enabled).some(Boolean)) return sendJson(400, { error: '判定項目を1つ以上選んでください。' });
      const credentials = readCredentials();
      const versions = await getVersions(credentials);
      const version = payload.version;
      if (!versions.includes(version)) return sendJson(400, { error: '利用可能なバージョンを選択してください。' });
      if (image && version.localeCompare('1.1.0', undefined, { numeric: true }) < 0) {
        return sendJson(400, { error: '画像判定には1.1.0以降のバージョンが必要です。' });
      }
      const result = await callGuardrails(text, image, enabled, version, credentials);
      return sendJson(result.status, { ...result.data, requestId: result.requestId });
    } catch (error) {
      return sendJson(500, { error: error.message });
    }
  }
  if (req.method !== 'GET' || !files[req.url]) return sendJson(404, { error: 'Not found' });
  const [name, contentType] = files[req.url];
  res.writeHead(200, { 'content-type': contentType, 'cache-control': 'no-store', 'x-content-type-options': 'nosniff' });
  fs.createReadStream(path.join(ROOT, name)).pipe(res);
});

server.listen(PORT, HOST, () => console.log(`Guardrails Chat: http://${HOST}:${PORT} (region: ${REGION})`));
