---
name: ae-vector-extract
description: 把 `.ai` / `.pdf` 设计稿拆成可独立做动画的透明 PNG(图标、逐字 Logo、副标题),并输出 `elements.json`(文件尺寸 + 合成坐标中心)给 comp-builder 摆层。当用户说「把这个启动页的图标和字抠出来」「设计稿拆成 PNG」「每个字要单独动」「素材中心坐标是多少」时使用。含统一深色底反解 alpha 的算法、裁→缩→补的顺序铁律、`--scale` 与 `--out-scale` 的区别、`--pad` 必须用交付资产反向标定、发光会被扣进 alpha 的局限。
agent_created: true
---

# 从设计稿拆透明元素

下游:`ae-comp-builder`(读 `elements.json` 摆层)。
本 skill 只管**一张设计稿 → 一组 PNG + 坐标**,不碰工程。

**核心结论先行**:素材不透明度和坐标全部从**像素**反解,不靠人眼量。
量错 1px,后面 9 个合成全部偏。

## 铁律

1. **先确认底色**:只支持**统一深色底 + 亮色图形**;浅底/反色/多色渐变底直接说不适用,别硬跑
2. **顺序不可换**:裁到可见内容 → 缩到输出尺度 → 补对称透明边距
3. **`--pad` 是输出像素**,同一套资产必须**同一个 pad**(本项目 56)
4. **`--out-scale` 决定坐标空间**,必须等于 `合成像素 / 页面 pt`;`--scale` 只影响边缘 AA
5. **`cx/cy` 用文件中心**:边距对称是前提,不对称先修素材
6. **先自动切块侦察,再 `--cells` 定框交付**;两边 `cx` 差 >1px 就是框给错了
7. **文件名一律 ASCII**(中文会被 sanitize 成 `_`,下游 `MISS`)

---

## §1 侦察:页面尺寸与底色

```bash
python - <<'PY'
import fitz
p = fitz.open(r"<设计稿>.ai")
for i, pg in enumerate(p):
    print(i, pg.rect, len(pg.get_drawings()))
PY
```

- `page.rect` 是 **pt**,不一定等于设计稿 px。打印出的 `1x WxH` 必须与合成尺寸**逐一对照**;
  对不上就先换算,再决定 `--out-scale`(本项目 `2048×1152 pt` → 合成 `2048×1152 px`,`--out-scale 1.0`)。
- 底色不用手填:`extract_assets.py` 取**四角中位数**当背景色并打印,与设计稿肉眼一致再继续。

## §2 定单元格

```bash
# 第一步:自动切块,只看结构(不交付)
python extract_assets.py page.ai --out _tmp_probe --prefix QQ
```

看输出里的 `cells` 与 `cx`,**只用来确认元素个数与分组**。
自动切块的两个已知行为:

| 现象 | 原因 |
|---|---|
| Logo 四个字被并成一块 | 字间距小于 `--gap`,自动合并 |
| 副标题拆成 N 块 | 字间距够大,能分开 |

⇒ 交付一律自己写 `cells.json`(`bbox` 用 **1x 页面坐标 / pt**):

```json
[
  { "name": "icon",   "bbox": [775, 476, 936, 607] },
  { "name": "logo_Q", "bbox": [938, 482, 1018, 601] },
  { "name": "tag_1",  "bbox": [770, 620, 826, 700] }
]
```

## §3 跑提取

```bash
python extract_assets.py page.ai --out out/QQ音乐 --prefix QQ --cells cells.json
```

关键参数:

| 参数 | 本项目取值 | 说明 |
|---|---|---|
| `--scale` | `2.0` | 超采样,只为边缘 AA 质量 |
| `--out-scale` | `1.0` | 输出像素 / 页面 pt,决定 `cx/cy` 空间 |
| `--pad` | `56` | 四周透明边距(**输出**像素) |
| `--thresh` | `8` | 非背景阈值 |

产物:

```
out/QQ音乐/
├── QQ_icon.png        # RGBA,可见内容居中,四周 56px 透明
├── QQ_logo_Q.png
└── elements.json      # {meta{...}, elements[{file,name,w,h,cx,cy}]}
```

## §4 验证:四条可证伪读数

| # | 判据 | 期望(本项目实测) | 怎么失败 |
|---|---|---|---|
| 0 | 每个 bbox 都有对应 PNG | 个数一致 | 少文件 ⇒ bbox 超出页面 |
| 1 | 文件尺寸 = 内容尺寸 + `2*pad` | icon `238×238`(内容 `126×127`) | pad 用了渲染尺度 ⇒ 尺寸差一倍 |
| 2 | alpha bbox 从 `(pad, pad)` 起 | icon 从 `(56,56)` | 边距不对称 / 没裁到可见内容 |
| 3 | `cx/cy` 与设计稿量的中心一致 | icon `855.75 / 541` | 用了渲染尺度 ⇒ 明显大于合成宽度 |

交叉验证:同一份设计稿**自动切块的 `cx`** 与**`--cells` 交付的 `cx`** 必须一致(差 >1px = 框错)。
本项目四个 Logo 字实测 `977.75 / 1056.75 / 1138.75 / 1220.5`,两组逐位相同。

最后目检:把 PNG 铺在黑底上看一遍(白边/黑边一圈就说明 alpha 反解过头)。

## §5 排查

| 现象 | 原因 |
|---|---|
| 导出图整体偏亮、边缘发白 | 半透明元素被归一化放大 ⇒ 加 `--unpremultiply` 并肉眼复核 |
| 图形外面带一圈光晕 | 设计稿里有发光/投影,被一起扣进 alpha |
| 尺寸正好差 2 倍 | `--out-scale` 与 `--scale` 混了 |
| 图层摆上去整体偏移 | `cx` 用了可见内容中心 / 边距不对称 |
| `MISS xxx.png` | 文件名非 ASCII 被 sanitize,清单里写的是原名 |
| 文字元素是方框 | 文本未转曲 |

## §6 脚本与文档

- [`../scripts/vector-extract/extract_assets.py`](../scripts/vector-extract/extract_assets.py) —— 反解 alpha + 单元格裁切 + `elements.json`
- [`../scripts/vector-extract/README.md`](../scripts/vector-extract/README.md) —— 参数表、三段顺序、局限
- 文档:[`../docs/从AI提取透明元素.md`](../docs/从AI提取透明元素.md)

## 与相邻 skill 的边界

| Skill | 分工 |
|---|---|
| `ae-vector-extract`(本) | 设计稿 → PNG + `elements.json` |
| `ae-comp-builder` | 下游:`elements.json` → `manifest.json` → 工程 |
| `ae-frame-verify` | 另一侧:成品抽帧与设计稿 bbox 比对 |
| `ae-crash-diagnose` | 与素材无关(那条链是脚本侧) |
