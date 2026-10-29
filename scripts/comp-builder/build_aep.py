# -*- coding: utf-8 -*-
"""build_aep.py —— 读 manifest.json,生成一份自包含的 build_<名>.jsx

链路:
    manifest.json  --build_aep.py-->  build_<名>.jsx  --run_ae.ps1-->  .aep + 抽帧

为什么生成 .jsx 而不在 AE 里读 JSON:
    AE 2026 的 ExtendScript 没有 JSON 解析器(没有 JSON.parse)。数据必须以**字面量**内联。

用法:
    python build_aep.py manifest.json -o build_start_page.jsx
    python build_aep.py manifest.json --check-ease     # 只比对缓动源码是否与 tween.jsx 一致
"""

import argparse
import io
import json
import os
import re
import sys

# ============================================================
# ★ 缓动源码:必须与 scripts/expression-tween/tween.jsx 的 TWEEN.EASE **逐字一致**
#   --check-ease 会用正则把两份都归一化再比对。表达式拿不到外部函数,只能拼源码。
# ============================================================
EASE = (
    "function bx(s,a,b){var u=1-s;return 3*u*u*s*a+3*u*s*s*b+s*s*s;}"
    "function by(s,a,b){var u=1-s;return 3*u*u*s*a+3*u*s*s*b+s*s*s;}"
    "function cb(t,a,b,c,d){var lo=0;var hi=1;var s=t;var i;var x;"
    "for(i=0;i<20;i++){x=bx(s,a,c);if(x<t){lo=s;}else{hi=s;}s=(lo+hi)/2;}"
    "return by(s,b,d);}"
)

CURVE = {
    "out": "0.16,1,0.3,1",
    "back": "0.34,1.56,0.64,1",
    "inOut": "0.65,0,0.35,1",
    "linear": "0,0,1,1",
    # 方案5 · 最初经典(取自 835_启动页 的方案5 动效调试 HTML)
    "quartOut": "0.25,1,0.5,1",     # Logo 整体
    "ease": "0.42,0,0.58,1",        # 副标题
}

HERE = os.path.dirname(os.path.abspath(__file__))
TWEEN_JSX = os.path.normpath(os.path.join(HERE, "..", "expression-tween", "tween.jsx"))


# ------------------------------------------------------------
# 表达式构造(与 tween.jsx 的 head/curve 同口径)
# ------------------------------------------------------------
CTRL = "参数控制"


def head(dur, delay, idx=0, stag=None):
    s = 'var C=thisComp.layer("%s");' % CTRL
    s += 'var D=Math.max(0.05,C.effect("%s")(1)/1000);' % dur
    s += 'var S=C.effect("%s")(1)/1000;' % delay
    if stag:
        s += "S+=%d*C.effect(\"%s\")(1)/1000;" % (idx, stag)
    s += "var u=Math.min(1,Math.max(0,(time-S)/D));"
    return s


def curve(key):
    return "var f=cb(u,%s);" % CURVE[key]


def proxy_param(role):
    """role -> (时长滑块名, 延迟滑块名, 错位滑块名 or None)"""
    if role == "icon":
        return "图标时长", "图标延迟", None
    if role == "logo":
        return "文字时长", "文字延迟", "文字错位"
    if role == "tag":
        return "副标题时长", "副标题延迟", "副标题错位"
    if role == "logo_full":
        return "Logo整体时长", "Logo整体延迟", None
    return "文字时长", "文字延迟", "文字错位"


# ------------------------------------------------------------
# 三套方案:role -> [(属性 matchName, 表达式)] + 可选模糊表达式
#   数值是 835_启动页 那批工程的实测取值,单位 px / %
# ------------------------------------------------------------
Y_IN_1152 = 1152.0


