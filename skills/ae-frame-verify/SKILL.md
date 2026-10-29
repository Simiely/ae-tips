---
name: ae-frame-verify
description: 对 AE 抽帧产物做数字核验——非背景包围盒、像素数、与设计稿期望包围盒比对、滑块前后差分,并拼联系表。当用户说「怎么证明做对了」「抽帧出来对一下位置」「AE 说成功但文件没生成」「比对一下和设计稿偏了多少」「滑块改了到底有没有生效」时使用。含 saveFrameToPng 异步写盘的判据、为什么不能用 md5 判两图相同、四条可证伪判据与容差。
agent_created: true
---

# 抽帧核验

上游:`ae-script-runner`(怎么抽帧)、`ae-comp-builder`(抽哪些时间点)。
本 skill 只管**把 PNG 变成数字,并用判据说"对"或"不对"**。

**核心结论先行**:AE 不会因为"做错了"报错。唯一可靠的判据是**抽帧后的像素读数**。

## 铁律

1. **判据先写清"什么算失败"**,再看结果
2. **不信日志的"成功"**:`saveFrameToPng` 是异步,只信 `(new File(fn)).exists`
3. **不用 md5 判两图相同**(PNG 含时间戳块 ⇒ md5 不同而像素可完全相同)
4. **背景色从清单取**,不凭眼睛填
5. **至少两条独立判据**:"在动"(单调性)+ "停在对的位置"(bbox)
6. **联系表只给人看,不进判据**

---

## §1 先侦察:帧齐不齐

```bash
python - <<'PY'
import glob, re, os
fs = glob.glob(r"<render_dir>/*.png")
groups = {}
for p in fs:
    m = re.match(r"(c\d+)_t(\d+)\.png", os.path.basename(p))
    if m: groups.setdefault(m.group(1), []).append(int(m.group(2)))
for k in sorted(groups, key=lambda s:int(s[1:])):
    print(k, len(groups[k]), sorted(groups[k]))
PY
```

判据:**每个 `c<N>` 的帧数**应等于清单里 `shoot` 的长度。

## §2 跑核验

```bash
python verify_frames.py <render_dir> --bg 0F0F11 --expect expects.json --contact contact.png
```

`expects.json`:

```json
{ "c1": { "name": "QQ音乐_方案1", "bbox": [792, 477, 1256, 677], "tol": 4 } }
```

## §3 四条判据

| # | 判据 | 失败意味着 | 开关 |
|---|---|---|---|
| 0 | `pixels > 0` | 抽帧没落盘 / 图层全透明 | 默认 |
| 1 | 像素数随时序单调不减 | 入场方向反了 / 元素中途消失 | `--strict-monotonic`(回弹方案别开) |
| 2 | 末帧 bbox 在期望 ±`tol` | 位置 / 尺寸 / 边距错 | `--expect` |
| 3 | 改滑块后同一时间点 bbox 必须变 | 表达式没读到滑块 | 手工两步抽帧 |

判据 1 与 2 **互相独立**:只做 2 会漏"根本没动"。

## §4 实测

```
c7   0.000   2048x1152   (787, 488, 1250, 613)     24324
c7   0.120   2048x1152   (787, 477, 1250, 603)     24554
c7   0.280   2048x1152   (787, 477, 1258, 678)     27419
FAIL=0  合成数=9  帧数=27
```

末帧 bbox:QQ `792–1256 / 477–677`、K歌 `796–1256 / 484–681`、懒人 `787–1257 / 477–677`。

滑块差分:`图标时长` 500→1000ms,`t=0.12s` 图标顶边 **486px → 497px**(差 11px ⇒ 生效)。

## §5 排查

| 现象 | 原因 |
|---|---|
| 目录里 0 个 PNG | 抽帧异步被 quit 吞了 / 文件名非 ASCII |
| 帧数比 `shoot` 少 | 某帧写盘超时,`sleep` 不够 |
| 全背景(`pixels=0`) | 表达式把不透明度算成 0 / 素材 alpha 全 0 |
| bbox 整体偏 N px | 素材边距不对称 / `cx` 用了内容中心 |
| 像素数中途回落 | 动画有回弹或元素消失;若设计如此,别开 `--strict-monotonic` |

## §6 脚本与文档

- [`../scripts/frame-verify/verify_frames.py`](../scripts/frame-verify/verify_frames.py) —— bbox / 像素数 / 联系表 / 期望比对
- [`../scripts/frame-verify/README.md`](../scripts/frame-verify/README.md) —— 文件名约定与三条判据
- 文档:[`../docs/抽帧核验.md`](../docs/抽帧核验.md)

## 与相邻 skill 的边界

| Skill | 分工 |
|---|---|
| `ae-frame-verify`(本) | 产物侧的**判据** |
| `ae-script-runner` | 抽帧**动作本身**与落盘 |
| `ae-crash-diagnose` | 脚本侧**为什么崩**,不是产物对错 |
