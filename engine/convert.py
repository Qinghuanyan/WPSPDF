# -*- coding: utf-8 -*-
"""PDF（文字已转曲）→ xlsx 转换器 v1

管线：
  1) 矢量框线 → 行列网格（grid.py，坐标精确）
  2) 整页栅格化 → RapidOCR（det+rec）→ 文本框
  3) 文本框中心落格 → 单元格文本（多行按 y 排序拼接）
  4) openpyxl 写出，列宽按网格宽度、行高按网格高度

用法：
  py -3 engine/convert.py "输入.pdf" -o "输出.xlsx" [--pages 1-3] [--dpi 200]
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import fitz
import numpy as np
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from grid import page_grid, locate  # noqa: E402


class Ocr:
    def __init__(self):
        from rapidocr_onnxruntime import RapidOCR
        self.engine = RapidOCR()

    def page(self, page: fitz.Page, dpi: int):
        """返回 [(cx, cy, text, score)]，坐标为 PDF point。"""
        pix = page.get_pixmap(dpi=dpi)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.n == 4:
            img = img[:, :, :3]
        res, _ = self.engine(img)
        scale = page.rect.width / pix.width
        out = []
        for item in (res or []):
            box, text, score = item[0], item[1], item[2]
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            out.append((sum(xs) / 4.0 * scale, sum(ys) / 4.0 * scale, text.strip(), float(score)))
        return out


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


def convert(pdf_path: str, out_path: str, pages_spec: str | None = None, dpi: int = 200, verbose=True):
    doc = fitz.open(pdf_path)
    pages = parse_pages(pages_spec, doc.page_count)
    ocr = Ocr()
    wb = Workbook()
    ws = wb.active
    ws.title = "数据"

    row_cursor = 1
    col_widths: dict[int, float] = {}
    warn = 0

    for pno in pages:
        page = doc[pno]
        ys, xs = page_grid(page)
        if len(ys) < 2 or len(xs) < 2:
            if verbose:
                print(f"[page {pno+1}] 未识别到网格，跳过", file=sys.stderr)
            continue
        t0 = time.time()
        texts = ocr.page(page, dpi)
        cells: dict[tuple[int, int], list] = {}
        for cx, cy, text, score in texts:
            hit = locate(cx, cy, ys, xs)
            if not hit:
                warn += 1
                continue
            cells.setdefault(hit, []).append((cy, cx, text))
        nrow = len(ys) - 1
        ncol = len(xs) - 1
        if verbose:
            print(f"[page {pno+1}] 网格 {nrow}行 x {ncol}列  OCR {len(texts)}块  {time.time()-t0:.1f}s")

        for i in range(nrow):
            for j in range(ncol):
                vals = sorted(cells.get((i, j), []))
                txt = "".join(v[2] for v in vals)
                if txt:
                    ws.cell(row=row_cursor + i, column=j + 1, value=txt)
            # 列宽（只记一次，按该页首行）
            for j in range(ncol):
                w = xs[j + 1] - xs[j]
                col_widths[j] = max(col_widths.get(j, 0), w)
        row_cursor += nrow

    for j, w in col_widths.items():
        # points → 字符宽度近似
        ws.column_dimensions[get_column_letter(j + 1)].width = max(6, min(60, w / 5.2))
    for row in ws.iter_rows():
        for c in row:
            c.font = Font(name="宋体", size=9)
            c.alignment = Alignment(horizontal="left", vertical="center", wrap_text=False)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    final = safe_save(wb, out_path)
    if verbose:
        print(f"已写出 {final}  共 {row_cursor-1} 行  未落格文本块 {warn}")
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
    a = ap.parse_args()
    out = a.out or str(Path(a.pdf).with_suffix(".xlsx"))
    convert(a.pdf, out, a.pages, a.dpi)


if __name__ == "__main__":
    main()