def scheme_s1(lyr, m):
    """上浮淡入:位移 + 淡入 + 轻微放大 + 模糊收清"""
    dur, delay, stag = proxy_param(lyr["role"])
    idx = lyr.get("idx", 0)
    h = head(dur, delay, idx, stag)
    f = curve("out")
    dy = {
        "icon": m["iconDy"],
        "logo": m["logoDy"],
        "tag": m["tagDy"],
        "logo_full": m["logoFullDy"],
    }[lyr["role"]]
    props = [
        ("ADBE Position", EASE + h + f + "var dy=%s;var p=value;[p[0],p[1]+dy-dy*f];" % dy),
        ("ADBE Opacity", EASE + h + f + "100*f;"),
    ]
    if lyr["role"] == "icon":
        props.append(("ADBE Scale", EASE + h + f + "var sc=92+8*f;[sc,sc];"))
        return props, EASE + h + f + "%s*(1-f);" % m["blurIcon"]
    if lyr["role"] in ("logo", "logo_full"):
        return props, EASE + h + f + "%s*(1-f);" % m["blurLogo"]
    return props, None


def scheme_s3(lyr, m):
    """弹性缩放:先冲过头再落回(back 曲线,y 超调)"""
    dur, delay, stag = proxy_param(lyr["role"])
    idx = lyr.get("idx", 0)
    h = head(dur, delay, idx, stag)
    f = curve("back")
    g = "var g=cb(Math.min(1,u/0.6),%s);" % CURVE["back"]
    if lyr["role"] == "icon":
        return [
            ("ADBE Scale", EASE + h + f + g + "var sc=50+60*f-10*g;[sc,sc];"),
            ("ADBE Opacity", EASE + h + f + "100*f;"),
        ], EASE + h + curve("out") + "%s*(1-f);" % m["blurIconPop"]
    # 文字:按 idx 奇偶向两侧分开
    dx = m["logoSpread"] if idx % 2 == 0 else -m["logoSpread"]
    return [
        ("ADBE Position", EASE + h + f + "var dx=%s;var p=value;[p[0]+dx-dx*f,p[1]];" % dx),
        ("ADBE Opacity", EASE + h + f + "100*(f>0?1:0);"),
    ], None


def scheme_s5(lyr, m):
    """整体上浮:Logo 整体一条大位移,内部字不动"""
    dur, delay, stag = proxy_param("logo_full")
    h = head(dur, delay, 0, None)
    f = curve("out")
    g = "var h2=cb(Math.min(1,u/0.55),%s);" % CURVE["out"]
    return [
        ("ADBE Position", EASE + h + f + "var dy=%s;var p=value;[p[0],p[1]+dy-dy*f];" % m["logoFullDy"]),
        ("ADBE Opacity", EASE + h + g + "100*h2;"),
    ], EASE + h + g + "%s*(1-h2);" % m["blurLogo"]


SCHEMES = {"s1": scheme_s1, "s3": scheme_s3, "s5": scheme_s5}


def scheme_s5v2(lyr, m):
    """方案5 · 最初经典:整体 Logo 一条大位移 + 缩放 94→100;
    透明度与模糊**在前 55% 收清**,位移/缩放走满 100%。
    Logo 走 Quart-out,副标题走 ease(两个 role 曲线不同,是本方案的特征)
    """
    dur, delay, stag = proxy_param(lyr["role"])
    idx = lyr.get("idx", 0)
    h = head(dur, delay, idx, stag)
    if lyr["role"] == "logo_full":
        f = curve("quartOut")
        g = "var h2=cb(Math.min(1,u/0.55),%s);" % CURVE["quartOut"]
        return [
            ("ADBE Position", EASE + h + f + "var dy=%s;var p=value;[p[0],p[1]+dy-dy*f];" % m["logoFullDy"]),
            ("ADBE Scale", EASE + h + f + "var sc=94+6*f;[sc,sc];"),
            ("ADBE Opacity", EASE + h + g + "100*h2;"),
        ], EASE + h + g + "%s*(1-h2);" % m["blurLogo5"]
    # 副标题(逐字)
    f = curve("ease")
    return [
        ("ADBE Position", EASE + h + f + "var dy=%s;var p=value;[p[0],p[1]+dy-dy*f];" % m["tagDy5"]),
        ("ADBE Opacity", EASE + h + f + "100*f;"),
    ], EASE + h + f + "%s*(1-f);" % m["blurTag5"]


SCHEMES["s5v2"] = scheme_s5v2


