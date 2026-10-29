# -*- coding: utf-8 -*-
"""verify_frames.py —— 抽帧核验:非背景 bbox / 像素数 / 联系表 / 与期望包围盒比对

判据(全部可证伪):
  [0] 每张 PNG 必须存在且非全背景(pixels > 0)
  [1] 同一合成的像素数应随时序**单调不减**(入场动画),除非方案本身有回弹
  [2] 末帧 bbox 必须落在期望包围盒 ±tol 内(期望来自设计稿量出的元素包围盒)

用法:
    python verify_frames.py <render_dir> --bg 0F0F11
    python verify_frames.py <render_dir> --bg 0F0F11 --expect expects.json --contact contact.png
    python verify_frames.py <render_dir> --bg 0F0F11 --expect expects.json --strict-monotonic
"""

import argparse
import glob
import json
import os
import re
import sys

import numpy as np
from PIL import Image

FRAME_RE = re.compile(r"^(c\d+)_t(\d+)\.png$")


def hex_rgb(h):
    h = h.lstrip("#")
    return np.array([int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)], dtype=np.int16)


def analyze(path, bg, thresh):
    im = Image.open(path).convert("RGB")
    a = np.asarray(im).astype(np.int16)
    diff = np.abs(a - bg).max(axis=2)          # 与背景的最大通道差
    mask = diff > thresh
    n = int(mask.sum())
    if n == 0:
        return im.size, (0, 0, 0, 0), 0
    ys, xs = np.nonzero(mask)
    return im.size, (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1), n


def load_frames(render_dir):
    """按 c<N> 分组,组内按时间升序"""
    groups = {}
    for p in glob.glob(os.path.join(render_dir, "*.png")):
        m = FRAME_RE.match(os.path.basename(p))
        if not m:
            continue
        groups.setdefault(m.group(1), []).append((int(m.group(2)), p))
    for k in groups:
        groups[k].sort()
    return groups


def contact_sheet(rows, out_path, thumb_w=340):
    """把 (prefix, t, path) 拼成联系表,每合成一行"""
    if not rows:
        return
    cells = []
    for _, _, p in rows:
        im = Image.open(p).convert("RGB")
        ratio = thumb_w / float(im.width)
        cells.append(im.resize((thumb_w, max(1, int(im.height * ratio))), Image.LANCZOS))
    th = cells[0].height

    per_row = {}
    for (prefix, t, p), cell in zip(rows, cells):
        per_row.setdefault(prefix, []).append(cell)
    ncol = max(len(v) for v in per_row.values())
    sheet = Image.new("RGB", (thumb_w * ncol, th * len(per_row)), (24, 24, 26))
    for r, (prefix, imgs) in enumerate(sorted(per_row.items())):
        for c, cell in enumerate(imgs):
            sheet.paste(cell, (c * thumb_w, r * th))
    sheet.save(out_path)
    print("contact sheet -> %s (%dx%d)" % (out_path, sheet.width, sheet.height))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("render_dir")
    ap.add_argument("--bg", default="0F0F11", help="背景十六进制,不带 #")
    ap.add_argument("--thresh", type=int, default=6, help="非背景阈值(0-255),默认 6")
    ap.add_argument("--expect", default=None, help="expects.json")
    ap.add_argument("--tol", type=int, default=4, help="末帧 bbox 容差 px")
    ap.add_argument("--contact", default=None)
    ap.add_argument("--strict-monotonic", action="store_true",
                    help="强制要求像素数单调不减(有回弹/消失的方案不要开;"
                         "★ 模糊入场也别开 —— 模糊扩散会让中段像素数比终帧还多)")
    ap.add_argument("--allow-empty-start", action="store_true",
                    help="允许首帧为空(入场从 opacity=0 起步的方案)")
    args = ap.parse_args()

    bg = hex_rgb(args.bg)
    groups = load_frames(args.render_dir)
    if not groups:
        print("FAIL: %s 下没有 c<N>_t<T>.png" % args.render_dir)
        return 2

    expects = {}
    if args.expect:
        with open(args.expect, encoding="utf-8-sig") as fh:
            expects = json.load(fh)

    fail = 0
    rows_for_sheet = []
    print("%-4s %-6s %-11s %-22s %8s  %s" % ("comp", "t", "size", "bbox(x0,y0,x1,y1)", "pixels", "note"))

    for prefix in sorted(groups, key=lambda s: int(s[1:])):
        frames = groups[prefix]
        counts = []
        last = None
        for t, path in frames:
            size, bbox, n = analyze(path, bg, args.thresh)
            counts.append(n)
            last = (t, size, bbox, n)
            rows_for_sheet.append((prefix, t, path))
            note = ""
            if n == 0:
                if args.allow_empty_start and t == frames[0][0]:
                    note = "首帧全透明(已放行)"
                else:
                    note = "全背景?"
                    fail += 1
            print("%-4s %-8.2f %-11s %-22s %8d  %s" %
                  (prefix, t / 1000.0, "%dx%d" % size, str(bbox), n, note))

        if args.strict_monotonic:
            for i in range(1, len(counts)):
                if counts[i] + 1 < counts[i - 1]:
                    print("FAIL %s: 像素数在 t=%.3f 回落(%d -> %d)"
                          % (prefix, frames[i][0] / 1000.0, counts[i - 1], counts[i]))
                    fail += 1

        exp = expects.get(prefix)
        if exp:
            t, size, bbox, n = last
            want = exp["bbox"]
            tol = exp.get("tol", args.tol)
            ok = (abs(bbox[0] - want[0]) <= tol and abs(bbox[1] - want[1]) <= tol and
                  abs(bbox[2] - want[2]) <= tol and abs(bbox[3] - want[3]) <= tol)
            print("  expect %-12s 末帧 t=%.3f bbox=%s want=%s tol=%d => %s"
                  % (exp.get("name", ""), t / 1000.0, bbox, want, tol, "OK" if ok else "FAIL"))
            if not ok:
                fail += 1

    if args.contact:
        contact_sheet(rows_for_sheet, args.contact)

    print("\nFAIL=%d  合成数=%d  帧数=%d" % (fail, len(groups), len(rows_for_sheet)))
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
