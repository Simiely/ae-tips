# -*- coding: utf-8 -*-
"""compare_curve.py —— 把 probe_curve.jsx 采到的实际值与**解析曲线**逐点对表

用法:
    python probe_curve.jsx 先跑一遍(得到 pipe 分隔的日志),然后:
    python compare_curve.py <日志> --profile s5v2 [--tol 0.05]

判据:
    位置偏差 ≤ tol(px)、缩放 / 不透明度 ≤ tol(%)、模糊 ≤ tol  => PASS
    另外两条硬检查:
      [a] 末尾两帧必须**逐位相等**(动画收干净了,否则"静止值"这个基准不可信)
      [b] 方案声明"透明度/模糊前 55% 到位"时,u≥55% 之后必须 opacity=100、blur=0,
          而位移仍未到终点(>1px) —— 这条能区分"真的分段"和"整体乘 0.55"

⚠ 为什么不比绝对坐标:绝对坐标要靠 cy 这个外部常数;用**末帧作为静止基准**,
   只比"还差多少像素",就不需要 cy,也不会把"整体摆偏"误判成"曲线错"。
"""

import argparse
import io
import re
import sys

# 方案参数(与 build_aep.py 的 SCHEMES 同口径)
PROFILES = {
    "s5v2": {
        "logo": {"dur": 0.5, "delay": 0.0, "dy": 116.0,
                 "scale_from": 94.0, "scale_to": 100.0,
                 "blur": 20.0, "hold": 0.55, "curve": "quartOut"},
        "tag": {"dur": 0.4, "delay": 0.1, "dy": 32.0,
                "blur": 10.0, "curve": "ease"},
    },
}

CURVES = {
    "out": (0.16, 1, 0.3, 1),
    "back": (0.34, 1.56, 0.64, 1),
    "inOut": (0.65, 0, 0.35, 1),
    "linear": (0, 0, 1, 1),
    "quartOut": (0.25, 1, 0.5, 1),
    "ease": (0.42, 0, 0.58, 1),
}


def cb(t, x1, y1, x2, y2):
    """与表达式里的 cb() 同一算法(二分 40 次,精度远高于 20 次)"""
    t = min(1.0, max(0.0, t))
    lo, hi = 0.0, 1.0
    for _ in range(40):
        s = (lo + hi) / 2.0
        x = 3 * (1 - s) ** 2 * s * x1 + 3 * (1 - s) * s * s * x2 + s ** 3
        if x < t:
            lo = s
        else:
            hi = s
    s = (lo + hi) / 2.0
    return 3 * (1 - s) ** 2 * s * y1 + 3 * (1 - s) * s * s * y2 + s ** 3


def u_of(t, p):
    return min(1.0, max(0.0, (t - p["delay"]) / p["dur"]))


def expected(kind, t, p):
    """返回 (dy_remaining, scale or None, opacity, blur)"""
    u = u_of(t, p)
    f = cb(u, *CURVES[p["curve"]])
    dy = p["dy"] * (1.0 - f)
    if kind == "logo":
        h = cb(min(1.0, u / p["hold"]), *CURVES[p["curve"]])
        return dy, p["scale_from"] + (p["scale_to"] - p["scale_from"]) * f, 100.0 * h, p["blur"] * (1.0 - h)
    return dy, None, 100.0 * f, p["blur"] * (1.0 - f)


SAMPLE = re.compile(r"S\|(.*)\|(logo|tag)\|([-\d.]+)\|([-\d.]+)\|([-\d.]+|[-])\|([-\d.]+)\|([-\d.]+)$")


