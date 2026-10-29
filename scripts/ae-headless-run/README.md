# ae-headless-run · 无头运行 AE 脚本

不起界面、不点菜单,用一次进程把建工程 / 挂表达式 / 抽帧 / 存盘全做完。

## 为什么必须一条命令串完

AE 没有常驻脚本通道(不像 Blender 有 9877 桥可以反复 exec)。`afterfx -r <jsx>` 起的是**一次性进程**,
脚本末尾 `app.quit()` 才退出。所以:

- **所有步骤写在同一份 `.jsx` 里**;
- **中间状态只能靠日志文件回传**;
- **成败判定 = 进程退出 + 日志里有 `DONE`**。

## 文件

| 文件 | 作用 |
|---|---|
| `run_ae.ps1` | 进程时序:杀掉残留 → 启动 → 等 `MainWindowTitle` → `sleep 1.5s` → `Start-Process -r` → 等进程退出 → 回读日志 |
| `jsxlib.jsx` | jsx 侧公共库:`L()` / `newComp` / `addBg` / `addController` / `placeLayer` / `setTransformExpr` / `addBlur` / `shoot` / `reportExprErrors` / `finish` |

## 用法

```powershell
.\run_ae.ps1 -Jsx D:\work\build_start_page.jsx -Log D:\work\build_log.txt -TimeoutSec 300
```

判据:

| 现象 | 结论 |
|---|---|
| 日志不存在 | jsx **根本没被执行** → 先查冷启动时序(是不是没等窗口就 `-r`) |
| 日志有内容、无 `DONE` | 脚本**中途硬崩**,最后一行就是崩溃点 |
| 日志有 `DONE`、`saved ... exists=true` | 工程已存盘 |
| 日志有 `frame ... exists=false` | 抽帧被进程退出吞了 → 加 `$.sleep` |

## 四个必须知道的时序

1. **冷启动**:`Start-Process` 后立即 `-r` 会静默丢脚本。必须先轮询 `MainWindowTitle -ne ""`,再 `sleep 1500ms`。
2. **日志逐行落盘**:`File` 在 `close()` 才提交;`L()` 每次 open/append/close。
3. **抽帧异步**:`comp.saveFrameToPng(t, file)` 只是投递;每帧后 `$.sleep(900)` + `exists` 自查,结尾再 `$.sleep(2500)`。
4. **退出**:`app.quit()` 是唯一"结束"信号;没有它,runner 只能超时杀进程(日志可能半截)。

## 实测

- 27 张抽帧 + 2 张滑块对照,加 `sleep` 后 **29/29 `exists=true`**;不加时 **0/27**。
- 冷启动轮询上限 90s;本机 AE 2026 冷启动约 8–15s。
- 单次跑 9 个合成 + 29 帧抽帧 + 存盘,整体在 `TimeoutSec=300` 内。
- 方案5 工程:3 合成 + 15 帧 + 存盘,`结束,耗时 20.0s`;`.aep` 708,865 字节;退出码 **0**(修好 `DONE$` 之后)。

## 坑

- **中文/空格文件名的抽帧会静默不落盘** → 前缀用 ASCII(`c1`),中文只进图层名与日志文本。
- **不要拼 AE 对象**:`L("ret=" + r)`(r 是 `saveFrameToPng` 返回值)会让进程消失。
- 已有 AfterFX 实例时 `-r` 会把脚本送进**那个**实例,时序不可控 ⇒ 先全部 `Stop-Process`。
- **`DONE` 判据必须匹配行尾**:日志每行以时间戳开头(`Thu Oct 29 … GMT+0800  DONE`),
  写 `^DONE` 永远匹配不到 —— 实测三次构建全部跑成功、却全被判成"中途崩",退出码 1。用 `DONE$`。
- **投递脚本用 `Start-Process`,不要 `& $AePath -r $Jsx`**:嵌套 PowerShell(`powershell -File`)里,
  `&` 会在 AE 退出后抛 `You cannot call a method on a null-valued expression`,而**脚本其实已经跑完**
  (日志有 `DONE`、`.aep` 已存)。`Start-Process` 不等,退出交给阶段 3 轮询。
- **`.ps1` 必须存成 UTF-8 带 BOM**:PS 5.1 按 ANSI 读无 BOM 文件,中文提示全变乱码(`[run_ae] 鍚姩 AE ...`)。