# ------------------------------------------------------------
# jsx 片段
# ------------------------------------------------------------
JSX_HEAD = """#target aftereffects
// 由 build_aep.py 生成,不要手改;改 manifest 或生成器后重跑。
// 约定:末尾必须先 L("DONE") 再 app.quit(),run_ae.ps1 靠它判结束。

var LOG_PATH   = %(log)s;
var RENDER_DIR = %(render)s;

var DATA = %(data)s;
"""

JSX_LIB = r"""
// ===== 日志:逐行 open/append/close(File 在 close() 才落盘) =====
function L(s) {
    var f = new File(LOG_PATH);
    f.open("a");
    f.write(new Date().toString() + "  " + s + "\n");
    f.close();
}

function hexToRgb(h) {
    h = h.replace("#", "");
    return [parseInt(h.substr(0, 2), 16) / 255,
            parseInt(h.substr(2, 2), 16) / 255,
            parseInt(h.substr(4, 2), 16) / 255];
}

function importPng(dir, fileName) {
    var f = new File(dir + "/" + fileName);
    if (!f.exists) { L("MISS " + fileName); return null; }
    return app.project.importFile(new ImportOptions(f));
}

function setT(lyr, propName, exprStr) {
    var p = lyr.property("ADBE Transform Group").property(propName);
    p.expression = exprStr;
    p.expressionEnabled = true;
}

function addBlur(lyr, exprStr) {
    var fx = lyr.property("ADBE Effect Parade").addProperty("ADBE Gaussian Blur 2");
    fx.property(3).setValue(1);        // Repeat Edge Pixels
    var p = fx.property(1);            // ★ 中文版:按索引,不按 "Blurriness"
    p.expression = exprStr;
    p.expressionEnabled = true;
}
"""


def js_quote(s):
    """生成 JSON 兼容的 jsx 字面量(双引号、转义反斜杠)"""
    return json.dumps(s, ensure_ascii=False)


# 默认 10 个滑块(旧工程的通用组);清单里写 meta.sliders 可以只保留实际用到的几组,
# 避免在 AE 里留下一排没人读的滑块。
SLIDERS_DEFAULT = [
    ["图标时长", 500], ["图标延迟", 0],
    ["文字时长", 500], ["文字延迟", 0], ["文字错位", 0],
    ["副标题时长", 400], ["副标题延迟", 400], ["副标题错位", 0],
    ["Logo整体时长", 1000], ["Logo整体延迟", 0],
]


