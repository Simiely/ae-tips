// jsxlib.jsx —— 无头 AE 脚本的公共库(ExtendScript / ES3)
//
// 用法两种:
//   ① 手写脚本里 `#include "jsxlib.jsx"`(同目录或绝对路径)
//   ② 生成器(build_aep.py)把需要的函数**原样内联**进生成的 .jsx —— 推荐,产物单文件可独立跑
//
// ⚠️ 这里定义的函数**不能被表达式调用**。AE 表达式运行在独立沙箱,只认内置对象
//    (time / value / thisComp / Math ...)。缓动函数必须**把源码字符串拼进表达式**,
//    见 ../expression-tween/tween.jsx 与 ../comp-builder/build_aep.py 的 EASE 常量。
//
// ⚠️ 本库所有日志只接受**标量**:把 Property / Viewer / 返回值拼进字符串会让 AE 进程直接消失。

#target aftereffects

// ============ 全局配置(主脚本开头改这三行) ============
var LOG_PATH = "C:/temp/ae_build.log";   // 日志绝对路径,正斜杠
var RENDER_DIR = "C:/temp/ae_render";    // 抽帧输出目录
var FONT = "";                           // 预留:文本图层字体,本库当前不使用

// ============ 日志:必须逐行 open/append/close ============
// File 对象在 close() 时才真正落盘;脚本硬崩 => 缓冲区全丢 => 日志为空 => 看起来像"没跑"。
function L(s) {
    var f = new File(LOG_PATH);
    f.open("a");
    f.write(new Date().toString() + "  " + s + "\n");
    f.close();
}

// ============ 颜色 ============
function hexToRgb(h) {
    h = h.replace("#", "");
    return [
        parseInt(h.substr(0, 2), 16) / 255,
        parseInt(h.substr(2, 2), 16) / 255,
        parseInt(h.substr(4, 2), 16) / 255
    ];
}

// ============ 工程 / 合成 ============
function newProject() {
    app.newProject();
    L("newProject ok");
}

function newComp(name, w, h, dur, fps) {
    var c = app.project.items.addComp(name, w, h, 1, dur, fps);
    L("comp " + name + " " + w + "x" + h + " @" + fps + "fps " + dur + "s");
    return c;
}

// 背景 solid:置底并锁定,避免误选
function addBg(comp, w, h, dur, hex) {
    var rgb = hexToRgb(hex);
    var bg = comp.layers.addSolid(rgb, "BG", w, h, 1, dur);
    bg.moveToEnd();
    bg.locked = true;
    return bg;
}

// 参数控制图层:一组滑块,排在最上
//   sliders = [["图标时长", 500], ["图标延迟", 0], ...]
// ★ 必须用 null 对象,不能用 solid: solid 是不透明黑层,会盖住整幅画面
//   (实测:抽帧 bbox 退化成整帧 (0,0,2048,1152))
function addController(comp, w, h, dur, sliders) {
    var ctl = comp.layers.addNull(dur);
    ctl.name = "参数控制";
    ctl.moveToBeginning();
    ctl.locked = false;
    var i, fx;
    for (i = 0; i < sliders.length; i++) {
        fx = ctl.property("ADBE Effect Parade").addProperty("ADBE Slider Control");
        fx.name = sliders[i][0];
        // ★ 中文界面下 property("Slider") 返回 null,取值一律按索引 effect(1)
        fx.property(1).setValue(sliders[i][1]);
    }
    L("controller sliders=" + sliders.length);
    return ctl;
}

// ============ 素材 ============
function importPng(dir, fileName) {
    var f = new File(dir + "/" + fileName);
    if (!f.exists) {
        L("MISS " + fileName);
        return null;
    }
    return app.project.importFile(new ImportOptions(f));
}

