/* global state */
const state = {
  currentArticle: null,
  history: [],
};

/* ── DOM helpers ─────────────────────────────────────── */
const $ = id => document.getElementById(id);
const show = el => el.classList.add('show');
const hide = el => el.classList.remove('show');

/* ── Toast ────────────────────────────────────────────── */
let toastTimer;
function toast(msg, type = 'info', duration = 3000) {
  const el = $('toast');
  el.textContent = msg;
  el.className = 'show ' + type;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.className = ''; }, duration);
}

/* ── Status bar ───────────────────────────────────────── */
function setStatus(msg, type, showSpinner = false) {
  const bar = $('status-bar');
  bar.className = 'show ' + type;
  bar.innerHTML = showSpinner
    ? `<div class="spinner"></div><span>${msg}</span>`
    : `<span>${msg}</span>`;
}
function clearStatus() { $('status-bar').className = ''; }

/* ── API ──────────────────────────────────────────────── */
async function apiFetch(path, method = 'GET', body = null) {
  const opts = { method, headers: {} };
  if (body) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '网络错误' }));
    throw new Error(err.detail || '请求失败');
  }
  return res.json();
}

/* ── Extract (preview) ───────────────────────────────── */
async function doExtract() {
  const url = $('url-input').value.trim();
  if (!url) { toast('请粘贴微信文章链接', 'error'); return; }

  $('btn-extract').disabled = true;
  hide($('preview-card'));
  state.currentArticle = null;
  setStatus('正在获取文章信息…', 'info', true);

  try {
    const data = await apiFetch('/api/extract', 'POST', { url });
    state.currentArticle = { ...data, url };
    renderPreview(data);
    clearStatus();
    show($('preview-card'));
  } catch (e) {
    setStatus(e.message, 'error');
  } finally {
    $('btn-extract').disabled = false;
  }
}

function renderPreview(data) {
  const set = (id, val) => { const el = $(id); if (el) el.textContent = val || '—'; };
  set('pre-title', data.title);
  set('pre-source', data.source);
  set('pre-author', data.author);
  set('pre-date', data.date);
  set('pre-images', `${data.image_count} 张图片`);
  set('pre-words', `约 ${data.word_count} 字`);
  set('pre-text', data.text_preview + '…');
}

/* ── Save ─────────────────────────────────────────────── */
async function doSave() {
  const url = $('url-input').value.trim();
  if (!url) { toast('请先填写链接', 'error'); return; }

  const formats = [];
  if ($('fmt-md').checked) formats.push('md');
  if ($('fmt-pdf').checked) formats.push('pdf');
  if (!formats.length) { toast('请至少选择一种格式', 'error'); return; }

  const save_path = $('save-path').value.trim() || null;

  $('btn-save').disabled = true;
  setStatus('正在抓取并保存文章，请稍候（可能需要 10-30 秒）…', 'info', true);

  try {
    const data = await apiFetch('/api/save', 'POST', { url, formats, save_path });
    state.history.unshift(data);
    renderHistory();
    setStatus(`✅ 保存成功：${data.title}`, 'success');
    toast('保存成功！', 'success');
  } catch (e) {
    setStatus(e.message, 'error');
    toast(e.message, 'error', 5000);
  } finally {
    $('btn-save').disabled = false;
  }
}

/* ── History ──────────────────────────────────────────── */
async function loadHistory() {
  try {
    state.history = await apiFetch('/api/history');
    renderHistory();
  } catch { /* ignore */ }
}

function renderHistory() {
  const list = $('history-list');
  if (!state.history.length) {
    list.innerHTML = '<p class="history-empty">暂无保存记录</p>';
    return;
  }

  list.innerHTML = state.history.map(item => {
    const formats = (item.saved_formats || []).map(f =>
      `<span class="tag">${f.toUpperCase()}</span>`
    ).join('');

    const savedAt = item.saved_at
      ? new Date(item.saved_at).toLocaleString('zh-CN', { hour12: false })
      : '';

    // 主保存路径
    const mainPath = item.save_dir || '';

    // 额外目标
    const extra = [];
    if (item.obsidian_path) extra.push('已同步 Obsidian');
    if (item.gdrive_path)   extra.push('已复制到 Google Drive');
    const extraText = extra.length ? `· ${extra.join(' · ')}` : '';

    return `
      <div class="history-item">
        <div class="history-icon">📄</div>
        <div class="history-body">
          <div class="history-title" title="${escHtml(item.title || '')}">${escHtml(item.title || '未知标题')}</div>
          <div class="history-meta">
            <span>${escHtml(item.source || '')}</span>
            <span>${escHtml(item.author || '')}</span>
            <span>${escHtml(savedAt)}</span>
            ${extraText ? `<span>${escHtml(extraText)}</span>` : ''}
          </div>
          <div class="history-tags">${formats}</div>
          ${mainPath ? `<div class="history-path" title="${escHtml(mainPath)}">${escHtml(mainPath)}</div>` : ''}
        </div>
      </div>
    `;
  }).join('');
}

