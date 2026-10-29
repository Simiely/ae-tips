# After Effects 技巧速查

> 日常 AE 脚本化踩坑与可复用技巧的速查手册,按主题索引。
> 结构沿用 [blender-tips](https://github.com/Simiely/blender-tips) 的单项目规范。

## 这是什么

记录在 **After Effects 2026(ExtendScript / `.jsx`)** 实战中验证过的技巧,每个主题含**场景 → 做法 → 坑**。
本仓库**只收实测结论**:每条做法后面都跟着当时跑出来的读数(帧数、字节数、报错原文),
没跑通的一律标"未验证",不写成结论。

覆盖:

| # | 主题 | 一句话 |
|---|---|---|
| 1 | 无头运行 AE 脚本 | `AfterFX.exe -r` 跑 `.jsx`,不点界面也能建工程、存盘、抽帧 |
| 2 | 表达式缓动 | 用表达式里的 cubic-bezier 反解做缓动,**绕开 `setTemporalEaseAtKey` 在 2026 的崩溃** |
| 3 | 参数控制图层 | 一个「参数控制」图层 + 一组滑块,驱动整条时间线的时长/延迟/错位 |
| 4 | 从素材清单生成 `.aep` | Python 读 `manifest.json` → 吐 `.jsx` → AE 里跑成多合成工程 |
| 5 | 抽帧核验 | `saveFrameToPng` **异步写盘**,必须等;用 bbox 与原稿比对判"做对了" |
| 6 | 从 `.ai`/`.pdf` 拆透明元素 | 统一背景反解 alpha + 单元格裁切,把设计稿拆成可独立做动画的 PNG |
| 7 | 脚本崩溃与静默失败排查 | 拼接 AE 对象会硬崩、日志不落盘、中文版属性名取不到 —— 按命中率排序 |

## 和 `scripts/` 与 `skills/` 的关系

| 目录 | 面向 | 内容形态 |
|---|---|---|
| `docs/` | 人 | 主题手册:原理 / 参数 / 步骤 / 实测数据 / 坑 |
| `scripts/` | 人 | 可直接跑的脚本包(README + 脚本),每包一个主题 |
| `skills/` | AI 助手 | 作业规范:怎么干、先干什么、什么绝对不能干,并**引用**同一份脚本包 |

`skills/` **不放脚本副本**,一律 `../scripts/<包>/` 引用(只维护一份,不存在两处同步)。

## 环境事实(本机实测)

- AE:`C:\Program Files\Adobe\Adobe After Effects 2026\Support Files\AfterFX.exe`
- 脚本语言:**ExtendScript(ES3)**,没有 `let/const`、箭头函数、模板字符串、`Array.forEach`
  (引擎支持一部分,但不要赌;**统一写 ES3**)
- 界面语言:中文版 ⇒ `property("Slider")` 这类**英文名取不到**(返回 `null`),要按**索引**取
- 输出目录里**不要用中文/空格文件名**做抽帧名(实测改 ASCII 后才稳定落盘)

## Agent Skills(给 AI 助手用的作业规范)

`skills/` 目录收录 **Agent Skill**:`SKILL.md` 写清「怎么干、先干什么、什么绝对不能干」,
并把配套脚本作为附件**引用**进来,让 AI 助手不必每次重新推演流程与安全闸。
清单与安装方式见 [`skills/README.md`](skills/README.md)。

## 版本

见 [`CHANGELOG.md`](CHANGELOG.md)。当前 **v1.0.0**(2026-10-29),内容来自 `835_启动页` 三品牌三方案工程的实际交付。
