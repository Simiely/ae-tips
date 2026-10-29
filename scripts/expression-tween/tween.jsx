// tween.jsx —— 表达式缓动库(ExtendScript / ES3)
//
// 解决的问题:AE 2026 的 `setTemporalEaseAtKey` 对多维亚属性不可用(Position 报错、Scale 硬崩进程),
// 所以缓动改由**表达式**完成:一个 `u = (time - delay) / dur` 归一化时间 + cubic-bezier 反解。
//
// ★ 表达式跑在独立沙箱里,**拿不到这里定义的函数**。所以每个 builder 返回的是**自包含字符串**
//   (EASE 源码被逐字拼进去)。这就是为什么仓库里到处是长表达式而不是"调个库函数"。

var TWEEN = (function () {

    // 三次贝塞尔:给定参数 s 求 x / y。P0=(0,0) P3=(1,1)
    //   x(s) = 3(1-s)²s·x1 + 3(1-s)s²·x2 + s³
    //   缓动的难点是"给定 x=t 反解 s" —— 下面 cb() 用 20 次二分
    var EASE =
        "function bx(s,a,b){var u=1-s;return 3*u*u*s*a+3*u*s*s*b+s*s*s;}" +
        "function by(s,a,b){var u=1-s;return 3*u*u*s*a+3*u*s*s*b+s*s*s;}" +
        "function cb(t,a,b,c,d){var lo=0;var hi=1;var s=t;var i;var x;" +
        "for(i=0;i<20;i++){x=bx(s,a,c);if(x<t){lo=s;}else{hi=s;}s=(lo+hi)/2;}" +
        "return by(s,b,d);}";

    // 与 CSS cubic-bezier() 同语义。back 的 y2=1.56 > 1 => 超调(回弹),可用于 Scale
    var CURVE = {
        out:    "0.16,1,0.3,1",
        back:   "0.34,1.56,0.64,1",
        inOut:  "0.65,0,0.35,1",
        linear: "0,0,1,1"
    };

    // ---- 头部:读滑块 -> 归一化进度 u ----
    //   o = { ctrl:"参数控制", dur:"图标时长", delay:"图标延迟", stag:"文字错位", idx:0 }
    //   时长/延迟单位都是**毫秒**(滑块上写 500 比写 0.5 直观)
    function head(o) {
        var c = o.ctrl || "参数控制";
        var s = 'var C=thisComp.layer("' + c + '");';
        s += 'var D=Math.max(0.05,C.effect("' + o.dur + '")(1)/1000);';
        s += 'var S=C.effect("' + o.delay + '")(1)/1000;';
        if (o.stag) {
            s += 'S+=' + (o.idx || 0) + '*C.effect("' + o.stag + '")(1)/1000;';
        }
        s += 'var u=Math.min(1,Math.max(0,(time-S)/D));';
        return s;
    }

    // ---- 进度 f = cb(u, 曲线) ----
    function curve(key) {
        return 'var f=cb(u,' + (CURVE[key] || CURVE.out) + ');';
    }

    // ---- 常用组合 ----
    // 纵向位移:基准值(图层摆好的位置)是**终点**;再往 +y 方向偏移 dy 作为起点
    function slideY(o) {
        return EASE + head(o) + curve(o.ease || "out") +
            'var dy=' + o.dy + ';var p=value;[p[0],p[1]+dy-dy*f];';
    }

    // 横向位移:dx 可正可负(按 idx 奇偶给正负号就能做"左右分开入场")
    function slideX(o) {
        return EASE + head(o) + curve(o.ease || "out") +
            'var dx=' + o.dx + ';var p=value;[p[0]+dx-dx*f,p[1]];';
    }

    function fade(o) {
        return EASE + head(o) + curve(o.ease || "out") + '100*f;';
    }

    // 缩放入场:from -> 100。带 squash(默认 0.6)时用 back 曲线做一次轻微超调
    function scalePop(o) {
        var from = (o.from === undefined ? 50 : o.from);
        var s = EASE + head(o) + curve(o.ease || "out");
        s += 'var sp=' + from + '+(' + (100 - from + 10) + ')*f;';
        if (o.squash === false) {
            s += 'var sc=sp;';
        } else {
            s += 'var g=cb(Math.min(1,u/' + (o.squash || 0.6) + '),0.34,1.56,0.64,1);';
            s += 'var sc=sp-10*g;';    // from=50 时读数 50+60*f-10*g:先冲过头再落回 100
        }
        return s + '[sc,sc];';
    }

    // 模糊入场:blur -> 0(必须同时开 Repeat Edge Pixels,见 jsxlib.addBlur)
    function blurIn(o) {
        return EASE + head(o) + curve(o.ease || "out") + (o.blur || 12) + '*(1-f);';
    }

    // ---- 自检:不碰 AE,纯算术,可在任何 jsx 里跑 ----
    function selfTest() {
        var out = [];
        var keys = ["out", "back", "inOut", "linear"];
        var i, c, t, s, lo, hi, x, k;
        for (i = 0; i < keys.length; i++) {
            c = CURVE[keys[i]].split(",");
            out.push(keys[i] + ": t=0 -> " + evalCb(0, c) +
                     "  t=0.5 -> " + evalCb(0.5, c) +
                     "  t=1 -> " + evalCb(1, c));
        }
        return out.join("\n");
    }

    // evalCb 只是把 EASE 的算法用 JS 再实现一遍,供 selfTest 用
    function evalCb(t, c) {
        var a = parseFloat(c[0]), b = parseFloat(c[1]),
            cc = parseFloat(c[2]), d = parseFloat(c[3]);
        var lo = 0, hi = 1, s = t, i, x;
        for (i = 0; i < 20; i++) {
            x = 3 * (1 - s) * (1 - s) * s * a + 3 * (1 - s) * s * s * cc + s * s * s;
            if (x < t) { lo = s; } else { hi = s; }
            s = (lo + hi) / 2;
        }
        return Math.round((3 * (1 - s) * (1 - s) * s * b + 3 * (1 - s) * s * s * d + s * s * s) * 1000) / 1000;
    }

    return {
        EASE: EASE,
        CURVE: CURVE,
        head: head,
        curve: curve,
        slideY: slideY,
        slideX: slideX,
        fade: fade,
        scalePop: scalePop,
        blurIn: blurIn,
        selfTest: selfTest
    };
}());
