# -*- coding: utf-8 -*-
"""PDF（文字已转曲）→ xlsx 转换器 v2

管线：
  1) 矢量框线 → 行列网格（grid.py，坐标精确）
     跨页取并集列边界，补齐「某页末列没画右边框」缺的列
  2) 整页栅格化 → RapidOCR（det+rec），多进程按页并行
  3) 文本框中心落格 → 单元格文本；同线块先按 y 聚类再按 x 排序，避免换行顺序颠倒
  4) 空单元格二次识别：只对「所在行有内容但该格没文字」的格子做单元格级 OCR（300dpi）
  5) 序号序列校验：OCR 把 093 认成 E60 这类脏值按前后值补回
  6) openpyxl 写出：列宽/字号还原、首行冻结、自动筛选、低置信度格高亮

用法：
  py -3 engine/convert.py "输入.pdf" -o "输出.xlsx" [--pages 1-3] [--dpi 200] [--no-recover]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import fitz
import numpy as np
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from grid import page_grid, locate, union_xs, xs_is_subset  # noqa: E402

# 同一文本行内允许的 y 抖动：OCR 会把一行切成多块，y 常差 0.1–0.5pt，
# 若直接按 (y, x) 排序会把右边的块排到左边块前面（标题因此颠倒）。
LINE_TOL = 3.0
RECOVER_DPI = 300   # 空单元格二次识别的 dpi
RECOVER_PADS = (2.0, 0.0, 3.0)   # 依次尝试的留白（pt）
LOW_SCORE = 0.55    # 低于此置信度的格子标黄，提示人工抽查
INK_DPI = 96        # 判「格里有没有墨」用的低 dpi
INK_GRAY = 200      # 低于该灰度视为有墨
TEXT_SCORE = 0.35   # 识别分下限（RapidOCR 默认 0.5，会滤掉正确的短文本）
CACHE_VERSION = "v3"   # OCR 参数或后处理变化时递增，让旧缓存失效
CACHE_DIR = Path(__file__).resolve().parent.parent / ".run" / "ocr_cache"


class Ocr:
    def __init__(self, text_score: float = TEXT_SCORE):
        from rapidocr_onnxruntime import RapidOCR
        # text_score 默认 0.5 会把「恒我」这类低分但正确的短文本整块滤掉（实测 0.40），
        # 降到 0.35 捞回来；低分格由标黄机制提示人工抽查，不会静默混入。
        self.engine = RapidOCR(text_score=text_score)

    def _run(self, img):
        res, _ = self.engine(img)
        return res or []

    def page(self, page: fitz.Page, dpi: int):
        """整页识别，返回 [(cx, cy, text, score)]，坐标为 PDF point。"""
        pix = page.get_pixmap(dpi=dpi)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.n == 4:
            img = img[:, :, :3]
        scale = page.rect.width / pix.width
        out = []
        for item in self._run(img):
            box, text, score = item[0], item[1], item[2]
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            t = str(text).strip()
            if t:
                out.append((sum(xs) / 4.0 * scale, sum(ys) / 4.0 * scale, t, float(score)))
        return out

    def crop(self, page: fitz.Page, rect: fitz.Rect, dpi: int = RECOVER_DPI, pad: float = 1.0):
        """单元格级识别，返回 [(cx, cy, text, score)]，坐标为 PDF point。"""
        r = fitz.Rect(rect.x0 - pad, rect.y0 - pad, rect.x1 + pad, rect.y1 + pad) & page.rect
        if r.is_empty:
            return []
        pix = page.get_pixmap(dpi=dpi, clip=r)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.n == 4:
            img = img[:, :, :3]
        sx = r.width / pix.width
        sy = r.height / pix.height
        out = []
        for item in self._run(img):
            box, text, score = item[0], item[1], item[2]
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            t = str(text).strip()
            if t:
                out.append((r.x0 + sum(xs) / 4.0 * sx, r.y0 + sum(ys) / 4.0 * sy, t, float(score)))
        return out


# ---------------------------------------------------------------- 并行 OCR

_OCR: Ocr | None = None


def _page_blocks(job):
    """子进程任务：整页 OCR。返回 [(cx, cy, text, score)]。"""
    global _OCR
    pdf_path, pno, dpi = job
    if _OCR is None:
        _OCR = Ocr()
    doc = fitz.open(pdf_path)
    try:
        return _OCR.page(doc[pno], dpi)
    finally:
        doc.close()


def default_workers(n_pages: int) -> int:
    """默认单进程。

    实测：本机（32 逻辑核 / 3.6 GB 空闲）2 进程 120.9s、1 进程 118.5s——并行无收益，
    因为 onnxruntime 自身已在核间并行，多进程只是重复加载模型并抢内存。
    想试并行可设环境变量 WPSPDF_WORKERS=2..4。
    """
    env = os.environ.get("WPSPDF_WORKERS")
    if env:
        try:
            return max(1, int(env))
        except ValueError:
            pass
    return 1


def ocr_pages(pdf_path: str, pages: list[int], dpi: int, workers: int, verbose=True,
              use_cache: bool = True):
    """按页 OCR，保序产出 (pno, blocks)。

    同一份 PDF 重复转换时命中页级缓存（键 = 文件内容哈希 + 页号 + dpi），
    只对本页首次识别才真正跑模型。进度行格式保持 `[page N]`，供 server.py 解析。
    """
    fh = _file_hash(pdf_path) if use_cache else ""
    done: dict[int, list] = {}
    todo: list[int] = []
    if use_cache:
        for pno in pages:
            got = _cache_get(fh, pno, dpi)
            if got is not None:
                done[pno] = got
            else:
                todo.append(pno)
        if verbose and done:
            print(f"OCR 缓存命中 {len(done)}/{len(pages)} 页")
    else:
        todo = list(pages)

    if workers <= 1 or len(todo) <= 1:
        if todo:
            ocr = Ocr()
            doc = fitz.open(pdf_path)
            try:
                for pno in todo:
                    bl = ocr.page(doc[pno], dpi)
                    _cache_put(fh, pno, dpi, bl)
                    done[pno] = bl
            finally:
                doc.close()
    else:
        import multiprocessing as mp
        ctx = mp.get_context("spawn")
        jobs = [(str(pdf_path), pno, dpi) for pno in todo]
        with ctx.Pool(processes=min(workers, len(jobs))) as pool:
            for pno, bl in zip(todo, pool.imap(_page_blocks, jobs)):
                _cache_put(fh, pno, dpi, bl)
                done[pno] = bl

    for pno in pages:
        yield pno, done[pno]


def _file_hash(path: str) -> str:
    h = hashlib.sha1()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        return ""
    return h.hexdigest()[:16]


def _cache_path(fh: str, pno: int, dpi: int) -> Path:
    return CACHE_DIR / f"{CACHE_VERSION}-{fh}-p{pno}-d{dpi}.json"


def _cache_get(fh: str, pno: int, dpi: int):
    if not fh:
        return None
    fp = _cache_path(fh, pno, dpi)
    if not fp.exists():
        return None
    try:
        return [tuple(b) for b in json.loads(fp.read_text("utf-8"))]
    except Exception:  # noqa: BLE001  缓存坏了就当没有
        return None


def _cache_put(fh: str, pno: int, dpi: int, blocks):
    if not fh:
        return
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(fh, pno, dpi).write_text(
            json.dumps([[round(b[0], 2), round(b[1], 2), b[2], round(b[3], 3)] for b in blocks],
                       ensure_ascii=False),
            "utf-8")
    except Exception:  # noqa: BLE001
        pass


def has_ink(page: fitz.Page, rect: fitz.Rect, dpi: int = INK_DPI, gray: int = INK_GRAY,
            inset: float = 1.5) -> bool:
    """格子里有没有墨（深色像素）。

    inset 必须内缩：单元格矩形自带 1px 边框线，不内缩会把框线当成墨，
    于是每个空格都被判「有墨」→ 白跑 OCR 还报一堆假残留。
    """
    r = fitz.Rect(rect.x0 + inset, rect.y0 + inset, rect.x1 - inset, rect.y1 - inset) & page.rect
    if r.is_empty or r.width < 1 or r.height < 1:
        return False
    pix = page.get_pixmap(dpi=dpi, clip=r, colorspace=fitz.csGRAY)
    if not pix.samples:
        return False
    return min(pix.samples) < gray


# ---------------------------------------------------------------- 单元格拼装

def join_cell(blocks) -> str:
    """把一个单元格里的多个 OCR 块拼成文本。

    先按 y 聚类成「行」，行内按 x 从左到右，行与行之间按 y 从上到下。
    这样 2 行以上的单元格（长标题、多人名）换行顺序不会颠倒。
    """
    if not blocks:
        return ""
    lines: list[list] = []  # [y_avg, [(x, text)]]
    for blk in sorted(blocks, key=lambda b: (b[0], b[1])):
        cy, cx, txt = blk[0], blk[1], blk[2]
        if lines and abs(cy - lines[-1][0]) <= LINE_TOL:
            lines[-1][1].append((cx, txt))
            n = len(lines[-1][1])
            lines[-1][0] = (lines[-1][0] * (n - 1) + cy) / n
        else:
            lines.append([cy, [(cx, txt)]])
    return "".join("".join(t for _, t in sorted(parts)) for _, parts in lines)


def repair_sequence(ws, col: int = 2, verbose: bool = True):
    """序号应严格 +1 递增。OCR 误读（如 093→E60）按前后值补回。

    只改「非纯数字」的格子；空行（分组间隔行）不参与推断，纯数字格一律不动。
    """
    prev = None
    fixed = []
    for r in range(2, ws.max_row + 1):
        cell = ws.cell(row=r, column=col)
        s = "" if cell.value is None else str(cell.value).strip()
        if not s:
            continue
        if s.isdigit():
            prev = int(s)
            continue
        nxt = None
        for rr in range(r + 1, min(ws.max_row, r + 6) + 1):
            t = ws.cell(row=rr, column=col).value
            ts = "" if t is None else str(t).strip()
            if ts.isdigit():
                nxt = int(ts)
                break
        if prev is None and nxt is None:
            continue
        # 前后都要对得上「中间只隔一行」才认定是被误读的序号
        if prev is not None and nxt is not None and nxt != prev + 2:
            continue
        guess = prev + 1 if prev is not None else nxt - 1
        if guess < 0:
            continue
        new = f"{guess:03d}"
        cell.value = new
        fixed.append((r, s, new))
        prev = guess
    if fixed and verbose:
        for r, old, new in fixed:
            print(f"  序号修复 行{r}: {old!r} → {new!r}")
    return fixed


def parse_pages(spec: str | None, total: int):
    if not spec:
        return list(range(total))
    sel = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            sel.update(range(int(a) - 1, int(b)))
        elif part:
            sel.add(int(part) - 1)
    return [p for p in sorted(sel) if 0 <= p < total]


def convert(pdf_path: str, out_path: str, pages_spec: str | None = None, dpi: int = 200,
            verbose=True, repair_seq: bool = True, workers: int | None = None,
            recover: bool = True, mark_low: bool = True):
    doc = fitz.open(pdf_path)
    pages = parse_pages(pages_spec, doc.page_count)
    grids = {}
    for pno in pages:
        grids[pno] = page_grid(doc[pno])

    # 跨页规范列边界：补齐「某页末列没画右边框」缺的列，否则整列文字被判网格外丢弃
    canon = union_xs([doc[pno] for pno in pages])
    if verbose:
        print(f"规范列边界 {len(canon)-1} 列: {[round(v) for v in canon]}")

    n_workers = workers if workers is not None else default_workers(len(pages))
    if verbose:
        print(f"OCR 并行进程 {n_workers}，dpi={dpi}")

    wb = Workbook()
    ws = wb.active
    ws.title = "数据"
    rec_ocr = Ocr() if recover else None   # 补救用，单进程顺序跑（格子小、量少）

    row_cursor = 1
    col_widths: dict[int, float] = {}
    warn = 0
    recovered = 0
    residual = 0
    residual_cells: list[tuple[int, int, int]] = []
    flagged: list[tuple[int, int, str, float]] = []
    low_cells = 0
    page_rows: list[tuple[int, int, int]] = []
    t_all = time.time()
    mark = PatternFill("solid", fgColor="FFF2CC")

    for pno, blocks in ocr_pages(pdf_path, pages, dpi, n_workers, verbose):
        t0 = time.time()
        page = doc[pno]
        ys, page_xs = grids[pno]
        xs = canon if (canon and xs_is_subset(page_xs, canon)) else page_xs
        if len(ys) < 2 or len(xs) < 2:
            if verbose:
                print(f"[page {pno+1}] 未识别到网格，跳过", file=sys.stderr)
            continue
        nrow, ncol = len(ys) - 1, len(xs) - 1

        cells: dict[tuple[int, int], list] = {}
        for cx, cy, text, score in blocks:
            hit = locate(cx, cy, ys, xs)
            if not hit or hit[0] >= nrow or hit[1] >= ncol:
                warn += 1
                continue
            cells.setdefault(hit, []).append((cy, cx, text, score))

        # 空单元格二次识别：只在「该行有内容」时补，整行空的是分组间隔行；
        # 先判墨迹，空白格直接跳过（大多数「指导教师为空」属于这种）
        if rec_ocr is not None:
            for i in range(nrow):
                if not any(cells.get((i, j)) for j in range(ncol)):
                    continue
                for j in range(ncol):
                    if cells.get((i, j)):
                        continue
                    rect = fitz.Rect(xs[j], ys[i], xs[j + 1], ys[i + 1])
                    if not has_ink(page, rect):
                        continue
                    got = []
                    # 留白要试多档：紧贴边（pad 0–1）常被判「无文本」，
                    # 留 2pt 才稳定读出；留太多又会把邻居的字带进来（靠中心点过滤挡掉）
                    for pad in RECOVER_PADS:
                        cand = [b for b in rec_ocr.crop(page, rect, pad=pad)
                                if rect.contains(fitz.Point(b[0], b[1]))]
                        if cand:
                            got = cand
                            break
                    if got:
                        cells[(i, j)] = got
                        recovered += 1
                    else:
                        residual += 1
                        if len(residual_cells) < 40:
                            residual_cells.append((pno + 1, row_cursor + i, j + 1))

        page_rows.append((pno + 1, row_cursor, row_cursor + nrow - 1))
        for i in range(nrow):
            for j in range(ncol):
                bl = cells.get((i, j))
                txt = join_cell(bl)
                if not txt:
                    continue
                cell = ws.cell(row=row_cursor + i, column=j + 1, value=txt)
                # 序号列（第 2 列）由 repair_sequence 做序列校验，不必靠置信度标黄
                score = min(b[3] for b in bl)
                if mark_low and j != 1 and score < LOW_SCORE:
                    cell.fill = mark
                    low_cells += 1
                    flagged.append((row_cursor + i, j + 1, txt, score))
            for j in range(ncol):
                w = xs[j + 1] - xs[j]
                col_widths[j] = max(col_widths.get(j, 0), w)
        if verbose:
            print(f"[page {pno+1}] 网格 {nrow}行 x {ncol}列  OCR {len(blocks)}块  "
                  f"{time.time()-t0:.1f}s  累计 {time.time()-t_all:.0f}s")
        row_cursor += nrow

    fixed = repair_sequence(ws, verbose=verbose) if repair_seq else []

    for j, w in col_widths.items():
        ws.column_dimensions[get_column_letter(j + 1)].width = max(6, min(60, w / 5.2))
    for row in ws.iter_rows():
        for c in row:
            c.font = Font(name="宋体", size=9)
            c.alignment = Alignment(horizontal="left", vertical="center", wrap_text=False)
    ws.freeze_panes = "A2"
    if row_cursor > 2 and col_widths:
        ws.auto_filter.ref = f"A1:{get_column_letter(max(col_widths) + 1)}{row_cursor - 1}"

    # 校对清单：把标黄格连同页码/行列/置信度列出来，比只标黄更容易核对
    if flagged:
        qa = wb.create_sheet("需校对")
        n_head = max(col_widths) + 1 if col_widths else ws.max_column
        heads = [ws.cell(row=1, column=c).value or f"列{c}" for c in range(1, n_head + 1)]

        def page_of(row: int) -> int | str:
            for pno, a, b in page_rows:
                if a <= row <= b:
                    return pno
            return ""

        qa.append(["页", "行号", "列名", "当前内容", "置信度"])
        for r, c, txt, score in flagged:
            name = heads[c - 1] if c - 1 < len(heads) else f"列{c}"
            qa.append([page_of(r), r, name, txt, round(score, 2)])
        for line in qa.iter_rows():
            for cell in line:
                cell.font = Font(name="宋体", size=9)
        for col, width in zip("ABCDE", (6, 8, 16, 46, 10)):
            qa.column_dimensions[col].width = width
        qa.freeze_panes = "A2"

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    final = safe_save(wb, out_path)
    if verbose:
        print(f"已写出 {final}  共 {row_cursor-1} 行  未落格 {warn}  空单元格补救 {recovered}  "
              f"仍有墨未识别 {residual}  低置信度 {low_cells}  序号修复 {len(fixed)}  "
              f"总耗时 {time.time()-t_all:.1f}s")
        if residual_cells:
            print("  有墨但没识别出文字（页/行/列）: " + ", ".join(f"{a}/{b}/{c}" for a, b, c in residual_cells))
        for pno, a, b in page_rows:
            print(f"  page {pno:2d} → 行 {a}–{b}")
    print(f"OUT={final}")
    return final


def safe_save(wb, out_path: str):
    """先写临时文件再替换；目标被 WPS 占用时改用带时间戳的文件名。"""
    out = Path(out_path)
    tmp = out.with_name(out.stem + ".tmp" + out.suffix)
    wb.save(tmp)
    try:
        os.replace(tmp, out)
        return out
    except PermissionError:
        alt = out.with_name(f"{out.stem}-{time.strftime('%H%M%S')}{out.suffix}")
        os.replace(tmp, alt)
        print(f"目标文件被占用，改存 {alt}")
        return alt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--pages", default=None, help="如 1-3 或 1,2,5")
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--workers", type=int, default=None, help="OCR 并行进程数（默认自动）")
    ap.add_argument("--no-recover", action="store_true", help="关闭空单元格二次识别")
    ap.add_argument("--no-mark", action="store_true", help="不标黄低置信度格")
    ap.add_argument("--no-repair-seq", action="store_true", help="不修复 OCR 误读的序号")
    a = ap.parse_args()
    out = a.out or str(Path(a.pdf).with_suffix(".xlsx"))
    convert(a.pdf, out, a.pages, a.dpi, repair_seq=not a.no_repair_seq,
            workers=a.workers, recover=not a.no_recover, mark_low=not a.no_mark)


if __name__ == "__main__":
    main()
