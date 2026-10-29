# expression-tween · 表达式缓动

不用关键帧,用表达式做缓动。入口 `tween.jsx`。

## 为什么不用 `setTemporalEaseAtKey`

AE 2026 实测不可用:

| 属性 | 调用 | 结果 |
|---|---|---|
| Position | `ps.setTemporalEaseAtKey(1, [ease], [ease])`(2 个 ease) | 报 `由于参数 2,无法调用 ... 值数组没有 1 元素` |
| Scale | `sc.setTemporalEaseAtKey(1, [ease], [ease])` | **AE 进程直接消失**(`try/catch` 接不住) |
| Position | 退到 1 个 ease | 过校验,但**采样/渲染阶段崩** |

⇒ 整条路径放弃。缓动改表达式:没有 API 依赖、参数可外置成滑块、改时长不用重打关键帧。

## 算法

CSS 的 `cubic-bezier(x1,y1,x2,y2)`,在表达式里要**由 x 反解参数 s**,再求 y:

```
x(s) = 3(1-s)²s·x1 + 3(1-s)s²·x2 + s³
y(s) = 3(1-s)²s·y1 + 3(1-s)s²·y2 + s³
```

`cb(t,...)` 用 **20 次二分**反解(`lo=0, hi=1`),精度 2⁻²⁰ ≈ 1e-6,对 30fps 的 1 帧(33ms)绰绰有余。

内置四条曲线:

| 键 | CSS | 用途 |
|---|---|---|
| `out` | `cubic-bezier(0.16, 1, 0.3, 1)` | 进厂主力(快出慢收) |
| `back` | `cubic-bezier(0.34, 1.56, 0.64, 1)` | y2 > 1 ⇒ **超调**,用于 Scale 回弹 |
| `inOut` | `cubic-bezier(0.65, 0, 0.35, 1)` | 淡入淡出 |
| `linear` | `cubic-bezier(0,0,1,1)` | 恒等(`y(x)=x`) |
| `quartOut` | `cubic-bezier(0.25, 1, 0.5, 1)` | 方案5 · 最初经典:Logo 整体 |
| `ease` | `cubic-bezier(0.42, 0, 0.58, 1)` | 方案5 · 最初经典:副标题 |

## 表达式怎么拼

```javascript
// 手写
var lyr = comp.layers.add(footage);
lyr.property("ADBE Transform Group").property("ADBE Position").expression =
    TWEEN.slideY({ dur: "图标时长", delay: "图标延迟", dy: 40.96 });

// 更省事:走 jsxlib
setTransformExpr(lyr, "ADBE Position", TWEEN.slideY({...}));
```

生成出来的一段(节选,`EASE` 被逐字拼进去):

```javascript
function bx(s,a,b){var u=1-s;return 3*u*u*s*a+3*u*s*s*b+s*s*s;}
function by(s,a,b){var u=1-s;return 3*u*u*s*a+3*u*s*s*b+s*s*s;}
function cb(t,a,b,c,d){var lo=0;var hi=1;var s=t;var i;var x;
  for(i=0;i<20;i++){x=bx(s,a,c);if(x<t){lo=s;}else{hi=s;}s=(lo+hi)/2;}
  return by(s,b,d);}
var C=thisComp.layer("参数控制");
var D=Math.max(0.05,C.effect("图标时长")(1)/1000);
var S=C.effect("图标延迟")(1)/1000;
var u=Math.min(1,Math.max(0,(time-S)/D));
var f=cb(u,0.16,1,0.3,1);
var dy=40.96;var p=value;[p[0],p[1]+dy-dy*f];
```

## ★ 三个必须知道的表达式事实

1. **表达式拿不到外部函数**。`tween.jsx` 里的 `cb` 在表达式里不存在,必须把源码**拼进字符串**。
   这就是 `EASE` 常量存在的理由,也是 `comp-builder` 里还要再存一份的原因(两边必须**逐字一致**,
   `build_aep.py --check-ease` 会比对)。
