# -*- coding: utf-8 -*-
"""从"文字转曲"的 PDF 里抽出表格网格（行列边界）。

依据：这类 WPS/macOS 导出的 PDF 虽然丢了文本层，但**表格框线仍是矢量**，
所以行列坐标可以精确得到（不受 OCR 误差影响）。

注意：WPS 会把同一批线条打包进**一个 drawing 对象**里（dr["rect"] 是整张表的外框），
所以必须遍历 dr["items"] 里的线段，而不是用 dr["rect"] 判断。
"""
from __future__ import annotations

from typing import List, Tuple

import fitz


def _cluster(values: List[float], tol: float = 1.5) -> List[float]:
    out: List[List[float]] = []
    for v in sorted(values):
        if out and abs(v - out[-1][-1]) <= tol:
            out[-1].append(v)
        else:
            out.append([v])
    return [sum(g) / len(g) for g in out]


def page_rules(page: fitz.Page, min_len: float = 8.0):
    """返回 (横向线段列表[(y,x0,x1)], 纵向线段列表[(x,y0,y1)])。"""
    hs: List[Tuple[float, float, float]] = []
    vs: List[Tuple[float, float, float]] = []
    for dr in page.get_drawings():
        for it in dr["items"]:
            t = it[0]
            if t == "l":
                p1, p2 = it[1], it[2]
                if abs(p1.y - p2.y) <= 0.6 and abs(p2.x - p1.x) >= min_len:
                    hs.append(((p1.y + p2.y) / 2.0, min(p1.x, p2.x), max(p1.x, p2.x)))
                elif abs(p1.x - p2.x) <= 0.6 and abs(p2.y - p1.y) >= min_len:
                    vs.append(((p1.x + p2.x) / 2.0, min(p1.y, p2.y), max(p1.y, p2.y)))
            elif t == "re":
                r = it[1]
                if r.height <= 1.6 and r.width >= min_len:
                    hs.append(((r.y0 + r.y1) / 2.0, r.x0, r.x1))
                elif r.width <= 1.6 and r.height >= min_len:
                    vs.append(((r.x0 + r.x1) / 2.0, r.y0, r.y1))
    return hs, vs


def page_grid(page: fitz.Page, min_len: float = 8.0, xs_override=None) -> Tuple[List[float], List[float]]:
    hs, vs = page_rules(page, min_len)
    ys = _cluster([h[0] for h in hs])
    xs = _cluster([v[0] for v in vs])
    if xs_override is not None:
        xs = list(xs_override)
    return ys, xs


def union_xs(pages, tol: float = 2.0) -> List[float]:
    """跨页并集列边界。

    多页表格里常有「某一页的末列右边框没画」的情况：文字在，竖线缺，
    该列就会被当成网格外丢字（本项目第 2–18 页的「正式答辩时段」正是如此）。
    把各页竖线 x 取并集，得到整份文档的规范列边界。
    """
    vals: List[float] = []
    for pg in pages:
        vals.extend(v[0] for v in page_rules(pg)[1])
    return _cluster(vals, tol)


def xs_is_subset(page_xs: List[float], canon: List[float], tol: float = 2.0) -> bool:
    """页内列边界是否全部落在规范边界里。

    是 → 说明该页只是「少画了几条线」，可安全用规范边界补齐；
    否 → 该页版式确实不同，保持原样，不要硬套。
    """
    return all(any(abs(x - c) <= tol for c in canon) for x in page_xs)


def locate(x: float, y: float, ys: List[float], xs: List[float]):
    import bisect
    if not (ys and xs):
        return None
    if not (ys[0] <= y <= ys[-1] and xs[0] <= x <= xs[-1]):
        return None
    r = min(max(bisect.bisect_right(ys, y) - 1, 0), len(ys) - 2)
    c = min(max(bisect.bisect_right(xs, x) - 1, 0), len(xs) - 2)
    return r, c


def vertical_rules(page: fitz.Page) -> List[Tuple[float, float, float]]:
    return page_rules(page)[1]


def has_vline_between(vlines, x: float, y0: float, y1: float, tol: float = 1.5) -> bool:
    for (vx, vy0, vy1) in vlines:
        if abs(vx - x) <= tol and vy0 <= y0 + tol and vy1 >= y1 - tol:
            return True
    return False
