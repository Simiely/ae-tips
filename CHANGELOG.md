# CHANGELOG.md

## v1.1.0 · 2026-10-29

- **新增方案 `s5v2`「方案5 · 最初经典」** —— 来源 `方案5_动效调试.html` + 其动效时序图
  (时序图写明:调试页 1024 宽下的 `58px / 16px / 10px / 5px` 对应 2048 合成下的 `116px / 32px / 20px / 10px`)
  - Logo 整体(`logo_full`):`+116px`、`Scale 94→100`、`Blur 20→0`、`Opacity 0→100`;
    **透明度与模糊在前 55% 收清**(位移/缩放走满 100%),曲线 **Quart-out** `(0.25, 1, 0.5, 1)`
  - 副标题(逐字):`+32px`、`Blur 10→0`、`Opacity 0→100`,曲线 **ease** `(0.42, 0, 0.58, 1)`,延迟 100ms
  - **两个 role 曲线不同是本方案的实质特征**(旧 `s5` 是一条 out 曲线吃全片)
  - 生成器:新增 `CURVE["quartOut"]` / `CURVE["ease"]`,新增 `meta.sliders`(只声明实际用到的滑块组)
- **第二次交付(三品牌 × 方案5)** —— `manifest_s5v2.json` → `build_s5v2.jsx` → `.aep`
  - 合成 **3** 个(2048×1152 / 30fps / 3s),图层 **8 / 9 / 5**(+ BG + 参数控制),滑块 **5** 个
  - `expressionError count=0`;抽帧 **15/15 `exists=true`**;`.aep` **708,865 字节**;生成 jsx 46,567 字符
  - `verify_frames.py --allow-empty-start --expect expects_s5v2.json` ⇒ **FAIL=0 合成数=3 帧数=15**
  - 末帧 bbox:QQ `792–1257 / 477–678`、K歌 `795–1257 / 484–682`、懒人 `787–1258 / 477–678`;
    `t=0.5` 与 `t=1.2` 逐像素相同 ⇒ 动画 0.5s 收干净
  - 曲线自洽核对(取 `t=0.12`、`u=0.24`):Quart-out 反解得 `f≈0.67` ⇒ 残余位移 `116×0.33≈38px`、
    缩放 94% 再抬 3px ⇒ 上沿应约 `518px`,实测 **516**;`t=0.28`(u=0.56 ⇒ `u/0.55>1` ⇒ 模糊已收清)实测 **483**
- **★★★ 参数控制图层原来用了 solid,盖住整幅画面**:第一次抽帧全帧都是黑、
  `bbox=(0,0,2048,1152)`、`pixels=2,358,478`,而**日志一切正常**(`layers=10`、`DONE`、`.aep` 已存)。
  改成 `addNull` 后 `t=0` 全透明、`t=1.2` bbox 正常。⇒ 参数控制**必须用 null 对象**;`jsxlib.jsx` 同步修
- **★★ `run_ae.ps1` 的 `DONE` 判据写成 `^DONE`,永远匹配不到**:日志每行以 `Thu Oct 29 … GMT+0800  DONE` 开头 ⇒
  三次构建**全部成功却全部报"日志里没有 DONE"、退出码 1**。改为 `DONE$`
- **★★ `& $AePath -r $Jsx` 在嵌套 PowerShell 里抛 `You cannot call a method on a null-valued expression`**:
  脚本其实已跑完(日志有 `DONE`、`.aep` 已存,708,829 字节),只是包装层报错。改 `Start-Process` + 先等进程出现再轮询
- **★ 表达式体检把 `undefined` 当成错误**:`CompItem.expressionError` 是 `undefined`,
  判据 `err !== "" && err !== null` 会给**每个合成各报一条** `EXPR_ERR <合成名> :: undefined`(实测 3 条)。
  改为 `typeof err === "string" && err.length > 0` ⇒ `count=0`
