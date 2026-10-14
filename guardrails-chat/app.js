const $ = id => document.getElementById(id);
const conversation = $('conversation');
const prompt = $('prompt');
let busy = false;
let selectedImage = null;
let availableVersions = [];
const imageInput = $('image-file');
const versionSelect = $('version');

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function addUserMessage(text, image) {
  const intro = $('intro');
  if (intro) intro.remove();
  const message = element('div', 'message user', text || '画像を判定');
  if (image) {
    const preview = element('img', 'user-image');
    preview.src = image.dataUrl;
    preview.alt = `添付画像: ${image.name}`;
    message.append(preview);
  }
  conversation.append(message);
  conversation.scrollTop = conversation.scrollHeight;
}

function addResult(data, elapsed, error = false) {
  const message = element('div', 'message assistant');
  const head = element('div', 'response-head');
  head.append(element('span', 'avatar', '◇'), element('strong', '', 'Guardrails の判定'), element('small', '', `${elapsed} ms`));
  message.append(head);
  const card = element('div', error ? 'result-card error-card' : 'result-card');
  if (error) {
    card.textContent = data.error || data.message || 'APIを呼び出せませんでした。';
  } else {
    const results = data.results || {};
    const categories = results.contentModeration?.categories || [];
    const overall = categories.find(item => item.name === 'OVERALL')?.score;
    const injection = results.promptInjection?.score;
    const pii = results.personallyIdentifiableInformation || [];
    const flagged = overall === 1 || injection === 1 || pii.length > 0;
    const title = element('div', 'result-title');
    title.append(element('strong', '', '評価結果'));
    if (data.guardrailVersion?.version) title.append(element('span', 'version-badge', `v${data.guardrailVersion.version}`));
    title.append(element('span', `verdict${flagged ? ' flagged' : ''}`, flagged ? '検出あり' : '検出なし'));
    card.append(title);
    const scores = element('div', 'scores');
    if (overall !== undefined) {
      const box = scoreBox('OVERALL', overall);
      const modalities = categories.find(item => item.name === 'OVERALL')?.flaggedModalities;
      if (modalities?.length) box.append(element('span', 'modality-note', `検出対象: ${modalities.join(' / ')}`));
      scores.append(box);
    }
    if (injection !== undefined) scores.append(scoreBox('PROMPT INJECTION', injection));
    if (categories.some(item => item.name === 'BLOCKLIST')) scores.append(scoreBox('BLOCKLIST', categories.find(item => item.name === 'BLOCKLIST').score, '現行版では照合非対応'));
    if ('personallyIdentifiableInformation' in results) scores.append(scoreBox('PII 件数', pii.length, '英語のみ対応', false));
    if (!scores.children.length) scores.append(element('p', '', '判定項目が返されませんでした。下のAPIレスポンスを確認してください。'));
    card.append(scores);
    if (pii.length) {
      const list = element('div', 'pii-list');
      list.append(element('strong', '', '検出されたPII'));
      for (const item of pii) {
        const entry = element('span', 'pii-item');
        entry.append(element('b', '', item.label || 'PII'), element('span', '', `${item.text || ''} (${Number(item.score).toFixed(2)})`));
        list.append(entry);
      }
      card.append(list);
    }
    const details = element('details');
    details.append(element('summary', '', 'APIレスポンスを見る'), element('pre', '', JSON.stringify(data, null, 2)));
    card.append(details);
  }
  message.append(card);
  conversation.append(message);
  conversation.scrollTop = conversation.scrollHeight;
}

function scoreBox(label, value, note = '', binary = true) {
  const box = element('div', 'score');
  box.append(element('span', 'score-label', label));
  const flagged = binary ? value === 1 : value > 0;
  box.append(element('span', `score-value ${flagged ? 'flagged' : 'safe'}`, String(value)));
  if (note) box.append(element('span', 'score-note', note));
  return box;
}