2. **单位是毫秒换秒**。滑块写 `500`,表达式里 `(1)/1000` 变 `0.5s`。**不要**让滑块直接写 0.5 ——
   交付方看到 "0.5" 会以为是半帧。
3. **`value` 是图层自己摆好的基准值**。位移用 `value + dy - dy*f`(基准=终点),
   缩放用 `[sc, sc]` 直接给两个分量。**不要**在表达式里写死绝对坐标,否则图层一动就对不上。

## 自检

```javascript
$.writeln(TWEEN.selfTest());
```

预期(20 次二分,取 4 位小数):

| 曲线 | t=0 | t=0.25 | t=0.5 | t=0.75 | t=1 |
|---|---|---|---|---|---|
| `out` | 0 | 0.8256 | 0.9718 | 0.9977 | 1 |
| `back` | 0 | 0.8163 | **1.0874** | 1.0596 | 1 |
| `inOut` | 0 | 0.0708 | 0.5 | 0.9292 | 1 |
| `linear` | 0 | 0.25 | 0.5 | 0.75 | 1 |
| `quartOut` | 0 | 0.6886 | 0.9341 | 0.9939 | 1 |
| `ease` | 0 | 0.1292 | 0.5 | 0.8708 | 1 |

三个可证伪的读数:① **`linear` 必须逐点等于 t**(反解写错时这条最先崩);
② **`back` 在 t=0.5 必须 >1**(1.0874 就是超调,写成 1.0 说明 y2 没生效);
③ **`out` 在 t=0.25 已到 0.8256**(缓动方向反了会变成 0.07 量级)。

> 这组数字是用同一套算法独立算出来再回填的(第一版 README 手写过 0.859 / 1.024,**两个都是错的**)。
> 教训:手册里的读数要么有脚本产出,要么别写。

## 怎么证明曲线**真的**应用了(采样对表)

抽帧只能证明"在动";要证明"按这条曲线在动",必须读**表达式求值后**的值:

```powershell
# 1) probe_curve.jsx 顶部改 AEP / LOG 路径,然后
run_ae.ps1 -Jsx probe_curve.jsx -Log curve_probe.log
# 2) 与解析曲线逐点对表
python compare_curve.py curve_probe.log --profile s5v2
```

`compare_curve.py` 的判据(`FAIL=0`):

| # | 判据 | 为什么 | 实测 |
|---|---|---|---|
| 0 | 位置 ≤0.05px、缩放/不透明度/模糊 ≤0.05 | 逐点,不是只看末帧 | 9 个时间点 × 6 组,**最大 0.0055** |
| a | 末两帧位置**必须相等** | "静止值"是整张表的基准;没停就算错 | `t=0.5` 与 `t=0.8` 差 0 |
| b | 声明"前 55% 到位"时,`u≥55%` 后 `opacity=100、blur=0` 且**位移仍有余量** | 区分真分段 `cb(min(1,u/0.55))` 与"整体乘个系数"的假实现 | `t=0.275`:`opacity=100.00 / blur=0.00 / 位移余 5.22px` |

采样行格式(`S|合成|logo/tag|t|posY|scale|opacity|blur`,固定 3 位小数,`-` 表示不适用):
好解析,也不依赖中文标签。

> ⚠ **比自己踩过的坑**:`dy_m` 的方向别写反 —— 元素是**从下方上浮**,所以"还差多少像素" = `当前 y − 静止 y`。
> 第一版写成 `rest_y - y`,于是 t=0 报 `-116 / 理论 116 / 差 232`,整张表全红了 —— 是**符号错**,不是曲线错。

## 坑

- **表达式里不要有 `//` 注释** —— 整个表达式是被拼接成一行的,`//` 会把后半段全注释掉。
- **别在表达式里 `for` 循环太大** —— 每帧每个图层都要算,20 次二分 × 上百图层仍是毫秒级,但别加码。
- **`Math.min(1, Math.max(0, ...))` 是必须的** —— 缺了它,`u` 在延迟前为负、结束后 >1,
  位移会"先反向跳一下"或"冲过头"。
