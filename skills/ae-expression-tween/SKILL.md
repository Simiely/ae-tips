---
name: ae-expression-tween
description: 用 AE 表达式做入场缓动(cubic-bezier 二分反解)与参数化控制——不用关键帧,绕开 AE 2026 的 setTemporalEaseAtKey 在多维亚属性上报错/硬崩进程的问题。当用户说「给这套动画加缓动」「入场上浮淡入/弹性缩放」「时长延迟做成可调的」「改参数不要重打关键帧」「AE 报 值数组没有 1 元素 / 设置缓动就崩溃」时使用。含 clamp 归一化时间、value 作基准、曲线参数顺序、表达式自包含(不能调外部函数)。
agent_created: true
---

# 表达式缓动

传输层见 `ae-script-runner`;参数控制图层的建法见 `ae-slider-control`;
本 skill 只讲**表达式里那套缓动本身**。

**核心结论先行**:AE 2026 的 `setTemporalEaseAtKey` 对多维亚属性**不可用**(Position 报错、
Scale **硬崩进程**、退到 1 个 ease 仍在采样阶段崩)⇒ **一律用表达式**。

## 铁律

1. **不碰 `setTemporalEaseAtKey`**;看到它先删
2. **缓动函数必须内联进表达式字符串** —— 表达式沙箱拿不到外部 `.jsx` 函数
3. **`u` 必须 clamp 到 [0,1]**,否则延迟前反向跳、结束后冲过头
4. **位移以 `value` 为基准**,不写绝对坐标
5. **滑块单位用毫秒**,表达式里 `/1000`
6. **表达式里不写 `//`** —— 拼接成一行后会把后半段全注释掉
7. **验证靠抽帧**,不信 API 返回值

---

## §1 先侦察:确认没有残留关键帧

```javascript
var props = layer.property("ADBE Transform Group");
for (var i = 1; i <= props.numProperties; i++) {
    var p = props.property(i);
    L(p.name + " keys=" + (p.numKeys || 0) + " expr=" + (p.expressionEnabled ? "on" : "off"));
}
```

- `keys > 0` 且有表达式 ⇒ 关键帧被表达式覆盖但**仍占文件体积**,建议删;
- 更要紧的是**没有** `setTemporalEaseAtKey` 残留(崩过一次的脚本要整段清掉)。

## §2 写表达式:固定骨架

```javascript
var C=thisComp.layer("参数控制");
var D=Math.max(0.05,C.effect("图标时长")(1)/1000);   // ms -> s
var S=C.effect("图标延迟")(1)/1000;
var u=Math.min(1,Math.max(0,(time-S)/D));
<EASE 源码>
var f=cb(u,0.16,1,0.3,1);
[value[0], value[1]+40.96-40.96*f];                  // 上浮到基准位置
```

`EASE` 源码(三函数,逐字):

```javascript
function bx(s,a,b){var u=1-s;return 3*u*u*s*a+3*u*s*s*b+s*s*s;}
function by(s,a,b){var u=1-s;return 3*u*u*s*a+3*u*s*s*b+s*s*s;}
function cb(t,a,b,c,d){var lo=0;var hi=1;var s=t;var i;var x;
for(i=0;i<20;i++){x=bx(s,a,c);if(x<t){lo=s;}else{hi=s;}s=(lo+hi)/2;}
return by(s,b,d);}
```

四条曲线:

| 键 | CSS | 用途 | t=0.5 实测 |
|---|---|---|---|
| `out` | `0.16,1,0.3,1` | 主力 | 0.9718 |
| `back` | `0.34,1.56,0.64,1` | 缩放超调 | **1.0874** |
| `inOut` | `0.65,0,0.35,1` | 淡入淡出 | 0.5 |
| `linear` | `0,0,1,1` | 恒等 | 0.5 |

常用组合直接调库:[`../scripts/expression-tween/tween.jsx`](../scripts/expression-tween/tween.jsx)

```javascript
TWEEN.slideY({ dur:"图标时长", delay:"图标延迟", dy:40.96 })
TWEEN.scalePop({ dur:"图标时长", delay:"图标延迟", from:50 })
TWEEN.blurIn({ dur:"图标时长", delay:"图标延迟", blur:12 })
```

## §3 验证