def build_jsx(manifest):
    meta = manifest["meta"]
    comp_cfg = meta["comp"]
    aep = meta["aep"]
    asset_dir = meta["asset_dir"]
    log = meta["log"]
    render_dir = meta["render_dir"]
    motion = meta.get("motion", {})
    defaults = {
        "iconDy": 40.96,
        "logoDy": 20.48,
        "tagDy": 20.48,
        "logoFullDy": 116.0,
        "logoSpread": 40.96,
        "blurIcon": 12,
        "blurIconPop": 16,
        "blurLogo": 4,
        # s5v2(方案5 · 最初经典):数值取自调试页 58/16/10/5 在 2048 合成下的 2 倍
        "tagDy5": 32.0,
        "blurLogo5": 20,
        "blurTag5": 10,
    }
    defaults.update(motion)

    data = {
        "comp": comp_cfg,
        "bg": meta.get("bg", "#0F0F11"),
        "aep": aep,
        "assetDir": asset_dir,
        "renderDir": render_dir,
        "comps": manifest["comps"],
    }

    out = io.StringIO()
    out.write(JSX_HEAD % {"log": js_quote(log),
                          "render": js_quote(render_dir),
                          "data": json.dumps(data, ensure_ascii=False, indent=1)})
    out.write(JSX_LIB)

    # ---- main ----
    out.write("\n// ===== main =====\n")
    out.write("app.newProject();\nL(\"newProject ok\");\n")
    out.write("var COMPS = [];\n")
    out.write("var i, j, k, c, cc, lyr, item, p, exprs, blurExpr, props, layerCfg;\n")
    out.write('var ASSET_DIR = DATA.assetDir;\n')
    out.write('var W = DATA.comp.width, H = DATA.comp.height;\n')
    out.write('var DUR = DATA.comp.duration, FPS = DATA.comp.fps;\n')
    out.write("var SLIDERS = %s;\n\n" % json.dumps(meta.get("sliders") or SLIDERS_DEFAULT,
                                                   ensure_ascii=False))

    out.write("for (i = 0; i < DATA.comps.length; i++) {\n")
    out.write("  c = DATA.comps[i];\n")
    out.write("  cc = app.project.items.addComp(c.name, W, H, 1, DUR, FPS);\n")
    out.write('  L("comp " + c.name);\n')
    out.write("  // 背景:置底 + 锁定\n")
    out.write("  var bg = cc.layers.addSolid(hexToRgb(DATA.bg), \"BG\", W, H, 1, DUR);\n")
    out.write("  bg.moveToEnd(); bg.locked = true;\n")
    out.write("  // 参数控制:置顶 null(★ 不能用 solid —— solid 是不透明黑层,会把整幅画面盖住;\n")
    out.write("  //   实测:抽帧 bbox 退化成 (0,0,2048,1152)、pixels 2,358,478)\n")
    out.write("  var ctl = cc.layers.addNull(DUR);\n")
    out.write('  ctl.name = "%s";\n' % CTRL)
    out.write("  ctl.moveToBeginning();\n")
    out.write("  for (j = 0; j < SLIDERS.length; j++) {\n")
    out.write("    var fx = ctl.property(\"ADBE Effect Parade\").addProperty(\"ADBE Slider Control\");\n")
    out.write("    fx.name = SLIDERS[j][0];\n")
    out.write("    fx.property(1).setValue(SLIDERS[j][1]);   // ★ 滑块值按索引 effect(1)\n")
    out.write("  }\n")

    # 每个图层:i 是下标(用于错位),需要把 scheme 与 props 在 Python 侧算好再写成字面量
    out.write("  for (k = 0; k < c.layers.length; k++) {\n")
    out.write("    layerCfg = c.layers[k];\n")
    out.write("    item = importPng(ASSET_DIR, layerCfg.file);\n")
    out.write("    if (item === null) { continue; }\n")
    out.write("    lyr = cc.layers.add(item);\n")
    out.write("    lyr.name = layerCfg.name;\n")
    out.write("    lyr.property(\"ADBE Transform Group\").property(\"ADBE Position\")\n")
    out.write("       .setValue([layerCfg.cx, layerCfg.cy]);\n")
    out.write("    var spec = layerCfg.props;\n")
    out.write("    for (j = 0; j < spec.length; j++) {\n")
    out.write("      setT(lyr, spec[j][0], spec[j][1]);\n")
    out.write("    }\n")
    out.write("    if (layerCfg.blur) { addBlur(lyr, layerCfg.blur); }\n")
    out.write("  }\n")
    out.write("  L(\"  layers=\" + cc.numLayers);\n")
    out.write("  COMPS.push(cc);\n")
    out.write("}\n\n")

    # 表达式体检
    out.write(r"""// ===== 表达式错误体检(递归遍历属性树) =====
var EXPR_ERRORS = [];
function scanExpr(prop, path) {
    var n = 0;
    try { n = prop.numProperties; } catch (e1) { n = 0; }
    if (n > 0) {
        for (var q = 1; q <= n; q++) {
            var child = null;
            try { child = prop.property(q); } catch (e2) { child = null; }
            if (child !== null) { scanExpr(child, path + "/" + child.name); }
        }
    } else {
        var err = null;
        try { err = prop.expressionError; } catch (e3) { err = null; }
        // ★ 必须判 "是字符串且非空":CompItem 也有 expressionError,值是 undefined,
        //   写成 err !== "" && err !== null 会把每个合成各报一条假错(实测 3 条)。
        if (typeof err === "string" && err.length > 0) { EXPR_ERRORS.push(path + " :: " + err); }
    }
}
for (i = 0; i < COMPS.length; i++) { scanExpr(COMPS[i], COMPS[i].name); }
L("expressionError count=" + EXPR_ERRORS.length);
for (i = 0; i < EXPR_ERRORS.length; i++) { L("EXPR_ERR " + EXPR_ERRORS[i]); }

""")

    # 抽帧
    out.write(r"""// ===== 抽帧:异步,必须等 =====
// 文件名里的数字是**毫秒**(t=0.12s -> _t120.png),避免"这到底是帧号还是时间"的歧义。
var d = new Folder(DATA.renderDir);
if (!d.exists) { d.create(); }
var t, fname, fobj;
for (i = 0; i < COMPS.length; i++) {
    var times = DATA.comps[i].shoot;
    if (!times) { continue; }
    COMPS[i].openInViewer();
    for (t = 0; t < times.length; t++) {
        fname = DATA.renderDir + "/c" + (i + 1) + "_t" + Math.round(times[t] * 1000) + ".png";
        fobj = new File(fname);
        COMPS[i].saveFrameToPng(times[t], fobj);
        $.sleep(900);                                  // 不等 => 日志成功、磁盘没文件
        L("frame " + fname + " exists=" + (new File(fname)).exists);
    }
}

// ===== 存盘 + 收尾 =====
app.project.save(new File(DATA.aep));
$.sleep(1500);
var outFile = new File(DATA.aep);
L("saved " + DATA.aep + " exists=" + outFile.exists + " bytes=" + outFile.length);
L("DONE");
$.sleep(2500);
app.quit();
""")
    return out.getvalue()


