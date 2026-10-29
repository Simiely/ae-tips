---
name: ae-comp-builder
description: 从素材清单(manifest.json)批量生成 AE 工程——多合成、背景 solid、参数控制图层、逐层导入 PNG 并挂表达式,产出一份自包含的 .jsx 交给无头运行。当用户说「三个品牌九套方案都做出来」「批量建合成」「把 manifest 铺成工程」「同一套动效铺到多个品牌/尺寸」「改一下位移量要重跑全部」时使用。含生成器分层(数据/逻辑/产物)、role 决定滑块组、AE 无 JSON.parse 所以要内联字面量、缓动源码两份必须逐字一致。
agent_created: true
---

# 从素材清单生成工程

传输层见 `ae-script-runner`;滑块契约见 `ae-slider-control`;缓动见 `ae-expression-tween`。
本 skill 管**编排**:哪些元素、进哪个合成、挂什么方案。

**核心结论先行**:数据(`manifest.json`)、逻辑(`build_aep.py`)、产物(`.jsx` → `.aep`)分三层。
手写 9 个合成 × 360 段表达式字符串是不可维护的。

## 铁律

1. **合成结构固定**:参数控制(**null 对象**,置顶)→ 图层 → BG(置底 + `locked`)
   - ★ 参数控制**不能用 solid**:不透明黑层会盖住整幅画面,而日志一切正常,只有抽帧能发现
2. **参数控制全合成唯一**,表达式靠名字找它
3. **`cx/cy` 用素材文件中心**(含透明边距);边距不对称就先修素材
4. **AE 没有 `JSON.parse`** ⇒ 清单一律变成 **JS 字面量**内联,不要试图在 jsx 里读 JSON
5. **表达式在 Python 侧拼好**,jsx 侧不做逻辑决策
6. **缓动源码两份必须逐字一致**,提交前跑 `--check-ease`
7. **生成器必须先打印清单的键路径**再动手(根节点带 `meta`,直接迭代会 `KeyError`)

---

## §1 先侦察:清单与素材

```bash
python -c "import json,io; d=json.load(io.open('manifest.json',encoding='utf-8-sig')); print(list(d.keys()))"
```

- 根键是 `meta` + `comps`(不是 `brands`);
- 每个 `layers[].file` 必须在 `meta.asset_dir` 下存在 —— 生成器会打 `MISS`,但**先自查更快**。

## §2 清单结构(最小可用)

```json
{
  "meta": {
    "comp":  { "width": 2048, "height": 1152, "fps": 30, "duration": 3 },
    "bg":    "#0F0F11",
    "asset_dir": "D:/work/素材",
    "aep": "D:/work/out/工程.aep",
    "log": "C:/temp/build_log.txt",
    "render_dir": "C:/temp/ae_render"
  },
  "comps": [
    { "name": "QQ音乐_方案1", "scheme": "s1",
      "shoot": [0, 0.12, 0.28, 1.2],
      "layers": [
        { "file": "QQ音乐/icon.png", "role": "icon", "name": "图标", "cx": 855.75, "cy": 541 },
        { "file": "QQ音乐/logo_full.png", "role": "logo_full", "name": "Logo整体", "cx": 1025, "cy": 541 },
        { "file": "QQ音乐/logo_Q.png", "role": "logo", "name": "字1", "cx": 977.75, "cy": 541, "idx": 0 }
      ] }
  ]
}
```

`role` 决定读哪组滑块:

| role | 时长/延迟 | 错位 | 典型对象 |
|---|---|---|---|
| `icon` | 图标时长 / 图标延迟 | — | 品牌图标 |
| `logo` | 文字时长 / 文字延迟 | 文字错位 | 逐字 Logo |
| `tag` | 副标题时长 / 副标题延迟 | 副标题错位 | 副标题逐字 |
| `logo_full` | Logo整体时长 / Logo整体延迟 | — | 整体 Logo |

## §3 生成与运行

```bash
python ../comp-builder/build_aep.py manifest.json -o build_x.jsx
python ../comp-builder/build_aep.py --check-ease
powershell -File ../ae-headless-run/run_ae.ps1 -Jsx build_x.jsx
```

生成物四段(缺一段都算没做完):

1. 路径常量 + `DATA` 字面量
2. 公共函数(`L` / `hexToRgb` / `importPng` / `setT` / `addBlur`)
3. 每层:import → 命名 → `Position.setValue([cx,cy])` → 逐条表达式 → 可选模糊
4. 收尾:表达式体检 → 抽帧(`sleep` + `exists`)→ `save` → `DONE` → `quit`

## §4 三套方案的数值

| 方案 | icon | 逐字 Logo | logo_full |
|---|---|---|---|
| `s1` 上浮淡入 | `+40.96px` / `Opacity` / `Scale 92→100` / `Blur 12→0` | `+20.48px` / `Blur 4→0` | `+116px` / `Blur 4→0` |
| `s3` 弹性缩放 | `Scale 50+60f-10g` / `Blur 16→0` | `±40.96px`(按 `idx` 奇偶) | — |
| `s5` 整体上浮 | — | — | `+116px` / `Opacity` 用 `u/0.55` 提前收满 |
| `s5v2` 最初经典 | — | `+32px` / `Opacity` / `Blur 10→0` / **ease** | `+116px` / `Scale 94→100` / `Blur 20→0` / 前 55% 收清 / **Quart-out** |

## §5 验证

| 判据 | 期望 | 实测 |
|---|---|---|
| 合成数 = 清单 `comps` 数 | 9 | 9 |
| `expressionError` = 0 条 | 0 | 9 个合成全 0 |
| 每层都进去了 | `cc.numLayers` = 图层数 + 2 | 一致 |
| 抽帧全落盘 | 日志 `exists=true` 数 = 磁盘文件数 | 27/27 + 2 对照 |
| `.aep` 存在且非空 | 字节数 > 0 | 2,281,249 |
| 末帧 bbox 对 | ±4px | 见 `ae-frame-verify` |

## §6 排查

| 现象 | 原因 |
|---|---|
| `KeyError: 'icon'` | 迭代了根节点(要 `comps`) |
| 图层偏 | `cx/cy` 用了可见内容中心,而素材边距对称 ⇒ 应该用文件中心 |
| 某层完全不见 | `importPng` 返回 null(文件不存在 / 路径拼错) |
| 表达式全红 | 参数控制不在顶层 / 名字不符;或体检判据把 `undefined` 当成错误(合成级会假报) |
| 改了生成器但产物没变 | 没重跑 `build_aep.py`(jsx 是生成物) |
| 缓动行为变了 | 两份 `EASE` 漂了 ⇒ `--check-ease` |

## §7 脚本与文档

- [`../scripts/comp-builder/build_aep.py`](../scripts/comp-builder/build_aep.py) —— 清单 → `.jsx`
- [`../scripts/comp-builder/README.md`](../scripts/comp-builder/README.md) —— 字段说明与方案数值
- [`../scripts/ae-headless-run/jsxlib.jsx`](../scripts/ae-headless-run/jsxlib.jsx) —— 手写 jsx 时用同一套公共函数
- 文档:[`../docs/从素材清单生成工程.md`](../docs/从素材清单生成工程.md)

## 与相邻 skill 的边界

| Skill | 分工 |
|---|---|
| `ae-comp-builder`(本) | 合成结构、图层编排、role→滑块、生成器纪律 |
| `ae-vector-extract` | 上游:设计稿 → PNG + `elements.json` |
| `ae-slider-control` | 滑块怎么建、叫什么 |
| `ae-frame-verify` | 下游:产物对不对 |
