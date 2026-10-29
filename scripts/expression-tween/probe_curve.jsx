#target aftereffects
// probe_curve.jsx —— 只读采样:把表达式**求值后**的真实属性值打到日志
//
// 为什么需要它:
//   抽帧只能看出"大概在动",看不出"是不是按这条曲线在动";
//   `valueAtTime(t, false)` 返回的是**含表达式求值**的结果,可以逐点与解析值对表。
//
// 用法:
//   1. 改下面 4 个配置(路径按需)
//   2. run_ae.ps1 -Jsx probe_curve.jsx -Log <日志路径>
//   3. compare_curve.py <日志> --profile s5v2
//
// ★ 只读:app.open() 打开工程、不改、不存盘,末尾 app.quit()。

var LOG   = "C:/temp/curve_probe.log";
var AEP   = "C:/temp/out.aep";
var TIMES = [0, 0.05, 0.1, 0.12, 0.2, 0.275, 0.35, 0.5, 0.8];
var LOGO_NAME = "Logo整体";
var TAG_NAME  = "副标题1";

function L(s) {
    var f = new File(LOG);
    f.open("a");
    f.write(s + "\n");
    f.close();
}

function tg(l, name) { return l.property("ADBE Transform Group").property(name); }

function f3(v) {
    // 固定 3 位小数,便于下游按 | 分隔解析
    return (Math.round(v * 1000) / 1000).toString();
}

app.open(new File(AEP));
L("open " + app.project.name + " file=" + (app.project.file !== null));

var i, k, it, comp, lyr, pPos, pScl, pOpa, pBlu, t, pos, sc, op, bl;
for (i = 1; i <= app.project.numItems; i++) {
    it = app.project.item(i);
    if (!(it instanceof CompItem)) { continue; }
    comp = it;
    L("COMP|" + comp.name + "|" + comp.width + "|" + comp.height + "|" + comp.numLayers);

    // ---- 整体 Logo ----
    lyr = null;
    try { lyr = comp.layer(LOGO_NAME); } catch (e1) { lyr = null; }
    if (lyr !== null) {
        pPos = tg(lyr, "ADBE Position");
        pScl = tg(lyr, "ADBE Scale");
        pOpa = tg(lyr, "ADBE Opacity");
        pBlu = lyr.property("ADBE Effect Parade").property(1).property(1);   // ★ 按索引,不按英文名
        for (k = 0; k < TIMES.length; k++) {
            t = TIMES[k];
            pos = pPos.valueAtTime(t, false);
            sc  = pScl.valueAtTime(t, false);
            op  = pOpa.valueAtTime(t, false);
            bl  = pBlu.valueAtTime(t, false);
            L("S|" + comp.name + "|logo|" + f3(t) + "|" + f3(pos[1]) + "|" + f3(sc[0]) + "|" + f3(op) + "|" + f3(bl));
        }
    }

    // ---- 副标题第 1 字 ----
    lyr = null;
    try { lyr = comp.layer(TAG_NAME); } catch (e2) { lyr = null; }
    if (lyr !== null) {
        pPos = tg(lyr, "ADBE Position");
        pOpa = tg(lyr, "ADBE Opacity");
        pBlu = lyr.property("ADBE Effect Parade").property(1).property(1);
        for (k = 0; k < TIMES.length; k++) {
            t = TIMES[k];
            pos = pPos.valueAtTime(t, false);
            op  = pOpa.valueAtTime(t, false);
            bl  = pBlu.valueAtTime(t, false);
            L("S|" + comp.name + "|tag|" + f3(t) + "|" + f3(pos[1]) + "|-|" + f3(op) + "|" + f3(bl));
        }
    }
}

L("DONE");
$.sleep(800);
app.quit();