```javascript
// ① 表达式体检:递归扫,判据 0 条
// ② valueAtTime 采样对表(最硬的一条,见下)
// ③ 抽帧:t=0 / 与滑块时长相关的几个点 / 末帧
// ④ 改滑块,同一时间点再抽一帧,bbox 必须变
```

**② 采样对表**:抽帧只能看出"在动",看不出"是不是按这条曲线在动"。
`prop.valueAtTime(t, false)` 返回**含表达式求值**的真实值,可以逐点与解析值比。

```powershell
# probe_curve.jsx 改好 AEP/LOG 路径后
run_ae.ps1 -Jsx probe_curve.jsx -Log curve_probe.log
python compare_curve.py curve_probe.log --profile s5v2
```

判据:`FAIL=0`,位置偏差 ≤0.05px、缩放/不透明度/模糊 ≤0.05。
`compare_curve.py` 还自带两条硬检查:

- **[a] 末两帧位置必须相等**(否则"静止基准"不可信,整张表都白算);
- **[b] 分段检查**:方案声明"前 55% 到位"时,`u≥55%` 之后必须 `opacity=100、blur=0`,而位移**仍有余量**
  (>1px)—— 这条能区分"真分段(`cb(min(1,u/0.55))`)"和"整体乘个系数"的假实现。

实测(s5v2 / 三品牌):`最大偏差 0.0055`,`[分段] t=0.275 opacity=100.00 blur=0.00 位移余5.22px > OK`。

三条可证伪读数:

| 判据 | 期望 | 实测 |
|---|---|---|
| 曲线算法 | `linear` 逐点等于 t;`back` 在 t=0.5 **>1** | `cb` 20 次二分:`out` 0.9718 / `back` 1.0874 |
| 终态精确 | `Scale` 末帧必须等于 100 | `50+60×1-10×1 = 100` |
| 采样对表 | 逐点差 ≤0.05 | 9 个时间点 × 6 组,`最大 0.0055` |
| 滑块生效 | 改时长后同一时刻位移必须变 | `图标时长` 500→1000ms,`t=0.12s` 顶边 **486px → 497px** |

`TWEEN.selfTest()` 可以不开 AE 直接验曲线(纯算术)。

## §4 排查

| 现象 | 原因 |
|---|---|
| 属性变红 | 表达式语法错 / 引用了不存在的图层或效果 |
| 值为 NaN / 图层消失 | `D` 为 0(滑块拨到 0)⇒ 必须 `Math.max(0.05, D)` |
| 延迟前反向跳一下 | `u` 没 clamp 到 0 |
| 动画方向反了 | `cb` 参数顺序写成 `cb(t,x1,x2,y1,y2)` |
| 表达式"未定义 cb" | 缓动源码没内联 |
| 后半段代码失效 | 表达式里有 `//` |
| 改画布尺寸后全偏 | 表达式写了绝对坐标,没用 `value` |

## §5 脚本

- [`../scripts/expression-tween/tween.jsx`](../scripts/expression-tween/tween.jsx) —— 曲线常量 + 表达式 builder + `selfTest()`
- [`../scripts/expression-tween/probe_curve.jsx`](../scripts/expression-tween/probe_curve.jsx) —— **只读采样**:打开 `.aep`,把 `valueAtTime` 求值结果按 `S|comp|obj|t|...` 落盘
- [`../scripts/expression-tween/compare_curve.py`](../scripts/expression-tween/compare_curve.py) —— 解析曲线逐点对表 + `[a]` 末帧静止 / `[b]` 分段检查
- [`../scripts/expression-tween/README.md`](../scripts/expression-tween/README.md) —— 六条曲线的实测数值表 + 采样用法
- 生成器里的同一份源码:[`../scripts/comp-builder/build_aep.py`](../scripts/comp-builder/build_aep.py) 的 `EASE`
  (**必须与 tween.jsx 逐字一致**,`build_aep.py --check-ease` 会比对)

文档:[`../docs/表达式缓动与滑块控制.md`](../docs/表达式缓动与滑块控制.md)

## 与相邻 skill 的边界

| Skill | 分工 |
|---|---|
| `ae-expression-tween`(本) | 缓动算法与表达式骨架 |
| `ae-slider-control` | 滑块怎么建、叫什么、默认多少、错位怎么叠 |
| `ae-comp-builder` | 表达式挂在**哪些层的哪些属性**上 |
