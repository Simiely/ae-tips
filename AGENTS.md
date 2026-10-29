# AGENTS.md · 项目规则

> 📌 **文档基线**:2026-10-29 v1.1.0 —— 新增方案 `s5v2`(最初经典:116px / 94→100 / 模糊 20→0 / 前 55% 收清,
> Logo Quart-out + 副标题 ease),并把第二次交付踩到的四个坑写回(参数控制用 null、`DONE$` 判据、
> `& -r` 的 null 报错、`expressionError` 的 `undefined` 假报)。
> 内容全部来自 `835_启动页` 两次实际交付(9 个合成 27 帧 + 3 个合成 15 帧),
> 口径为 **AE 2026(中文界面)/ Windows**。
> (**★★ 头号坑:AE 2026 的 `setTemporalEaseAtKey` 对多维亚属性不可用** —— Position 传 2 个 ease 直接报
> `由于参数 2,无法调用...值数组没有 1 元素`;Scale 传 2 个 ease **硬崩溃整个 AE 进程**(`try/catch` 接不住);
> Position 退到 1 个 ease 后**采样阶段仍然崩**。⇒ **本仓库一律用表达式做缓动,不碰该 API**
> · ★★ **`saveFrameToPng` 是异步写盘**:首轮 27 帧的日志全写"成功",**磁盘上 0 个文件** ——
> 根因是脚本跑完立即 `app.quit()`,写盘请求被进程退出吞掉;修法 = 每帧后 `$.sleep(900)` 再 `(new File(fn)).exists` 自查,
> 结尾 `$.sleep(2500)` 才算完
> · ★★ **日志必须逐行 open/append/close 落盘**:`File` 对象在 `close()` 时才真正写盘,
> 脚本中途硬崩 ⇒ 缓冲区全丢、日志为空 ⇒ **看起来像"脚本没跑"**。逐行落盘后崩溃点永远能定位
> · ★ **拼接 AE 对象会让进程硬崩**:`L("openInViewer " + ok)`、`L("ret=" + r)`(r 是 `saveFrameToPng` 返回值)
> 都实测崩过;**只能拼 `.name` / `.exists` / `.length` / 数字/字符串**
> · ★ **中文版 AE 里 `property("Slider")` / `property("Blurriness")` 返回 `null`** ⇒ 一律按**索引**取
> (`effect(1)`、`fx.property(1)`、`fx.property(3)`)
> · ★ **`dimensionsSeparated = true` 之后再 `ps.property(1)` 会崩** ⇒ 分离维度方案整条放弃
> · ★ **冷启动要先等窗口**:同一进程里 `Start-Process` → 轮询 `MainWindowTitle` 非空 → 才 `-r <jsx>`,
> 否则脚本静默不执行、日志为空
> · ★ **抽帧文件名用 ASCII**:中文/空格名在首轮里出现"日志成功、文件不存在",换 `c<N>_t<T>.png` 后稳定)

## 仓库定位

沉淀**用脚本批量做 AE 工程**的实战结论:不是"AE 快捷键合集",而是
**「设计稿 → 素材 → 工程 → 抽帧核验」这条链上每一环的可复现做法与硬坑**。
服务对象是**要让 AI 助手照着干**的场景(批量启动页、片头、字幕条、多品牌多方案)。

## 技术栈与环境事实

| 项 | 事实 |
|---|---|
| 应用 | Adobe After Effects **2026**(Windows) |
| 可执行 | `C:\Program Files\Adobe\Adobe After Effects 2026\Support Files\AfterFX.exe` |
| 脚本 | ExtendScript `.jsx`,**ES3 语法**;入口 `afterfx -r <jsx>` |
| 工程 | `.aep`(`app.newProject()` → 建合成 → `app.project.save(new File(path))`) |
| 界面 | **中文版** ⇒ 属性名查找不可靠,按索引取 |
| 抽帧 | `comp.openInViewer()` + `viewer.saveFrameToPng(time, file)`(**异步**) |
| 辅助 | Python 3(PyMuPDF 拆素材、Pillow/numpy 做像素判据)、PowerShell 5.1 跑启动通道 |

> 与 blender-tips 的关键差异:**AE 没有常驻脚本通道**。Blender 有 9877 桥可以反复 exec,
> AE 只能「**起进程 → 跑脚本 → 退出**」,所以**一次 `.jsx` 必须把所有事做完**,
> 中途状态只能靠**日志文件**回传 —— 这就是本仓库把"日志纪律"放在铁律第一条的原因。

