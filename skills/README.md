# Agent Skills(给 AI 助手用的作业规范)

本目录收录供 AI 助手加载的 **Agent Skill**:每个子目录一个 skill,
内含 `SKILL.md`(YAML frontmatter:触发条件 + 作业步骤 + 硬约束),脚本**引用**同级 `../scripts/`。

## 和 `../scripts/` 的区别

| 目录 | 面向 | 内容形态 |
|---|---|---|
| `../scripts/` | **人** | 可复用脚本包:README(原理 / 参数 / 步骤 / 实测读数)+ 脚本 |
| `skills/` | **AI 助手** | 作业规范:怎么干、先干什么、什么绝对不能干,并**引用**同一份脚本 |

两者内容**有意重叠**,但**不复制脚本**:本仓库一律 `../scripts/<包>/` 引用(**只维护一份**,
不存在 blender-tips 里"自带 + 引用"两套约定混用的问题)。

## 清单(7 个)

| Skill | 作用 | 关联文档 / 脚本包 |
|---|---|---|
| `ae-script-runner` | **无头通道**:`AfterFX.exe -r <jsx>` 起进程 → 跑脚本 → 退出;冷启动轮询、日志纪律、抽帧异步等待、`DONE` 判结束 | [无头运行AE脚本](../docs/无头运行AE脚本.md) / [`../scripts/ae-headless-run/`](../scripts/ae-headless-run/) |
| `ae-expression-tween` | **表达式缓动**:cubic-bezier 二分反解替代 `setTemporalEaseAtKey`(2026 对多维亚属性会报错/硬崩);四条曲线的实测值、滑出/淡入/缩放/模糊四个原子动作 | [表达式缓动与滑块控制](../docs/表达式缓动与滑块控制.md) / [`../scripts/expression-tween/`](../scripts/expression-tween/) |
| `ae-slider-control` | **参数控制图层**:一个置顶图层 + 10 个中文滑块,驱动全片时长/延迟/错位;名字 vs 索引、ms→s 换算、勾稽与验证 | 同上 / [`../scripts/ae-headless-run/jsxlib.jsx`](../scripts/ae-headless-run/jsxlib.jsx) |
| `ae-comp-builder` | **从素材清单生成工程**:`manifest.json` → `build_aep.py` → `.jsx` → `.aep`;合成结构固定、role 决定滑块组、表达式在 Python 侧拼好、缓动源码两份逐字一致 | [从素材清单生成工程](../docs/从素材清单生成工程.md) / [`../scripts/comp-builder/`](../scripts/comp-builder/) |
| `ae-frame-verify` | **抽帧核验**:bbox / 像素数 / 与设计稿期望比对 / 滑块前后差分 / 联系表;四条可证伪判据,不用 md5 | [抽帧核验](../docs/抽帧核验.md) / [`../scripts/frame-verify/`](../scripts/frame-verify/) |
| `ae-vector-extract` | **设计稿拆透明元素**:统一深色底反解 alpha,单元格裁切,输出 PNG + `elements.json`(尺寸 + 合成坐标中心);裁→缩→补的顺序铁律 | [从AI提取透明元素](../docs/从AI提取透明元素.md) / [`../scripts/vector-extract/`](../scripts/vector-extract/) |
| `ae-crash-diagnose` | **失败定位**:进程闪退 / 日志 0 字节 / 日志成功但没文件 / 属性变红 / 存盘缺合成;七条路径按命中率排序 | [AE脚本崩溃排查](../docs/AE脚本崩溃排查.md) / [`../scripts/ae-headless-run/`](../scripts/ae-headless-run/) |

七个是**同一条链上的分工**,不是互相替代:

> `ae-vector-extract`(设计稿→素材)→ `ae-comp-builder`(素材清单→工程,内含 `ae-slider-control`
> 的控制契约与 `ae-expression-tween` 的缓动算法)→ `ae-script-runner`(把 `.jsx` 跑起来)
> → `ae-frame-verify`(产物对不对);
> `ae-crash-diagnose` 不在链上,它是**任何一环失败时**的分诊入口。

其中 `ae-expression-tween` / `ae-slider-control` 是**被 `ae-comp-builder` 引用的子规范** ——
单独改缓动或单独加滑块时才单独加载。

## 安装

⚠️ **只拷 `skills/` 会留下断链** —— 各 SKILL.md 用 `../scripts/<包>/` 与 `../docs/<文>.md` 引用同级目录,
必须**连同 `scripts/` 与 `docs/` 一起**拷到同一个父目录下。