# ------------------------------------------------------------
def prepare(manifest):
    """把每层的 props/blur 预先算好,内联进 DATA(jsx 侧不做任何逻辑决策)"""
    m = {
        "iconDy": 40.96, "logoDy": 20.48, "tagDy": 20.48, "logoFullDy": 116.0,
        "logoSpread": 40.96, "blurIcon": 12, "blurIconPop": 16, "blurLogo": 4,
        "tagDy5": 32.0, "blurLogo5": 20, "blurTag5": 10,
    }
    m.update(manifest["meta"].get("motion", {}))
    for comp in manifest["comps"]:
        scheme = comp.get("scheme", "s1")
        if scheme not in SCHEMES:
            raise SystemExit("未知方案: %s(可选 %s)" % (scheme, "/".join(SCHEMES)))
        for lyr in comp["layers"]:
            props, blur = SCHEMES[scheme](lyr, m)
            lyr["props"] = [[name, expr] for name, expr in props]
            if blur:
                lyr["blur"] = blur
    return manifest


def extract_ease(js_text):
    m = re.search(r"var EASE\s*=\s*(.*?);\s*\n", js_text, re.S)
    if not m:
        return None
    parts = re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1))
    return "".join(parts)


def check_ease():
    if not os.path.exists(TWEEN_JSX):
        print("SKIP: 找不到 %s" % TWEEN_JSX)
        return 2
    with open(TWEEN_JSX, encoding="utf-8-sig") as fh:
        other = extract_ease(fh.read())
    if other is None:
        print("FAIL: tween.jsx 里找不到 `var EASE = ...`")
        return 1
    if other == EASE:
        print("OK: 缓动源码与 tween.jsx 逐字一致(%d 字符)" % len(EASE))
        return 0
    print("FAIL: 缓动源码不一致")
    for i, (a, b) in enumerate(zip(EASE, other)):
        if a != b:
            print("  首个差异 @%d: build_aep=%r  tween.jsx=%r" % (i, a, b))
            break
    print("  长度 build_aep=%d tween.jsx=%d" % (len(EASE), len(other)))
    return 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest", nargs="?", help="manifest.json 路径")
    ap.add_argument("-o", "--out", default=None, help="输出 .jsx 路径")
    ap.add_argument("--check-ease", action="store_true", help="只比对缓动源码")
    args = ap.parse_args()

    if args.check_ease:
        sys.exit(check_ease())
    if not args.manifest:
        ap.error("需要 manifest.json")

    with open(args.manifest, encoding="utf-8-sig") as fh:
        manifest = json.load(fh)
    prepare(manifest)

    jsx = build_jsx(manifest)
    out_path = args.out or os.path.splitext(args.manifest)[0] + ".jsx"
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(jsx)

    print("生成 %s(%d 字符)" % (out_path, len(jsx)))
    for comp in manifest["comps"]:
        print("  %-24s scheme=%s layers=%d" %
              (comp["name"], comp.get("scheme", "s1"), len(comp["layers"])))


if __name__ == "__main__":
    main()