async function send(text) {
  if (busy || (!text.trim() && !selectedImage)) return;
  if (!versionSelect.value) { setFormMessage('バージョンの取得を確認してください。'); return; }
  if (selectedImage && (!imageCompatible(versionSelect.value) || !$('moderation').checked)) {
    setFormMessage('画像判定には1.1.0以降とContent Moderationが必要です。');
    return;
  }
  busy = true;
  $('send').disabled = true;
  const image = selectedImage;
  addUserMessage(text.trim(), image);
  prompt.value = '';
  clearImage();
  setFormMessage('');
  const start = performance.now();
  try {
    const response = await fetch('/api/guardrails', {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ text, image: image?.dataUrl || null, version: versionSelect.value, moderation: $('moderation').checked, injection: $('injection').checked, pii: $('pii').checked })
    });
    const data = await response.json();
    addResult(data, Math.round(performance.now() - start), !response.ok);
  } catch (error) {
    addResult({ error: error.message }, Math.round(performance.now() - start), true);
  } finally {
    busy = false;
    $('send').disabled = !availableVersions.length;
    prompt.focus();
  }
}

function setFormMessage(message) { $('form-message').textContent = message; }
function imageCompatible(version) { return version.localeCompare('1.1.0', undefined, { numeric: true }) >= 0; }
function syncImageRules() {
  for (const option of versionSelect.options) option.disabled = Boolean(selectedImage) && !imageCompatible(option.value);
  if (selectedImage && !imageCompatible(versionSelect.value)) {
    const compatible = availableVersions.find(imageCompatible);
    if (compatible) versionSelect.value = compatible;
  }
  $('moderation').checked ||= Boolean(selectedImage);
  $('moderation').disabled = Boolean(selectedImage);
  $('version-note').textContent = selectedImage ? '画像判定は1.1.0以降' : '';
}
function clearImage() {
  selectedImage = null;
  imageInput.value = '';
  $('attachment').hidden = true;
  $('image-preview').removeAttribute('src');
  syncImageRules();
}
function readImage(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error('画像を読み込めませんでした。'));
    reader.readAsDataURL(file);
  });
}

imageInput.addEventListener('change', async () => {
  const file = imageInput.files?.[0];
  if (!file) return;
  if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type) || file.size > 4 * 1024 * 1024) {
    imageInput.value = '';
    setFormMessage('PNG・JPEG・WebPの画像を4MB以下で選択してください。');
    return;
  }
  if (!availableVersions.some(imageCompatible)) {
    imageInput.value = '';
    setFormMessage('画像判定に対応したバージョンを利用できません。');
    return;
  }
  try {
    selectedImage = { name: file.name, dataUrl: await readImage(file) };
    $('image-preview').src = selectedImage.dataUrl;
    $('image-name').textContent = file.name;
    $('attachment').hidden = false;
    syncImageRules();
    setFormMessage('');
  } catch (error) { setFormMessage(error.message); }
});
$('remove-image').addEventListener('click', clearImage);
versionSelect.addEventListener('change', syncImageRules);

$('composer').addEventListener('submit', event => { event.preventDefault(); send(prompt.value); });
prompt.addEventListener('keydown', event => {
  if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); send(prompt.value); }
});
document.querySelectorAll('.sample').forEach(button => button.addEventListener('click', () => {
  prompt.value = button.dataset.prompt;
  prompt.focus();
}));
$('new-chat').addEventListener('click', () => { conversation.replaceChildren(); prompt.value = ''; clearImage(); prompt.focus(); });
fetch('/api/status').then(response => response.json()).then(data => {
  $('status-text').textContent = data.ready ? 'OCI署名設定を読み込み済み' : 'OCI認証情報を確認してください';
  $('status-dot').classList.toggle('ready', data.ready);
  $('region-text').textContent = data.region || '';
}).catch(() => { $('status-text').textContent = 'サーバーに接続できません'; });

fetch('/api/versions').then(async response => {
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'バージョンを取得できませんでした。');
  availableVersions = data.versions;
  versionSelect.replaceChildren(...availableVersions.map(version => {
    const option = element('option', '', version);
    option.value = version;
    return option;
  }));
  versionSelect.disabled = false;
  $('send').disabled = false;
}).catch(error => {
  versionSelect.replaceChildren(new Option('取得失敗', ''));
  setFormMessage(error.message);
});
