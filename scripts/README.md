# 脚本包（人读）

每个子目录一个主题:一份 README(原理 / 参数 / 步骤 / 实测数据) + 可跑脚本。
`skills/<名>/SKILL.md` 通过 `../scripts/<包>/` 引用这里的同一份文件,**不存在两处副本**。

| 包 | 作用 | 对应主题 | 对应 Skill |
|---|---|---|---|
| [`ae-headless-run/`](ae-headless-run/) | 起 AE → 等窗口就绪 → `afterfx -r <jsx>` → 等进程退出 → 回读日志;附 jsx 侧公共库 | [#1](../docs/无头运行AE脚本.md) | `ae-script-runner` |
| [`expression-tween/`](expression-tween/) | cubic-bezier 缓动的**表达式源码**、表达式生成器,以及**采样对表**(`probe_curve.jsx` + `compare_curve.py`) | [#2](../docs/表达式缓动与滑块控制.md) | `ae-expression-tween` |
| [`comp-builder/`](comp-builder/) | 读 `manifest.json` 生成 `.jsx`(多合成 / 背景 solid / 参数控制 / 全图层表达式) | [#4](../docs/从素材清单生成工程.md) | `ae-comp-builder` |
| [`frame-verify/`](frame-verify/) | 抽帧统计:非背景 bbox / 像素数 / 联系表 / 与期望包围盒比对 | [#5](../docs/抽帧核验.md) | `ae-frame-verify` |
| [`vector-extract/`](vector-extract/) | `.ai`/`.pdf` → 透明 PNG 元素 + `manifest.json`(背景反解 alpha) | [#6](../docs/从AI提取透明元素.md) | `ae-vector-extract` |

## 通用约定

- **所有脚本顶部都有 `OUT_DIR` / 路径常量**,跑之前先改;同一个包内多个脚本的常量必须一致。
- **Python 依赖**:`pymupdf`(拆素材)、`numpy`、`pillow`(只剩联系表与像素判据用)。
- **PowerShell**:`run_ae.ps1` 只负责进程时序,不解析 jsx 内容;成败一律看日志。
- **不写产物到仓库目录**:输出目录一律在仓库外(`.gitignore` 也把 `ae_render/`、`*.aep`、`*.log` 排除了)。
