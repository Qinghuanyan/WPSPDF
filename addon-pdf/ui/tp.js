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
    setOnline(ok);
    const path = pdfPathSafe();
    $('pdfPath').textContent = '当前 PDF：' + (path || '—（取不到路径）');
    if (ok) { log(`ping ok ${base}`); tick(); }
    else { startWaiting(true); }     // 没起来就自己等（计划任务会按需拉起）
}

// ---- 引擎未就绪时的自助入口 ----
// 页面无法直接创建进程（实测 ShellExecute 无效、CreateObject 报 Load dll fail、
// CoCreateInstance cannot create、自定义协议也不触发），所以按钮的语义是：
// 「已请求启动，等系统按需拉起」+ 每 2 秒自检，起来就自动接管。
let waitTimer = null, waitDeadline = 0;

function setOnline(ok) {
    $('dot').className = 'dot ' + (ok ? 'ok' : 'bad');
    $('state').textContent = ok ? '引擎在线' : '引擎未启动';
    $('cardEngine').style.display = ok ? 'none' : 'block';
    $('btnGo').disabled = !ok;
}

function startWaiting(auto) {
    $('cardEngine').style.display = 'block';
    $('btnEngine').disabled = true;
    $('btnEngine').textContent = '正在等待引擎…';
    $('engineHint').textContent = '已请求启动：系统每 1 分钟检查一次，通常 60 秒内就绪（也可双击桌面「PDF转表格·启动引擎」立即启动）';
    if (auto === true) log('引擎未启动，开始自动等待');
    if (waitTimer) return;
    waitDeadline = Date.now() + 90000;
    const step = async () => {
        const ok = await probe();
        if (ok) {
            waitTimer = null;
            setOnline(true);
            $('btnEngine').disabled = false;
            $('btnEngine').textContent = '启动引擎';
            log('引擎已就绪 ' + base);
            tick();
            return;
        }
        if (Date.now() > waitDeadline) {
            waitTimer = null;
            $('btnEngine').disabled = false;
            $('btnEngine').textContent = '重试';
            $('engineHint').textContent = '还没就绪：请双击桌面「PDF转表格·启动引擎」，或稍后再点「重试」';
            log('等待超时');
            return;
        }
        waitTimer = setTimeout(step, 2000);
    };
    step();
}

$('btnEngine').onclick = async () => {
    log('请求启动引擎');
    const asked = await askLoaderStart();
    if (asked) log('轻量加载器已受理，等待引擎就绪');
    startWaiting(false);
};

// 页面不能创建进程，但可以 HTTP 请求「轻量加载器」，由它来创建（参考 LocalReadTranslate 分层启动）
async function askLoaderStart() {
    try {
        const r = await fetch('http://127.0.0.1:38730/start', { method: 'POST', cache: 'no-store' });
        const d = await r.json();
        return !!d.ok;
    } catch (e) {
        log('轻量加载器不在线（可双击桌面「PDF转表格·启动引擎」，或运行 tools\\install-loader.ps1 安装）');
        return false;
    }
}

// 每 5 秒自检一次：引擎起来/挂掉都能自己发现，面板不会停留在过期状态
setInterval(async () => {
    const wasOnline = !!base;
    const ok = await probe();
    if (ok && !wasOnline) {
        setOnline(true);
        log('检测到引擎恢复 ' + base);
        tick();
    } else if (!ok && wasOnline) {
        base = null;
        setOnline(false);
        log('引擎已断开');
        startWaiting(true);
    }
}, 5000);


$('btnGo').onclick = async () => {
    if (!base) {
        const ok = await probe();
        if (!ok) { setOnline(false); startWaiting(false); log('引擎未启动，已转为等待'); return; }
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

// 关窗格时停掉轮询，别给宿主播放中的页面添等待
window.addEventListener('pagehide', function () { if (timer) clearTimeout(timer); });
