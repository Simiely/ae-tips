# DEVELOPMENT.md · 架构与问题记录

## 项目概览

AE 脚本化技巧仓库:沉淀「**设计稿 → 素材 → `.aep` 工程 → 抽帧核验**」这条链上验证过的做法。
核心资产是 [`docs/技巧速查.md`](docs/技巧速查.md),配套 AGENTS / CHANGELOG 按单项目规范维护。
当前内容全部来自一次真实交付:3 个品牌 × 3 套动效方案 = 9 个合成,2048×1152 / 30fps,产物 `.aep` 2,281,249 字节。

## 架构说明

**流水线**(每一环都可单独复跑):

```
设计稿  .ai / .pdf(矢量,统一深色底)
   │  ① scripts/vector-extract/extract_assets.py
   │     2x 渲染 → 与背景色做 difference → 反解 alpha → 单元格裁切 → +56px 透明边距
   ▼
素材  <输出目录>/<品牌>/*.png  +  manifest.json(每元素 w/h/cx/cy)
   │  ② scripts/comp-builder/build_aep.py
   │     读 manifest → 生成 build_<名>.jsx(DATA 内联,不依赖外部 JSON 解析)
   ▼
脚本  build_<名>.jsx  (ES3;合成/图层/表达式/抽帧全在一份里)
   │  ③ scripts/ae-headless-run/run_ae.ps1
   │     起 AE → 轮询 MainWindowTitle → -r <jsx> → 等进程退出 → 读日志
   ▼
产物  <名>.aep  +  ae_render/c<N>_t<T>.png
   │  ④ scripts/frame-verify/verify_frames.py
   ▼
判据  非背景像素 bbox / 像素数 / 滑块对照差分 → 回填 manifest 与 CHANGELOG
```

**为什么是"脚本全部做完"而不是"分步调 API"**:
AE 没有常驻脚本通道(不像 Blender 有 9877 桥)。`afterfx -r` 起的是一个**一次性进程**,
脚本里 `app.quit()` 后才退出;所以**建工程、挂表达式、抽帧、存盘必须在同一份 `.jsx` 里串完**,
中间状态只能靠**日志文件**回传。这是本仓库所有纪律的源头。

**为什么动画用表达式而不是关键帧**:
`setTemporalEaseAtKey` 在 AE 2026 对多维亚属性不可用(见下"问题 1"),而
**表达式 + 滑块**的方案同时解决了三件事:① 缓动可控且与 CSS 对齐;② 时长/延迟/错位**集中在一处**;
③ 改参数**不需要重打关键帧**,交付方自己能调。

## 关键问题与方案(一坑一篇)

## 问题:AE 2026 `setTemporalEaseAtKey` 对多维亚属性不可用,且会硬崩

**TL;DR**:Position/Scale 不要用这个 API;缓动一律走表达式。

- 问题:给 Position 打关键帧后设缓动:
  `ps.setTemporalEaseAtKey(1, [ease], [ease])` 传 2 个 ease → 报 `由于参数 2,无法调用 ... 值数组没有 1 元素`
- 根因:该 API 对**多维亚属性**要求"每个维度一套 ease",但 2026 的实现在参数校验与内存访问上都不对;
  Position 退到 **1 个 ease** 后**能过校验**,却在之后的**采样/渲染阶段**崩(不是当场崩,更难查)
- 更严重:Scale 传 2 个 ease **直接让 AE 进程消失**,`try/catch` 接不住(不是脚本异常,是进程级崩溃)
- 解决:**整条放弃关键帧缓动**,改表达式(`scripts/expression-tween/tween.jsx`)
- 预防:任何"多维亚属性 + ease"的组合先假设不可用;要看缓动效果就**抽帧看**,别信 API 返回

## 问题:`saveFrameToPng` 是异步写盘,进程退出会吞掉未落盘的文件

**TL;DR**:调用成功 ≠ 文件存在;每帧后必须 sleep + `exists` 自查。

- 问题:首轮 27 帧,日志逐行打印"frame c1_t0 ... ok",但 `ae_render/` **一个文件都没有**
- 根因:`viewer.saveFrameToPng(time, file)` 只是**投递**一个写盘任务,真正落盘在之后的空闲周期;
  脚本连续投递 27 个 + 末尾 `app.quit()`,进程退出时队列里未完成的写入全部丢失
- 解决:每帧投递后 `$.sleep(900)`,再 `(new File(fn)).exists` 自查并把结果写进日志;末尾 `$.sleep(2500)` 再退出
- 实测:加 sleep 后 27/27 帧 `exists=true`;滑块对照 2 张同样落盘
- 预防:任何"AE 自己写文件"的 API(抽帧、导出、渲染)都按**异步**对待,判据只信 `exists`