```powershell
$dst = "$env:USERPROFILE\.workbuddy\skills"   # 改成你的助手 skill 目录
# 1) 7 个技能本体
Copy-Item .\skills\* $dst -Recurse -Force
# 2) 共享脚本包 —— 供 SKILL.md 里的 ../scripts/<包>/ 解析
Copy-Item .\scripts   $dst -Recurse -Force
# 3) 配套文档 —— 供 SKILL.md 里的 ../docs/<文>.md 解析
Copy-Item .\docs      $dst -Recurse -Force
```

装完**务必跑一次断链校验**:

```bash
python - <<'PY'
import os, re
SK = os.path.expanduser("~/.workbuddy/skills")   # 安装目录；仓库内自检改成 staging 目录(见下)
LINK = re.compile(r'\]\(([^)\s]+)\)')

def strip_fences(txt):   # ★ 先去掉 ``` 代码块
    out, infence = [], False
    for line in txt.splitlines():
        if line.lstrip().startswith("```"):
            infence = not infence; continue
        if not infence: out.append(line)
    return "\n".join(out)

bad = 0; n = 0
for d in sorted(os.listdir(SK)):
    p = os.path.join(SK, d, "SKILL.md")
    if not os.path.isfile(p): continue
    for t in sorted(set(LINK.findall(strip_fences(open(p, encoding="utf-8-sig").read())))):
        if t.startswith(("http://", "https://", "#", "mailto:")): continue
        base = t.partition("#")[0]
        if not base: continue
        n += 1
        if not os.path.exists(os.path.normpath(os.path.join(os.path.dirname(p), base))):
            print("MISS", d, "->", t); bad += 1
print("检查了 %d 个相对链接目标, 断链: %d" % (n, bad))
PY
```

判据:**断链 = 0**。非 0 = 漏拷 `scripts/` / `docs/`,或 SKILL.md 里的相对层级写错。

两条实测过的度量陷阱(都是**先怀疑度量**的例子):

1. **不要"扫全文里所有像路径的串"**,只取 markdown 链接目标 `](...)`。
   否则反引号里的**显示文本**也被算进来 —— `[`docs/x.md`](../docs/x.md)` 这种写法显示文本少一级,
   健康的仓库会被假报。
2. **必须先剥掉 ` ``` ` 代码块**。本文件里的检查脚本自己就有 `](target)` 这样的注释,
   不剥代码块会让检查器把自己的示例当成断链(实测假报 2 处)。

> **相对层级约定(易错)**:从 `skills/<名>/` 出发,正确写法是 **`../scripts/`** 与 **`../docs/`**(一级)。
> 写成 `../../`(两级)会落到安装根之外,**静默断链**。
>
> ⚠️ **仓库内自检要先做 staging**:这层相对路径是按**安装后**布局写的(安装时 `scripts/`、`docs/`
> 是**拷进** `skills/` 里),而仓库里它们在 `skills/` 的**上一级**。直接拿仓库的 `skills/` 当根,
> 会全量假报 26 处(实测)。做法:

```powershell
$stage = "$env:TEMP\ae-tips-stage"
Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory $stage | Out-Null
Copy-Item .\skills\* $stage -Recurse -Force
Copy-Item .\scripts  $stage -Recurse -Force
Copy-Item .\docs     $stage -Recurse -Force
# 然后把上面脚本里的 SK 改成 $stage
```

判据同样是 **断链 = 0**。

拷完目录结构:

```
~/.workbuddy/skills/
├── README.md
├── ae-script-runner/SKILL.md
├── ae-expression-tween/SKILL.md
├── ae-slider-control/SKILL.md
├── ae-comp-builder/SKILL.md
├── ae-frame-verify/SKILL.md
├── ae-vector-extract/SKILL.md
├── ae-crash-diagnose/SKILL.md
├── scripts/            # 三件套之二:ae-headless-run / expression-tween / comp-builder / frame-verify / vector-extract
└── docs/               # 三件套之三:7 篇主题手册
```

> 各 skill 目录下**没有** `scripts/` —— 脚本包只有一个副本,在 `../scripts/<包>/`。

## 维护约定

1. **脚本只改一处**:改 `../scripts/<包>/` 即对全部 skill 生效(没有副本要同步)。
2. **改完跑一次断链校验**,判据 `断链 = 0`。
3. **清单行数必须与 `skills/` 子目录数零差集**(当前 7 / 7)。
4. **新增 skill**:同时更新 `README.md` 主题表、本文件清单、`CHANGELOG.md` 与 `AGENTS.md` 的文档基线。