async function clearHistory() {
  if (!confirm('确定清空所有保存记录？')) return;
  await apiFetch('/api/history', 'DELETE');
  state.history = [];
  renderHistory();
  toast('历史已清空');
}

/* ── Settings modal ──────────────────────────────────── */
async function openSettings() {
  try {
    const cfg = await apiFetch('/api/config');
    $('cfg-save-path').value  = cfg.default_save_path  || '';
    $('cfg-obsidian').value   = cfg.obsidian_vault     || '';
    $('cfg-gdrive').value     = cfg.google_drive_path  || '';
  } catch { /* ignore */ }
  show($('modal-backdrop'));
}

function closeSettings() { hide($('modal-backdrop')); }

async function saveSettings() {
  const payload = {
    default_save_path: $('cfg-save-path').value.trim(),
    obsidian_vault:    $('cfg-obsidian').value.trim(),
    google_drive_path: $('cfg-gdrive').value.trim(),
  };
  try {
    await apiFetch('/api/config', 'PUT', payload);
    // 同步默认保存路径到输入框
    if (payload.default_save_path) {
      $('save-path').placeholder = payload.default_save_path;
    }
    closeSettings();
    toast('设置已保存', 'success');
  } catch (e) {
    toast(e.message, 'error');
  }
}

/* ── Utility ──────────────────────────────────────────── */
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/* ── Convert (batch link → accessible URL) ───────────── */
async function doConvert() {
  const raw = $('convert-input').value.trim();
  if (!raw) { toast('请粘贴至少一条微信链接', 'error'); return; }

  const urls = raw.split('\n').map(u => u.trim()).filter(Boolean);
  if (!urls.length) { toast('未检测到有效链接', 'error'); return; }

  $('btn-convert').disabled = true;
  setConvertStatus(`正在转换 ${urls.length} 条链接，请耐心等待（每条间隔 1-3 秒）…`, 'info', true);
  $('convert-results').innerHTML = '';

  try {
    const data = await apiFetch('/api/convert', 'POST', { urls });
    renderConvertResults(data.results);
    const ok = data.results.filter(r => !r.error).length;
    const fail = data.results.length - ok;
    setConvertStatus(
      `完成：${ok} 条成功${fail ? `，${fail} 条失败` : ''}`,
      fail > 0 ? 'error' : 'success',
    );
  } catch (e) {
    setConvertStatus(e.message, 'error');
  } finally {
    $('btn-convert').disabled = false;
  }
}

function renderConvertResults(results) {
  const wrap = $('convert-results');
  if (!results || !results.length) { wrap.innerHTML = ''; return; }

  wrap.innerHTML = results.map(r => {
    if (r.error) {
      return `
        <div class="convert-item convert-item--error">
          <div class="convert-item-url" title="${escHtml(r.url)}">${escHtml(r.url)}</div>
          <div class="convert-item-error">❌ ${escHtml(r.error)}</div>
        </div>`;
    }
    // 用 location.origin 补全完整 URL，不依赖后端 server_base_url 配置
    const articlePath = r.article_id ? `/article/${r.article_id}` : (r.accessible_url || '');
    const fullUrl = articlePath.startsWith('http') ? articlePath : location.origin + articlePath;
    const cached = r.already_cached ? ' <span class="tag tag--cached">已缓存</span>' : ' <span class="tag tag--new">新转换</span>';
    return `
      <div class="convert-item">
        <div class="convert-item-title">${escHtml(r.title || '未知标题')}${cached}</div>
        <div class="convert-item-row">
          <a class="convert-item-link" href="${escHtml(fullUrl)}" target="_blank">${escHtml(fullUrl)}</a>
          <button class="btn-copy" data-url="${escHtml(fullUrl)}" onclick="copyUrl(this)">复制</button>
        </div>
      </div>`;
  }).join('');
}

