# comp-builder · 从素材清单生成 `.aep`

`build_aep.py` 读 `manifest.json` → 吐一份**自包含**的 `build_<名>.jsx` → 交给 `run_ae.ps1` 跑成 `.aep`。

## 为什么中间要过一层 jsx

AE 2026 的 ExtendScript **没有 `JSON.parse`**。清单必须变成 **JS 字面量**内联进脚本;
而且表达式是**字符串**,生成器在 Python 侧拼好再写进去,比在 jsx 里二次拼更可控。

## 用法

```bash
python build_aep.py manifest.json -o build_start_page.jsx
python build_aep.py --check-ease      # 只校验缓动源码与 tween.jsx 是否逐字一致
powershell -File ../ae-headless-run/run_ae.ps1 -Jsx build_start_page.jsx
```

## manifest 结构

```json
{
  "meta": {
    "comp":  { "width": 2048, "height": 1152, "fps": 30, "duration": 3 },
    "bg":    "#0F0F11",
    "asset_dir": "D:/work/素材",
    "aep":       "D:/work/out/工程.aep",
    "log":       "C:/temp/build_log.txt",
    "render_dir":"C:/temp/ae_render",
    "motion": { "iconDy": 40.96, "logoDy": 20.48, "tagDy": 20.48,
                "logoFullDy": 116.0, "logoSpread": 40.96,
                "blurIcon": 12, "blurIconPop": 16, "blurLogo": 4 }
  },
  "comps": [
    {
      "name": "QQ音乐_方案1",
      "scheme": "s1",
      "shoot": [0, 0.12, 0.28, 0.45, 0.7, 1.2],
      "layers": [
        { "file": "QQ音乐/icon.png",     "role": "icon",      "name": "图标",     "cx": 855.75, "cy": 541 },
        { "file": "QQ音乐/logo_full.png","role": "logo_full", "name": "Logo整体", "cx": 1025,   "cy": 541 },
        { "file": "QQ音乐/字1.png",       "role": "logo",      "name": "字1",      "cx": 977.75, "cy": 541, "idx": 0 }
      ]
    }
  ]
}
```

字段:

| 字段 | 说明 |
|---|---|
| `meta.comp` | 合成规格;`duration` 秒 |
| `meta.bg` | 背景纯色,`addBg` 会置底并**锁定** |
| `meta.asset_dir` | PNG 目录;层里 `file` 是相对路径 |
| `meta.motion.*` | 位移/模糊的**默认量**,单位 px;缺省值见上表(取自实测工程) |
| `comps[].scheme` | `s1` 上浮淡入 / `s3` 弹性缩放 / `s5` 整体上浮 |
| `comps[].shoot` | 抽帧时间点(秒);不写就不抽 |
| `layers[].role` | `icon` / `logo` / `tag` / `logo_full` ⇒ 决定读哪组滑块 |
| `layers[].idx` | 错位序号(`logo` 用 `文字错位`,方案 3 里还决定左右方向) |
| `layers[].cx/cy` | 图层中心在合成坐标的位置 |

## 生成物包含什么

1. `#target aftereffects` + 三个路径常量 + `DATA`(整份清单的 JS 字面量)
2. 公共函数:`L()` / `hexToRgb` / `importPng` / `setT` / `addBlur`
3. 每个合成:背景 solid(锁定)→ 参数控制图层(**10 个滑块**)→ 逐层 import + 定位 + 挂表达式 + 可选高斯模糊
4. 表达式体检:`scanExpr` 递归遍历属性树,把 `expressionError` 非空的打到日志
5. 抽帧:`c<N>_t<T>.png`,每帧 `$.sleep(900)` + `exists` 自查
6. 存盘 → `L("DONE")` → `$.sleep(2500)` → `app.quit()`

## 三套方案的数值

| 方案 | icon | 文字(逐字) | logo_full |
|---|---|---|---|
| `s1` 上浮淡入 | `Position` `+40.96px` 上浮、`Opacity 100*f`、`Scale 92→100`、`Blur 12→0` | `+20.48px`、`Opacity`、`Blur 4→0` | `+116px`、`Opacity`、`Blur 4→0` |
| `s3` 弹性缩放 | `Scale 50+60*f-10*g`(`back` 超调)、`Blur 16→0` | `Position ±40.96px`(按 `idx` 奇偶分左右) | — |
| `s5` 整体上浮 | — | — | `+116px`、`Opacity` 用 `u/0.55` 提前收满、`Blur 4→0` |

滑块默认值:`图标时长 500 / 图标延迟 0 / 文字时长 500 / 文字延迟 0 / 文字错位 0 /
副标题时长 400 / 副标题延迟 400 / 副标题错位 0 / Logo整体时长 1000 / Logo整体延迟 0`(单位 ms)。

## 坑

- **缓动源码有两份**:`build_aep.py` 的 `EASE` 与 `../expression-tween/tween.jsx` 的 `TWEEN.EASE`。
  表达式不能调外部函数 ⇒ 只能复制;**复制就容易漂**,所以加了 `--check-ease`(判据:逐字一致,273 字符)。
- **`data["brands"]` 而不是根节点**:清单根上还有 `meta`,直接迭代会 `KeyError: 'icon'`。
  本版已改成 `comps` 扁平列表,避免同类问题;读别人的清单时**先打印键路径**。
- **`cx/cy` 是文件中心**(含透明边距)。边距左右不等时,可见内容会偏 —— 要么用 `vector-extract` 的对称边距,
  要么改传可见内容中心。
- **滑块名用中文,表达式也用中文**可以工作(自己命名的属性名会随界面语言);
  但**默认英文名**(`Slider` / `Blurriness`)**在中文界面取不到** ⇒ 按索引。