- **★ 模糊入场时像素数不单调**:`t=0.12 → 0.28 → 0.5` 的像素数是 `25372 → 31649 → 29685`,
  模糊扩散让中段比终帧还多 ⇒ `--strict-monotonic` 在含模糊的方案上**必须关**;
  "在动"改用 bbox 上沿(`516 → 483 → 477`)
- **新增 `verify_frames.py --allow-empty-start`**:入场从 `opacity=0` 起步时首帧 `pixels=0` 是正常的,
  原判据会报 FAIL ⇒ 只放行**首帧**,其余仍要求 `>0`
- **`run_ae.ps1` 改存 UTF-8 with BOM**:PS 5.1 按 ANSI 读无 BOM 的 `.ps1`,中文提示全乱码(`[run_ae] 鍚姩 AE ...`)
- **文档同步**:`docs/从素材清单生成工程.md`(结构图 + 两组实测)、`scripts/comp-builder/README.md`(方案表 + 坑)、
  `scripts/ae-headless-run/README.md`(时序 + 3 条坑 + 实测)、`skills/ae-script-runner`(铁律 7/8 + 排查表)、
  `skills/ae-comp-builder`(铁律 1 + 方案表)、`skills/ae-frame-verify`(判据 0/1 + 方案5 实测)、`AGENTS.md`(基线 + 4 行坑)

## v1.0.0 · 2026-10-29

- **仓库建立**,7 个主题 + 7 个 Skill 入库。内容来自 `835_启动页` 三品牌三方案工程的实际交付:
  3 份 `.ai` 设计稿 → 素材 PNG + `manifest.json` → 9 个合成(2048×1152 / 30fps / 3s)→ `.aep`(2,281,249 字节);
  抽帧 27 张 + 滑块对照 2 张,全部 `exists=true`;9 个合成表达式 `expressionError` 全为空
- **主题 #1 无头运行 AE 脚本** —— `AfterFX.exe -r` 通道、冷启动轮询 `MainWindowTitle`、逐行落盘日志、`app.quit()` 收尾
  - ★★ 首轮最大的坑:**日志说 27 帧全成功,磁盘 0 个文件**。根因 `saveFrameToPng` 是**异步写盘**,
    末尾 `app.quit()` 把队列吞了。修法:每帧 `$.sleep(900)` + `(new File(fn)).exists` 自查,结尾 `$.sleep(2500)`
  - ★★ 日志**逐行 open/append/close** 才落盘(`File` 在 `close()` 才提交);否则崩溃一次日志就是空的,像"脚本没跑"
  - ★ 冷启动:`Start-Process` 后轮询 `MainWindowTitle` 非空 + `sleep 1500ms` 再 `-r`,否则静默不执行
  - 脚本包 `scripts/ae-headless-run/`(`run_ae.ps1` + `jsxlib.jsx`)、文档 `docs/无头运行AE脚本.md`、Skill `ae-script-runner`
- **主题 #2 表达式缓动** —— 表达式内 cubic-bezier 二分反解,与 CSS 的 `cubic-bezier()` 语义一致
  - ★★★ **`setTemporalEaseAtKey` 在 AE 2026 对多维亚属性不可用**:Position 传 2 个 ease 报
    `由于参数 2,无法调用...值数组没有 1 元素`;**Scale 传 2 个 ease 直接硬崩进程**(`try/catch` 接不住);
    Position 退到 1 个 ease 能过校验,但**采样阶段仍崩** ⇒ 整条放弃关键帧缓动
  - 采用的两条曲线:进厂 `cubic-bezier(0.16, 1, 0.3, 1)`,带回弹 `cubic-bezier(0.34, 1.56, 0.64, 1)`(y 可 >1,用于 Scale 超调)
  - 脚本包 `scripts/expression-tween/`、文档 `docs/表达式缓动与滑块控制.md`、Skill `ae-expression-tween`
  - ★ **`dimensionsSeparated = true` 后再取 `property(1)` 会崩** ⇒ 需要分轴就在表达式里拆数组,不改属性结构
