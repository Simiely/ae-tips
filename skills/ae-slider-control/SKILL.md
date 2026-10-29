---
name: ae-slider-control
description: 在 AE 合成里建「参数控制」图层——一个 solid 挂一组 Slider Control(时长/延迟/错位),让整条时间线的节奏改参数即生效,交付方自己就能调。当用户说「做成可调参数的」「加几个滑块控制时长和延迟」「每个字依次出现(错位)」「参数集中在一个地方好调」「滑块改了没反应」时使用。含中文界面下按索引取 effect(1)、命名约定、单位用毫秒、错位 Index、判据(改滑块后 bbox 必须变)。
agent_created: true
---

# 参数控制图层(滑块)

缓动算法本身见 `ae-expression-tween`;本 skill 管**控制契约**:图层怎么建、滑块叫什么、
默认多少、表达式怎么读、怎么证明它真的生效。

**核心结论先行**:把"节奏"从代码里搬到滑块上,是这类模板工程能交付的前提 ——
否则每改一次时长都要重跑生成器。

## 铁律

1. **图层名固定 `参数控制`**,且**全合成唯一**(表达式靠 `thisComp.layer("参数控制")` 找它)
2. **置顶**(`moveToBeginning`),否则可能被同名层顶掉
3. **滑块一律用毫秒**;表达式里 `/1000`
4. **读滑块按索引 `effect(1)`**;不要用默认英文名 `"Slider"`
5. **同名滑块禁止重复**:同一图层上两个「时长」会让表达式取到前者
6. **加滑块前后的表达式必须勾稽**:滑块名改了,表达式里也要改,一处漏了就是 `null`
7. **判据 = 改滑块后同一时间点 bbox 必须变**

---

## §1 先侦察:合成里现有控制层

```javascript
for (var i = 1; i <= comp.numLayers; i++) {
    var l = comp.layer(i);
    if (l.name === "参数控制") {
        var fx = l.property("ADBE Effect Parade");
        for (var j = 1; j <= fx.numProperties; j++) {
            L("slider " + j + " name=" + fx.property(j).name);
        }
    }
}
```

判据:同名滑块出现两次 ⇒ 先改名,别急着加新的。

## §2 建控制层

```javascript
var ctl = comp.layers.addSolid([0,0,0], "参数控制", w, h, 1, dur);
ctl.moveToBeginning();
var S = [
  ["图标时长",500],["图标延迟",0],
  ["文字时长",500],["文字延迟",0],["文字错位",0],
  ["副标题时长",400],["副标题延迟",400],["副标题错位",0],
  ["Logo整体时长",1000],["Logo整体延迟",0]
];
for (var i = 0; i < S.length; i++) {
    var fx = ctl.property("ADBE Effect Parade").addProperty("ADBE Slider Control");
    fx.name = S[i][0];
    fx.property(1).setValue(S[i][1]);   // ★ 按索引,不按 "Slider"
}
```

现成实现:[`../scripts/ae-headless-run/jsxlib.jsx`](../scripts/ae-headless-run/jsxlib.jsx) 的 `addController()`

## §3 表达式怎么读

```javascript
var C = thisComp.layer("参数控制");
var D = Math.max(0.05, C.effect("图标时长")(1) / 1000);
var S = C.effect("图标延迟")(1) / 1000;
S += idx * C.effect("文字错位")(1) / 1000;    // idx = 组内序号,0 起
```

**两种名字情况必须分清**:

| 情形 | 能否按名字取 | 结论 |
|---|---|---|
| 效果**默认英文名**(`Slider`、`Blurriness`) | ✗ 返回 `null`(中文界面) | 按**索引** `effect(1)` |
| **自己用脚本命名**(`fx.name="图标时长"`) | ✓ | 表达式里可以按中文名 |

## §4 十项默认值与分组

| 组 | 滑块 | 默认 | 说明 |
|---|---|---|---|
| 图标 | 图标时长 / 图标延迟 | 500 / 0 | 时长 0.5s |
| 文字 | 文字时长 / 文字延迟 / 文字错位 | 500 / 0 / 0 | 逐字;错位 = 每字多等 N ms |
| 副标题 | 副标题时长 / 副标题延迟 / 副标题错位 | 400 / 400 / 0 | 比文字晚 0.4s 起 |
| Logo 整体 | Logo整体时长 / Logo整体延迟 | 1000 / 0 | 慢一点、有分量 |

分组的意义:交付方只看"哪个东西什么节奏",不用理解表达式。

## §5 验证

| 判据 | 做法 | 实测 |
|---|---|---|
| 滑块存在且数量对 | 遍历效果名 | 10 个 |
| 表达式读得到 | `expressionError` = 0 | 9 个合成 0 条 |
| **真的生效** | 改时长 → 同一时间点抽帧 → 比 bbox | 500→1000ms,`t=0.12s` 顶边 **486 → 497px** |
| 错位生效 | 把错位拨到 100ms → 首字与末字出现时刻应拉开 | 末字比首字晚 `(n-1)×100ms` |
| 归位无残留 | 验完把滑块改回默认值再存盘 | 存盘前 `setValue(默认)` |

> **验完必须还原**:滑块留在 1000ms 的工程交付出去,对方会以为默认就是 1 秒。

## §6 排查

| 现象 | 原因 |
|---|---|
| `C.effect("图标时长")` 为 `null` | 图层名不是 `参数控制` / 滑块名拼错 |
| 值不跟着滑块变 | 表达式读的是索引,但滑块顺序被改动过 |
| 两个滑块互相影响 | 同名重复 |
| 时长拨到 0 图层消失 | 忘了 `Math.max(0.05, D)` |
| 拨滑块动画不变 | 抽帧太靠后(动画已结束),要在动画中段取 |

## §7 脚本与文档

- [`../scripts/ae-headless-run/jsxlib.jsx`](../scripts/ae-headless-run/jsxlib.jsx) —— `addController(comp, w, h, dur, sliders)`
- [`../scripts/comp-builder/build_aep.py`](../scripts/comp-builder/build_aep.py) —— 生成器里的 10 个滑块与默认值
- 文档:[`../docs/表达式缓动与滑块控制.md`](../docs/表达式缓动与滑块控制.md) §4

## 与相邻 skill 的边界

| Skill | 分工 |
|---|---|
| `ae-slider-control`(本) | 控制契约(建层 / 命名 / 默认值 / 读取 / 生效证明) |
| `ae-expression-tween` | 拿 `u` 之后的缓动算法 |
| `ae-comp-builder` | 哪个合成需要哪组滑块 |
