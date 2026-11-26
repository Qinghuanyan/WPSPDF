// 任务窗格：状态 + 一键转换 + 进度（进度以引擎为准，关掉窗格再打开会接上）
const PORTS = [38731, 38732, 38733, 38734];
let base = null;
let curJob = null;
let sawRunning = false;
let openedFor = null;
let timer = null;
const $ = id => document.getElementById(id);

function pdfPathSafe() {
    try {
        const d = (typeof Application !== 'undefined' && Application.ActiveDocument);
        if (!d) return '';
        const cands = ['FullName', 'Path'];
        for (const k of cands) { const v = d[k]; if (v && /\.pdf$/i.test(v)) return v; }
        const p = d.Path, n = d.Name;
        if (p && n) return p.replace(/[\\\/]$/, '') + '\\' + n;
    } catch (e) { }
    return '';
}

function log(m) {
    const el = $('log');
    const t = new Date().toLocaleTimeString('zh-CN', { hour12: false });
    el.textContent = (el.textContent === '（空）' ? '' : el.textContent + '\n') + `[${t}] ${m}`;
    el.scrollTop = el.scrollHeight;
}

function mmss(s) {
    if (s === null || s === undefined) return '—';
    s = Math.max(0, Math.round(s));
    const m = Math.floor(s / 60), r = s % 60;
    return m > 0 ? `${m} 分 ${String(r).padStart(2, '0')} 秒` : `${r} 秒`;
}

async function probe() {
    for (const p of PORTS) {
        try {
            const r = await fetch(`http://127.0.0.1:${p}/ping`, { cache: 'no-store' });
            if (r.ok) { base = `http://127.0.0.1:${p}`; return true; }
        } catch (e) { }
    }
    return false;
}

function paint(job) {
    if (!job) {
        $('barIn').style.width = '0%';
        $('hint').textContent = '—';
        $('btnGo').disabled = false;
        $('btnGo').textContent = '开始转换';
        return;
    }
    const st = job.state;
    const pct = job.percent != null ? job.percent : 0;
    $('barIn').style.width = pct + '%';

    if (st === 'running') {
        const done = job.pages_done || 0, total = job.pages_total || 0;
        const eta = job.eta_s != null ? ` · 预计剩余 ${mmss(job.eta_s)}` : '';
        $('hint').textContent = (total ? `第 ${done} / ${total} 页` : '准备中') + eta;
        $('btnGo').disabled = true;
        $('btnGo').textContent = '转换中…';
    } else if (st === 'done') {
        $('hint').textContent = '完成：' + (job.out || '');
        $('btnGo').disabled = false;
        $('btnGo').textContent = '开始转换';
    } else if (st === 'error') {
        $('hint').textContent = '失败：' + (job.msg || '');
        $('btnGo').disabled = false;
        $('btnGo').textContent = '重试';
    }
}

async function fetchJob() {
    try {
        const r = await fetch(`${base}/job`, { cache: 'no-store' });
        const d = await r.json();
        return d.job || null;
    } catch (e) { return null; }
}

function openResult(path) {
    if (!path) return;
    try {
        fetch(`${base}/open?path=` + encodeURIComponent(path))
            .then(r => r.json())
            .then(d => log(d.ok ? ('已用 WPS 表格打开：' + path) : ('打开失败：' + (d.error || ''))))
            .catch(e => log('打开失败：' + e));
    } catch (e) { log('打开失败：' + e); }
}

async function tick() {
    if (!base) return;
    const job = await fetchJob();
    if (job && job.id !== curJob) { curJob = job.id; sawRunning = false; log('接管任务 ' + job.id); }
    if (job && job.state === 'running') sawRunning = true;
    // 只有“亲眼看到它在跑、然后变完成”才自动打开，避免每次开窗格都弹一次
    if (job && job.state === 'done' && openedFor !== job.id) {
        openedFor = job.id;
        if (job.opened) log('已用 WPS 表格打开产物');
    }
    paint(job);
    if (job && job.state === 'running') {
        timer = setTimeout(tick, 1000);
    } else {
        timer = null;
    }
}

async function init() {
    const ok = await probe();
    $('dot').className = 'dot ' + (ok ? 'ok' : 'bad');
    $('state').textContent = ok ? '引擎在线' : '引擎未启动 · 双击桌面「PDF转表格·启动引擎」';
    const path = pdfPathSafe();
    $('pdfPath').textContent = '当前 PDF：' + (path || '—（取不到路径）');
    if (ok) { log(`ping ok ${base}`); tick(); }
}

$('btnGo').onclick = async () => {
    if (!base) {
        const ok = await probe();
        if (!ok) { $('state').textContent = '引擎未启动 · 双击桌面「PDF转表格·启动引擎」'; log('引擎未启动'); return; }
    }
    const path = pdfPathSafe();
    if (!path) { $('hint').textContent = '取不到当前 PDF 路径'; return; }
    $('btnGo').disabled = true;
    const res = await fetch(`${base}/convert`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path })
    });
    const data = await res.json();
    if (!data.ok) { $('hint').textContent = '提交失败：' + (data.error || res.status); $('btnGo').disabled = false; return; }
    curJob = data.job;
    log('任务 ' + data.job);
    if (timer) clearTimeout(timer);
    tick();
};

init();