def load(log_path):
    groups = {}
    for line in io.open(log_path, encoding="utf-8-sig"):
        m = SAMPLE.search(line.strip())
        if not m:
            continue
        comp, kind = m.group(1), m.group(2)
        t, y = float(m.group(3)), float(m.group(4))
        sc = None if m.group(5) == "-" else float(m.group(5))
        op, bl = float(m.group(6)), float(m.group(7))
        groups.setdefault((comp, kind), []).append((t, y, sc, op, bl))
    for k in groups:
        groups[k].sort()
    return groups


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    ap.add_argument("--profile", default="s5v2", choices=sorted(PROFILES))
    ap.add_argument("--tol", type=float, default=0.05,
                    help="位置 px / 其余同单位的容差")
    args = ap.parse_args()

    prof = PROFILES[args.profile]
    groups = load(args.log)
    if not groups:
        print("FAIL: 日志里没有 S|... 采样行(probe_curve.jsx 跑了吗?)")
        return 2

    fail = 0
    worst = 0.0
    per_comp = {}
    printed_header = False

    for (comp, kind), rows in sorted(groups.items()):
        p = prof[kind]
        # [a] 末两帧必须相等(静止基准可信)
        if len(rows) >= 2 and abs(rows[-1][1] - rows[-2][1]) > 0.01:
            print("FAIL %s/%s: 末两帧位置不等(%.3f vs %.3f),动画没停" %
                  (comp, kind, rows[-2][1], rows[-1][1]))
            fail += 1
        rest_y = rows[-1][1]

        if not printed_header and kind == "logo":
            print("%-16s %-5s %-6s | %-26s | %-8s | %-9s | %-8s" %
                  ("comp", "obj", "t", "dy剩余 实测/理论/差", "scale差", "opacity差", "blur差"))
            printed_header = True

        for t, y, sc, op, bl in rows:
            dy_m = y - rest_y          # 元素从下方上浮:当前 y 比静止位置大 ⇒ "还差多少像素"
            e_dy, e_sc, e_op, e_bl = expected(kind, t, p)
            d_dy = abs(dy_m - e_dy)
            d_sc = 0.0 if (e_sc is None or sc is None) else abs(sc - e_sc)
            d_op, d_bl = abs(op - e_op), abs(bl - e_bl)
            w = max(d_dy, d_sc, d_op, d_bl)
            worst = max(worst, w)
            per_comp[comp] = max(per_comp.get(comp, 0.0), w)
            if comp == sorted({c for c, _ in groups})[0] and kind == "logo":
                print("%-16s %-5s %-6.3f | %9.3f/%9.3f/%7.3f | %8.4f | %9.4f | %8.4f" %
                      (comp, kind, t, dy_m, e_dy, d_dy, d_sc, d_op, d_bl))
            if w > args.tol:
                print("FAIL %s/%s t=%.3f: 偏差 %.4f > tol %.4f" % (comp, kind, t, w, args.tol))
                fail += 1

        # [b] 分段检查:u>=hold 之后 opacity/blur 必须到位,而位移还在走
        if kind == "logo" and "hold" in p:
            done_t = p["delay"] + p["hold"] * p["dur"]
            hits = [r for r in rows if r[0] >= done_t - 1e-6]
            if not hits:
                print("SKIP %s: 采样点没覆盖 %.3fs(分段落点)之后的时刻" % (comp, done_t))
            else:
                t0 = hits[0]
                dy_m = t0[1] - rest_y
                ok = abs(t0[3] - 100.0) <= args.tol and abs(t0[4]) <= max(args.tol, 0.01) and dy_m > 1.0
                print("  [分段] %s t=%.3f(opacity=%.2f blur=%.2f 位移余%.2fpx)> %s" %
                      (comp, t0[0], t0[3], t0[4], dy_m, "OK" if ok else "FAIL"))
                if not ok:
                    fail += 1

    print()
    for comp in sorted(per_comp):
        print("%-24s 最大偏差 = %.4f" % (comp, per_comp[comp]))
    print("总最大偏差 = %.4f(tol=%.3f)" % (worst, args.tol))
    print("FAIL=%d  采样组=%d  方案=%s" % (fail, len(groups), args.profile))
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
