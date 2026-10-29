---
name: ae-script-runner
description: 通过系统命令行无头运行 Adobe After Effects 2026 的 ExtendScript(.jsx)——起进程、等主窗口就绪、afterfx -r、等进程退出、回读日志。当用户说「跑一下这个 jsx」「无头生成 aep」「不开 AE 界面把工程做出来」「AE 跑完没反应/日志是空的」「脚本执行到一半崩了」时使用。含冷启动时序、日志逐行落盘、app.quit() 收尾、超时与残留实例处理。
agent_created: true
---

# 无头运行 AE 脚本

本 skill 管**通道**:怎么让 `.jsx` 在没人点界面的情况下跑完,并且**留下可诊断的证据**。
动画怎么写见 `ae-expression-tween`;工程怎么组织见 `ae-comp-builder`。

**核心结论先行**:AE 没有常驻脚本通道,`-r` 起的是**一次性进程**;
所以一次 `.jsx` 必须把所有事做完,成败只能靠**日志文件**回传 —— 这也是本 skill 把日志纪律放在第一位的原因。

## 铁律

1. **先杀残留实例**:已有 AfterFX 在跑时 `-r` 会把脚本送进**那个**实例,时序不可控
2. **必须等主窗口**:轮询 `MainWindowTitle -ne ""` + `sleep 1500ms` 之后才 `-r`,否则**静默丢脚本**
3. **日志逐行 open/append/close**:`File` 在 `close()` 才落盘,硬崩时缓冲全丢
4. **日志只拼标量**:`L("x" + 对象)` 会让进程消失
5. **抽帧等写盘**:`$.sleep(900)` + `(new File(fn)).exists` 自查,结尾 `$.sleep(2500)`
6. **末尾 `app.quit()`**:这是 runner 判"结束"的唯一信号
7. **一次只改一个矛盾点**,卡住就停

---

## §1 先侦察:环境与前置

```powershell
Test-Path "C:\Program Files\Adobe\Adobe After Effects 2026\Support Files\AfterFX.exe"
Get-Process AfterFX -ErrorAction SilentlyContinue | Select-Object Id, MainWindowTitle
```

- 路径不存在 ⇒ 换 `-AePath`;
- 有实例 ⇒ `run_ae.ps1` 会自动清,但**先问一下用户**那个实例里有没有未存的工程。

## §2 写脚本:必须包含的五段

```javascript
#target aftereffects

// ① 路径常量(绝对路径,正斜杠)
var LOG_PATH   = "C:/temp/ae_build.log";
var RENDER_DIR = "C:/temp/ae_render";

// ② 日志(逐行落盘)
function L(s) {
    var f = new File(LOG_PATH);
    f.open("a");
    f.write(new Date().toString() + "  " + s + "\n");
    f.close();
}

// ③ 干活(建工程 / 建合成 / 挂表达式 …)

// ④ 抽帧(若需要)
comp.openInViewer();
comp.saveFrameToPng(t, new File(fn));
$.sleep(900);
L("frame " + fn + " exists=" + (new File(fn)).exists);

// ⑤ 收尾
app.project.save(new File("C:/temp/out.aep"));
$.sleep(1500);
L("saved exists=" + (new File("C:/temp/out.aep")).exists);
L("DONE");
$.sleep(2500);
app.quit();
```

> 现成的公共库:[`../scripts/ae-headless-run/jsxlib.jsx`](../scripts/ae-headless-run/jsxlib.jsx)

## §3 跑起来

```powershell
.\run_ae.ps1 -Jsx C:\temp\build.jsx -Log C:\temp\build.log -TimeoutSec 300
```

参数:`-Jsx`(必填)、`-Log`(默认 `<jsx 同名>.log.txt`)、`-TimeoutSec`、`-AePath`、`-KeepRunning`。

## §4 验证:看日志,不看感觉

| 日志现象 | 结论 | 下一步 |
|---|---|---|
| 文件不存在 | 脚本没被执行 | 查冷启动时序(是不是没等窗口) |
| 存在但 0 字节 | 日志没逐行落盘 | 改 `L()` 为 open/append/close |
| 有内容、无 `DONE` | 中途硬崩 | **最后一行就是崩溃点** |
| 有 `DONE`、无 `saved ... exists=true` | 存盘失败 | 查路径与权限 |
| `frame ... exists=false` | 抽帧被进程退出吞 | 加 `sleep`;文件名换 ASCII |

`run_ae.ps1` 退出码:`0` = 有 `DONE`;`1` = 日志无 `DONE`;`2` = 日志不存在。

再叠一层产物判据:[`../scripts/frame-verify/verify_frames.py`](../scripts/frame-verify/verify_frames.py) 必须 `FAIL=0`。

## §5 排查

| 现象 | 最可能原因 |
|---|---|
| 进程直接消失 | 拼接 AE 对象进字符串 |
| 日志空 | 冷启动未就绪 / 未逐行落盘 |
| 日志成功但无文件 | 异步写盘 + 立即 quit |
| `afterfx -r` 返回但什么都没发生 | 脚本被已有实例吞了 / 路径含中文 |
| 超时被杀 | 脚本没有 `app.quit()` |

## 脚本

- [`../scripts/ae-headless-run/run_ae.ps1`](../scripts/ae-headless-run/run_ae.ps1) —— 进程时序(启动 / 等窗口 / `-r` / 等退出 / 回读日志)
- [`../scripts/ae-headless-run/jsxlib.jsx`](../scripts/ae-headless-run/jsxlib.jsx) —— jsx 侧公共库(`L` / `newComp` / `addBg` / `addController` / `placeLayer` / `setTransformExpr` / `addBlur` / `shoot` / `reportExprErrors` / `finish`)

文档:[`../docs/无头运行AE脚本.md`](../docs/无头运行AE脚本.md)

## 与相邻 skill 的边界

| Skill | 分工 |
|---|---|
| `ae-script-runner`(本) | **怎么把脚本跑起来并拿到证据**;不管脚本内容 |
| `ae-comp-builder` | 脚本里"建什么合成、放什么层" |
| `ae-expression-tween` | 脚本里"挂什么表达式" |
| `ae-frame-verify` | 脚本外"产物对不对" |
| `ae-crash-diagnose` | 已经崩了,**怎么定位** |