function copyUrl(btn) {
  // 通过 data-url 属性读取，避免 HTML 转义破坏 URL
  const url = btn.dataset ? btn.dataset.url : btn;
  const onSuccess = () => {
    const orig = btn.textContent;
    btn.textContent = '已复制✓';
    btn.style.background = '#e8f9ee';
    toast('链接已复制', 'success', 2000);
    setTimeout(() => { btn.textContent = orig; btn.style.background = ''; }, 2000);
  };
  const fallback = () => {
    // 降级：创建临时 input 复制（HTTP 环境 navigator.clipboard 不可用）
    const tmp = document.createElement('input');
    tmp.value = url;
    document.body.appendChild(tmp);
    tmp.select();
    document.execCommand('copy');
    document.body.removeChild(tmp);
    onSuccess();
  };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(url).then(onSuccess).catch(fallback);
  } else {
    fallback();
  }
}

function setConvertStatus(msg, type, showSpinner = false) {
  const bar = $('convert-status');
  bar.className = 'convert-status show ' + type;
  bar.innerHTML = showSpinner
    ? `<div class="spinner"></div><span>${msg}</span>`
    : `<span>${msg}</span>`;
}

/* ── Cached articles management ──────────────────────── */
async function loadCached() {
  const card = $('cached-card');
  card.style.display = 'block';
  try {
    const data = await apiFetch('/api/cached');
    renderCached(data.articles || []);
  } catch (e) {
    $('cached-list').innerHTML = `<p class="history-empty">${escHtml(e.message)}</p>`;
  }
}

function renderCached(articles) {
  const list = $('cached-list');
  if (!articles.length) {
    list.innerHTML = '<p class="history-empty">暂无缓存文章</p>';
    return;
  }
  list.innerHTML = articles.map(a => {
    const articleUrl = location.origin + '/article/' + a.id;
    return `
    <div class="history-item" id="cached-${escHtml(a.id)}">
      <div class="history-icon">📄</div>
      <div class="history-body">
        <div class="history-title">${escHtml(a.title || '未知标题')}</div>
        <div class="history-meta">
          <span>${escHtml(a.source || '')}</span>
          <span>${escHtml(a.author || '')}</span>
          <span>${escHtml(a.date || '')}</span>
        </div>
        <div class="history-path" style="display:flex;align-items:center;gap:8px;margin-top:6px;flex-wrap:wrap;">
          <a href="${escHtml(articleUrl)}" target="_blank" style="font-size:12px;color:var(--accent);word-break:break-all;">${escHtml(articleUrl)}</a>
          <button class="btn-copy" data-url="${escHtml(articleUrl)}" onclick="copyUrl(this)">复制</button>
          <button class="btn-delete" onclick="deleteCached('${escHtml(a.id)}')">删除</button>
        </div>
      </div>
    </div>
  `}).join('');
}

async function deleteCached(articleId) {
  if (!confirm('确定删除这篇缓存文章？')) return;
  try {
    await apiFetch(`/api/cached/${articleId}`, 'DELETE');
    const el = $(`cached-${articleId}`);
    if (el) el.remove();
    toast('已删除', 'success');
    // 若列表空了，刷新一下
    if (!$('cached-list').querySelector('.history-item')) {
      $('cached-list').innerHTML = '<p class="history-empty">暂无缓存文章</p>';
    }
  } catch (e) {
    toast(e.message, 'error');
  }
}

/* ── Init ─────────────────────────────────────────────── */
async function init() {
  // 从服务器加载历史
  await loadHistory();

  // 同步默认路径为 placeholder
  try {
    const cfg = await apiFetch('/api/config');
    if (cfg.default_save_path) {
      $('save-path').placeholder = cfg.default_save_path;
    }
  } catch { /* ignore */ }

  // 事件绑定
  $('btn-extract').addEventListener('click', doExtract);
  $('btn-save').addEventListener('click', doSave);
  $('btn-clear-history').addEventListener('click', clearHistory);
  $('btn-settings').addEventListener('click', openSettings);
  $('btn-close-modal').addEventListener('click', closeSettings);
  $('btn-cancel-modal').addEventListener('click', closeSettings);
  $('btn-save-modal').addEventListener('click', saveSettings);

  // 关闭 modal 点击遮罩
  $('modal-backdrop').addEventListener('click', e => {
    if (e.target === $('modal-backdrop')) closeSettings();
  });

  $('btn-convert').addEventListener('click', doConvert);
  $('btn-load-cached').addEventListener('click', loadCached);
  $('btn-refresh-cached').addEventListener('click', loadCached);

  // 回车触发提取
  $('url-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') doExtract();
  });
}

document.addEventListener('DOMContentLoaded', init);
