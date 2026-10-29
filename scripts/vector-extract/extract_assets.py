# -*- coding: utf-8 -*-
"""extract_assets.py —— 从 .ai / .pdf 设计稿拆出透明 PNG 元素 + elements.json

适用前提:**统一深色底 + 亮色图形**。原理是"背景反解":
    渲染页 -> 取背景色(四角中位数) -> 与背景做逐像素差 -> 差值越大越不透明
    alpha = min(1, diff / norm),norm 取单元格内 diff 的 99.5 分位
浅底 / 反色 / 多色渐变背景**不适用**,要另做(见 README「局限」)。

两种取单元格方式:
  ① --cells cells.json   显式给框(推荐,最可控;逐字拆分也靠它)
  ② 自动:先按行投影分带,再在带内按列间隙切块(--gap)

用法:
    python extract_assets.py page.pdf --out out/QQ音乐 --prefix QQ --scale 2 --pad 56
    python extract_assets.py page.pdf --out out/QQ音乐 --cells cells.json --scale 2 --pad 56

cells.json:
    [ {"name": "icon",  "bbox": [x0,y0,x1,y1]},
      {"name": "logo_Q","bbox": [...]} ]        # bbox 用**1x 页面坐标**(pt)
"""

import argparse
import io
import json
import os
import re
import sys

import numpy as np
from PIL import Image

try:
    import pymupdf as fitz
except ImportError:                      # 老版本只有 fitz 这个名字
    import fitz


def render(page, scale):
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    return np.array(img)


def detect_bg(img):
    corners = np.concatenate([
        img[0:4, 0:4].reshape(-1, 3), img[0:4, -4:].reshape(-1, 3),
        img[-4:, 0:4].reshape(-1, 3), img[-4:, -4:].reshape(-1, 3),
    ])
    return np.median(corners, axis=0).astype(np.int16)


def hex_of(rgb):
    return "#%02X%02X%02X" % tuple(int(round(v)) for v in rgb)


def runs_of(flag, min_len=1):
    """把一维布尔数组切成 [start, end) 区间"""
    out, start = [], None
    for i, v in enumerate(flag):
        if v and start is None:
            start = i
        elif not v and start is not None:
            if i - start >= min_len:
                out.append((start, i))
            start = None
    if start is not None and len(flag) - start >= min_len:
        out.append((start, len(flag)))
    return out


def auto_cells(mask, gap, min_area):
    """行投影分带 -> 带内列投影切块"""
    h, w = mask.shape
    bands = runs_of(mask.sum(axis=1) > 0, min_len=2)
    cells = []
    for y0, y1 in bands:
        band = mask[y0:y1]
        cols = runs_of(band.sum(axis=0) > 0, min_len=1)
        merged = []
        for x0, x1 in cols:
            if merged and x0 - merged[-1][1] < gap:
                merged[-1] = (merged[-1][0], x1)
            else:
                merged.append((x0, x1))
        for x0, x1 in merged:
            sub = band[:, x0:x1]
            if int(sub.sum()) < min_area:
                continue
            cells.append((x0, y0, x1, y1))
    return cells