// 把 PNG 放到合成里的 (cx, cy)
//   cx/cy 是**文件中心**(含透明边距)在合成坐标系的位置;透明边距左右不等时要另行补偿
function placeLayer(comp, dir, fileName, layerName, cx, cy) {
    var item = importPng(dir, fileName);
    if (item === null) {
        return null;
    }
    var lyr = comp.layers.add(item);
    lyr.name = layerName;
    lyr.property("ADBE Transform Group").property("ADBE Position").setValue([cx, cy]);
    return lyr;
}

// ============ 表达式 ============
// 变换类:propName 用 matchName —— "ADBE Position" / "ADBE Scale" / "ADBE Opacity" / "ADBE Rotate Z"
function setTransformExpr(layer, propName, exprStr) {
    var p = layer.property("ADBE Transform Group").property(propName);
    p.expression = exprStr;
    p.expressionEnabled = true;
    return p;
}

// 高斯模糊 + 表达式(模糊度按索引 property(1))
// ★ "ADBE Gaussian Blur 2":1=Blurriness  2=Blur Dimensions  3=Repeat Edge Pixels
function addBlur(layer, exprStr) {
    var fx = layer.property("ADBE Effect Parade").addProperty("ADBE Gaussian Blur 2");
    fx.property(3).setValue(1);          // Repeat Edge Pixels = 开,防止边缘透明被吸黑
    var p = fx.property(1);
    p.expression = exprStr;
    p.expressionEnabled = true;
    return fx;
}

// ============ 抽帧(异步,必须等) ============
// times 单位秒;前缀必须 ASCII,中文/空格名会静默不落盘
function shoot(comp, times, outDir, prefix, waitMs) {
    if (!waitMs) {
        waitMs = 900;
    }
    var d = new Folder(outDir);
    if (!d.exists) {
        d.create();
    }
    comp.openInViewer();
    L("openInViewer " + comp.name);
    var i, tt, fn, f;
    for (i = 0; i < times.length; i++) {
        tt = times[i];
        fn = outDir + "/" + prefix + "_t" + Math.round(tt * 100) + ".png";
        f = new File(fn);
        comp.saveFrameToPng(tt, f);      // 只是投递,不是同步写
        $.sleep(waitMs);                 // 不 sleep 就会出现"日志说成功、磁盘没文件"
        L("frame " + fn + " exists=" + (new File(fn)).exists);
    }
}

// ============ 表达式错误体检 ============
var EXPR_ERRORS = [];

function scanExprErrors(prop, path) {
    var n = 0;
    try { n = prop.numProperties; } catch (e1) { n = 0; }
    var i, child;
    if (n > 0) {
        for (i = 1; i <= n; i++) {
            try { child = prop.property(i); } catch (e2) { child = null; }
            if (child !== null) {
                scanExprErrors(child, path + "/" + child.name);
            }
        }
    } else {
        var err = "";
        try { err = prop.expressionError; } catch (e3) { err = ""; }
        if (err !== "" && err !== null) {
            EXPR_ERRORS.push(path + " :: " + err);
        }
    }
}

function reportExprErrors(comps) {
    EXPR_ERRORS = [];
    var i;
    for (i = 0; i < comps.length; i++) {
        scanExprErrors(comps[i], comps[i].name);
    }
    L("expressionError count=" + EXPR_ERRORS.length);
    for (i = 0; i < EXPR_ERRORS.length; i++) {
        L("EXPR_ERR " + EXPR_ERRORS[i]);
    }
}

// ============ 收尾:存盘 + DONE + 退出 ============
// ★ app.quit() 是本脚本能被 run_ae.ps1 判定"结束"的唯一信号;少了它只能靠超时
function finish(aepPath) {
    app.project.save(new File(aepPath));
    $.sleep(1500);                       // 等保存落盘
    var f = new File(aepPath);
    L("saved " + aepPath + " exists=" + f.exists + " bytes=" + f.length);
    L("DONE");
    $.sleep(2500);                        // 等抽帧队列写完,再退出
    app.quit();
}