## 目录约定

```
ae-tips/
├── README.md          主题索引表(一句话一主题)
├── AGENTS.md          本文件:规则 + 关键坑清单 + 文档基线
├── DEVELOPMENT.md     架构说明 + 关键问题(一坑一篇)
├── CHANGELOG.md       版本记录(每版一个 ## vX.Y.Z · 日期)
├── docs/              主题手册(人读)
├── scripts/           脚本包(人读 README + 可跑脚本)
└── skills/            Agent Skill(SKILL.md + 引用 ../scripts/)
    └── README.md      技能清单 + 安装三件套 + 断链校验
```

**相对路径只允许一级**:从 `skills/<名>/` 出发写 `../scripts/`、`../docs/`;
写成 `../../` 会落到安装根之外,**静默断链**(blender-tips 踩过,本仓库开局就按一级写)。

## 写作纪律

1. **只写跑过的结论**。每条做法后面跟当时的读数或报错原文;没跑通的标「未验证」,不写"应该可以"。
2. **一坑一篇**。`DEVELOPMENT.md` 一个问题一节,格式固定:`**TL;DR**` → 问题 → 根因 → 解决 → 预防。
3. **判据可证伪**。验收一律写"什么读数算失败",而不是"看起来对了"。
4. **先怀疑度量,再怀疑被测对象**。判"两张图一样"不能比 md5(时间戳块会让 md5 不同),要**比像素**。
5. **失败要留诊断**。脚本报 FAIL 时同时打印差异的位置/幅度,一眼分辨"量化台阶"还是"真坏了"。

## 关键坑清单(按杀伤力排序)

| 级 | 坑 | 判据 / 修法 |
|---|---|---|
| ★★★ | `setTemporalEaseAtKey` 多维亚属性 | Position 报错、Scale **硬崩进程** ⇒ 用表达式缓动,见 [主题 2](docs/表达式缓动与滑块控制.md) |
| ★★★ | 参数控制用 solid | 不透明黑层盖住整幅画面,**日志全正常** ⇒ 抽帧 bbox 退化成 `(0,0,W,H)`;改 `addNull` |
| ★★★ | `saveFrameToPng` 异步写盘 | 日志成功 ≠ 文件存在 ⇒ 每帧 `$.sleep(900)` + `exists` 自查 |
| ★★ | 日志不落盘 | `File` 只在 `close()` 写盘 ⇒ 逐行 open/append/close |
| ★★ | `DONE` 判据写成 `^DONE` | 日志行首是时间戳 ⇒ 永远匹配不到,成功的构建被报"中途崩"、退出码 1 ⇒ 用 `DONE$` |
| ★★ | `& AfterFX.exe -r` | 嵌套 PowerShell 里退出后抛 null 报错(脚本其实跑完了)⇒ 改 `Start-Process` |
| ★★ | 拼接 AE 对象进字符串 | 进程硬崩 ⇒ 只拼标量 |
| ★★ | 中文版属性名 | `property("Slider")` = `null` ⇒ 按索引 |
| ★ | `expressionError` 的 `undefined` | 合成级会假报 `EXPR_ERR <合成名> :: undefined` ⇒ 判 `typeof err === "string"` |
| ★ | 模糊入场时像素数非单调 | 模糊扩散让中段比终帧多(实测 31649 → 29685)⇒ 用 bbox 上沿判"在动" |
| ★ | 冷启动未等窗口 | `-r` 静默不执行 ⇒ 轮询 `MainWindowTitle` |
| ★ | `.ps1` 无 BOM | PS 5.1 按 ANSI 读 ⇒ 中文提示乱码 ⇒ 存 UTF-8 with BOM |
| ★ | `dimensionsSeparated` | 分维度后取属性崩溃 ⇒ 不分离 |
| ★ | 抽帧中文文件名 | 文件不落盘 ⇒ ASCII 名 |

## 更新纪律

改任何代码或文档后,同一次提交内完成三件事:

1. **更新本文件顶部「文档基线」**(日期 + 版本 + 一句话说明本版改了哪条);
2. **`CHANGELOG.md` 顶部追加 `## vX.Y.Z · 日期`** 段,含实测读数;
3. **同步索引**:`README.md` 主题表、`skills/README.md` 技能表与技能总数。
   新增/删除技能时,`skills/README.md` 的「清单」行数与 `skills/` 目录数**必须零差集**。

提交前跑一次 `skills/README.md` 里的**断链校验**,判据 **断链 = 0**。