def extract_one(img, bg, box1x, scale, out_scale, pad, thresh, unpremul):
    x0, y0, x1, y1 = [int(round(v * scale)) for v in box1x]
    x0 = max(0, x0); y0 = max(0, y0)
    x1 = min(img.shape[1], x1); y1 = min(img.shape[0], y1)
    crop = img[y0:y1, x0:x1].astype(np.int16)
    diff = np.abs(crop - bg).max(axis=2).astype(np.float32)

    # 只在"有内容"的像素上取归一化基准,避免整块空背景把分位拉低
    lit = diff[diff > thresh]
    norm = float(np.percentile(lit, 99.5)) if lit.size else 255.0
    norm = max(norm, 1.0)
    alpha = np.clip(diff / norm, 0.0, 1.0)

    rgb = crop.astype(np.float32)
    if unpremul:
        # F = B + (C - B)/a : 把半透明边缘还原成"该元素本来的颜色"
        safe = np.maximum(alpha, 0.02)[..., None]
        rgb = bg.astype(np.float32) + (rgb - bg.astype(np.float32)) / safe
        rgb = np.clip(rgb, 0, 255)
    rgba = np.dstack([rgb.astype(np.uint8), (alpha * 255).round().astype(np.uint8)])

    # ① 裁到可见内容 ② 缩到**输出尺度**(合成像素空间)③ 补对称透明边距
    #   顺序不能反:先补边距再缩放会把边距一起缩掉,换算全错
    ys, xs = np.nonzero(alpha > 0.02)
    if ys.size:
        rgba = rgba[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    if abs(out_scale - scale) > 1e-9:
        hh, ww = rgba.shape[:2]
        tw = max(1, int(round(ww * out_scale / scale)))
        th = max(1, int(round(hh * out_scale / scale)))
        rgba = np.array(Image.fromarray(rgba, mode="RGBA").resize((tw, th), Image.LANCZOS))
    hh, ww = rgba.shape[:2]
    canvas = np.zeros((hh + pad * 2, ww + pad * 2, 4), dtype=np.uint8)
    canvas[pad:pad + hh, pad:pad + ww] = rgba
    return canvas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--out", required=True, help="输出目录(每个元素一个 PNG)")
    ap.add_argument("--scale", type=float, default=2.0, help="渲染倍率(超采样,提高边缘AA)")
    ap.add_argument("--out-scale", type=float, default=1.0, help="输出像素相对页面 pt 的倍率(应与合成像素空间一致)")
    ap.add_argument("--pad", type=int, default=56, help="四周透明边距(**输出**像素)")
    ap.add_argument("--thresh", type=int, default=8, help="非背景阈值 0-255")
    ap.add_argument("--gap", type=int, default=16, help="自动切块的列间隙(1x pt)")
    ap.add_argument("--min-area", type=int, default=400, help="自动切块的最小墨迹面积(1x)")
    ap.add_argument("--cells", default=None, help="cells.json(1x 页面坐标)")
    ap.add_argument("--prefix", default="", help="输出文件名前缀")
    ap.add_argument("--unpremultiply", action="store_true", help="半透明边缘反预乘")
    ap.add_argument("--page", type=int, default=0)
    args = ap.parse_args()

    doc = fitz.open(args.pdf)
    page = doc[args.page]
    img = render(page, args.scale)
    bg = detect_bg(img)
    print("page %dx%d(1x %.1fx%.1f)  bg=%s" %
          (img.shape[1], img.shape[0], page.rect.width, page.rect.height, hex_of(bg)))

    mask = (np.abs(img.astype(np.int16) - bg).max(axis=2) > args.thresh)

    if args.cells:
        with open(args.cells, encoding="utf-8-sig") as fh:
            spec = json.load(fh)
        cells = [(c["name"], c["bbox"]) for c in spec]
    else:
        cells = [("cell%02d" % (i + 1), [b[0] / args.scale, b[1] / args.scale,
                                         b[2] / args.scale, b[3] / args.scale])
                 for i, b in enumerate(auto_cells(mask, args.gap, args.min_area))]

    os.makedirs(args.out, exist_ok=True)
    elements = []
    for name, box in cells:
        safe_name = re.sub(r"[^\w\-.]+", "_", name)
        rgba = extract_one(img, bg, box, args.scale, args.out_scale, args.pad,
                           args.thresh, args.unpremultiply)
        fn = (args.prefix + "_" if args.prefix else "") + safe_name + ".png"
        path = os.path.join(args.out, fn)
        Image.fromarray(rgba).save(path)
        h, w = rgba.shape[:2]
        cx = (box[0] + box[2]) / 2.0 * args.out_scale
        cy = (box[1] + box[3]) / 2.0 * args.out_scale
        elements.append({"file": fn, "name": name, "w": w, "h": h,
                         "cx": round(cx, 2), "cy": round(cy, 2)})
        print("  %-14s %4dx%-4d  cx=%.2f cy=%.2f" % (name, w, h, cx, cy))

    meta = {
        "meta": {"source": os.path.basename(args.pdf), "page": args.page,
                 "scale": args.scale, "out_scale": args.out_scale, "pad": args.pad,
                 "bg": hex_of(bg), "page_w": img.shape[1], "page_h": img.shape[0]},
        "elements": elements,
    }
    out_json = os.path.join(args.out, "elements.json")
    with io.open(out_json, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(meta, ensure_ascii=False, indent=2))
    print("-> %s(%d 个元素)" % (out_json, len(elements)))


if __name__ == "__main__":
    sys.exit(main())