## 问题:日志文件为空,看起来像"脚本没跑"

**TL;DR**:`File` 只在 `close()` 时落盘;逐行 open/append/close。

- 问题:脚本中途硬崩后,日志文件存在但**0 字节**,无法定位崩在哪
- 根因:ExtendScript 的 `File` 写入先进缓冲区,`close()` 才提交;进程被崩溃带走 ⇒ 缓冲区全丢
- 解决:日志函数 `L()` 每次 **open → writeline → close**,代价是 IO 慢一点,换来"崩溃点永远可见"
- 实测:改用逐行落盘后,`dimensionsSeparated` 那次崩溃的**最后一行**正好是被崩的语句
- 预防:调试期一律逐行落盘;正式跑也不关,日志量对这点帧数无所谓

## 问题:把 AE 对象拼进字符串 → 进程硬崩

**TL;DR**:只有标量能进字符串。

- 问题:`L("openInViewer " + ok)`、`L("ret=" + r)`(r 为 `saveFrameToPng` 返回值)两处都崩
- 根因:ExtendScript 对这些宿主对象做 `toString` 时走进未实现的路径,直接终止进程;
  **不是抛异常**,是进程消失 ⇒ 日志停在上一行
- 解决:只拼 `.name` / `.exists` / `.length` / 数字 / 字符串;需要记录对象就记它的 `name`
- 预防:**不要写"万能日志"把参数原样拼进去**;日志函数只接受标量

## 问题:中文版 AE 里按英文名取属性返回 null

**TL;DR**:按索引取,不按名字。

- 问题:`effect.property("Slider")`、`fx.property("Blurriness")` 都返回 `null`,后续 `setValue` 报错
- 根因:AE 的 `property(name)` 走的是**本地化显示名**;中文界面下叫「滑块」「模糊度」
- 解决:一律索引 —— 滑块控件 `effect(1)`、高斯模糊的模糊度 `fx.property(1)`、
  "重复边缘像素" `fx.property(3)`
- 预防:凡是"标准效果的标准参数",先用索引试通,再考虑名字;名字只用于**自己命名的**属性

## 问题:`dimensionsSeparated` 之后取属性崩溃

**TL;DR**:不要分离维度。

- 问题:想分维度控 Position,设 `ps.dimensionsSeparated = true` 后再 `ps.property(1)` → 崩溃
- 根因:2026 在分离维度后的属性组重建上不稳定
- 解决:放弃分维度;**需要独立控制 X/Y 就在表达式里拆数组**(`p[0]`/`p[1]`),不动属性结构
- 预防:能用表达式解决的,不要改属性结构

## 问题:冷启动时 `-r` 静默不执行

**TL;DR**:等主窗口标题非空再 `-r`。

- 问题:`Start-Process AfterFX.exe` 后紧接着 `-r script.jsx`,日志为空、工程未生成
- 根因:AE 冷启动几秒到十几秒;进程存在 ≠ 应用就绪,`-r` 被丢弃
- 解决:轮询 `Get-Process AfterFX | Where MainWindowTitle -ne ""`,拿到窗口后 `Start-Sleep 1500ms` 再 `-r`
- 预防:见 [`scripts/ae-headless-run/run_ae.ps1`](scripts/ae-headless-run/run_ae.ps1),已在多次复跑中稳定

## 问题:抽帧文件名带中文/空格时文件不落盘

**TL;DR**:抽帧名用 ASCII。

- 问题:文件名带品牌中文名时,日志写"ok"但文件不存在;改成 `c<N>_t<T>.png` 稳定
- 根因:与异步写盘叠加后,非 ASCII 名在某些路径上失败得更早,且**不报错**
- 解决:抽帧名固定 ASCII,中文只进**日志文本**和**图层名**(图层名不影响写盘)
- 预防:凡是"要被别的进程读"的文件名,一律 ASCII

## 问题:生成器读 manifest 时 `KeyError: 'icon'`

**TL;DR**:清单根节点包了一层 `brands`。

- 问题:`for brand, b in data.items()` 直接迭代根节点,报 `KeyError: 'icon'`
- 根因:manifest 结构是 `{ "brands": { "QQ音乐": {...} } }`,根节点还带 `meta` 字段
- 解决:迭代 `data["brands"].items()`;生成器里对 `meta` 显式 `continue`
- 预防:生成器**先打印清单的键路径**再动手,比读代码快