- **主题 #3 参数控制图层** —— 一个「参数控制」图层挂 10 个滑块(图标/文字/副标题/Logo 整体 的时长、延迟、错位),
  表达式按 `C.effect("<中文名>")(1)` 取值;时长单位 ms、表达式内 `/1000` 换秒
  - ★ 中文界面下 `property("Slider")` 返回 `null` ⇒ 滑块值按 **`effect(1)`** 取;模糊/重复边缘像素同理按索引
  - 实测滑块生效:`图标时长` 500→1000ms,同一 `t=0.12s` 帧的图标顶边 **486px → 497px**
  - Skill `ae-slider-control`(与 #2 共用脚本包)
- **主题 #4 从素材清单生成 `.aep`** —— Python 读 `manifest.json` 生成 `.jsx`(`DATA` 内联,免 AE 侧 JSON 解析)
  - 结构:每个品牌 × 每个方案一个合成;背景 solid 锁定;「参数控制」置顶;图层按 `makeLayer` 统一挂表达式
  - 脚本包 `scripts/comp-builder/`(`build_aep.py` 泛化版)、Skill `ae-comp-builder`
  - ★ 生成器迭代 `data["brands"]` 而非根节点(根节点带 `meta`,直接迭代报 `KeyError: 'icon'`)
- **主题 #5 抽帧核验** —— `verify_frames.py` 统计每帧非背景 bbox/像素数,拼联系表;滑块对照单独比
  - 判据:**非背景 bbox 必须在原稿包围盒 ±4px 内**;1.2s 终态实测 QQ `792–1256 / 477–677`、
    K歌 `796–1256 / 484–681`、懒人 `787–1257 / 477–677`
  - ★ 判"两张图一样"**不能比 md5**(PNG 含时间戳块 ⇒ md5 不同而字节数可能完全相同)⇒ **比像素**
  - Skill `ae-frame-verify`
- **主题 #6 从 `.ai`/`.pdf` 拆透明元素** —— PyMuPDF 2x 渲染 + 与背景色 `#0F0F11` 做 difference 反解 alpha
  + 单元格裁切 + 56px 透明边距
  - 产出:QQ icon `238×239` @ `cx855.75 cy541`;logo 逐字 4 个(间距约 79–82px);`logo_full` 三品牌分别 `577×239` / `574×240` / `575×237`
  - 脚本包 `scripts/vector-extract/`、文档 `docs/从AI提取透明元素.md`、Skill `ae-vector-extract`
- **主题 #7 脚本崩溃与静默失败排查** —— 按命中率排序:拼接 AE 对象(硬崩)、日志不落盘、中文属性名、
  冷启动未就绪、抽帧非 ASCII 名
  - Skill `ae-crash-diagnose`
- **索引**:`README.md`(主题表 7 行)、`skills/README.md`(技能表 7 行 + 安装三件套 + 断链校验)、本文件
- **结构校验(实测)**:`skills/` 子目录 **7** 个、`skills/README.md` 清单 **7** 行,零差集;
  7 个 SKILL.md 全部 `name` / `description` / `agent_created` 三键齐、无 BOM;
  `py_compile` 三个 Python 脚本通过、`run_ae.ps1` PowerShell 解析通过
  - **断链校验:技能数 7 / 相对链接目标 24 / 断链 0**
  - ★ **两个度量陷阱(实测各假报一次)**:① 只取 markdown 链接目标(方括号后紧跟圆括号的形式),
    不扫"全文像路径的串";② **必须先剥掉代码块** —— 检查脚本的注释里自带一条"链接目标示例",
    不剥就会把它当断链(假报 2 处)
  - ★ **仓库内直接拿 `skills/` 当检查根会全量假报 26 处**:`../scripts/` 是按**安装后**布局写的
    (安装时 `scripts/`、`docs/` 拷**进** `skills/` 里),而仓库里它们在上一级 ⇒ 要先做一次 staging 拷贝再校验
