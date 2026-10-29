# 无头运行 AE 脚本

**场景**:批量生成 `.aep`、批量抽帧、无人值守跑一整夜;不开界面、不点菜单。
**结论**:`afterfx -r <jsx>` + 严格的进程时序 + 逐行落盘日志。

## 1 为什么只能一条命令串完

AE 不像 Blender 有常驻脚本通道(9877 桥)。`-r` 起的是**一次性进程**:

```
Start-Process AfterFX.exe
  → 等主窗口就绪
  → afterfx -r script.jsx        (脚本在主线程跑)
  → 脚本末尾 app.quit()
  → 进程退出 ⇒ 才是"跑完了"
```

⇒ **建工程、挂表达式、抽帧、存盘必须写在同一份 `.jsx` 里**;中途状态只能靠日志文件。

## 2 时序四步

### 2.1 冷启动必须等窗口

```powershell
Start-Process -FilePath $AePath
while (...) {
  $p = Get-Process AfterFX | Where-Object { $_.MainWindowTitle -ne "" } | Select-Object -First 1
  if ($p) { break }
  Start-Sleep -Milliseconds 500
}
Start-Sleep -Milliseconds 1500
& $AePath -r $Jsx
```

- 实测:窗口没出来就 `-r` ⇒ **脚本静默不执行、日志为空**,最像"环境坏了"。
- 本机 AE 2026 冷启动约 **8–15s**;轮询上限给 90s。

### 2.2 已有实例要先清掉

`-r` 会把脚本投给**已经在跑的实例**,那个实例里可能有别人的工程 ⇒ 时序与结果都不可控。
`run_ae.ps1` 开头 `Stop-Process -Force` 清干净。

### 2.3 退出判据

脚本末尾:

```javascript
L("DONE");
$.sleep(2500);
app.quit();
```

runner 里等进程消失:

```powershell
while ($sw.Elapsed.TotalSeconds -lt $TimeoutSec) {
  if (-not (Get-Process AfterFX -ErrorAction SilentlyContinue)) { break }
  Start-Sleep -Milliseconds 500
}
```

没有 `app.quit()` 只能靠超时杀进程,日志可能是半截。

### 2.4 回读日志 + 判据

| 现象 | 结论 | 下一步 |
|---|---|---|
| 日志不存在 | 脚本没执行 | 查冷启动时序 |
| 日志有内容、无 `DONE` | 中途硬崩 | 最后一行就是崩溃点 |
| 有 `DONE`、没有 `saved ... exists=true` | 存盘失败 | 查路径/权限 |
| 有 `frame ... exists=false` | 抽帧被吞 | 加 `$.sleep` |

## 3 日志:必须逐行 open/append/close

```javascript
function L(s) {
    var f = new File(LOG_PATH);
    f.open("a");
    f.write(new Date().toString() + "  " + s + "\n");
    f.close();
}
```

- ExtendScript 的 `File` 写入先进缓冲,`close()` 才提交;
- 进程硬崩 ⇒ 缓冲全丢 ⇒ **日志 0 字节**,让人误判"脚本没跑";
- 逐行落盘后,崩溃点永远可见(实测:崩在 `dimensionsSeparated` 那行,日志正好停在它)。

代价是 IO 慢一点。29 帧的日志量完全无所谓。

## 4 抽帧是异步写盘

```javascript
comp.openInViewer();
comp.saveFrameToPng(t, f);     // 只是"投递"
$.sleep(900);
L("frame " + fn + " exists=" + (new File(fn)).exists);
```

- 首轮 27 帧:**日志全说成功,磁盘 0 个文件**。根因 = 连续投递 27 个后 `app.quit()`,
  进程退出时队列未完成的写入全丢。
- 加 `sleep 900ms` 后 **27/27 exists=true**;结尾再 `sleep 2500` 兜底。
- 文件名必须是 **ASCII**:中文/空格名会静默不落盘。

## 5 路径与命名

- 日志与抽帧目录用**绝对路径**,正斜杠 `C:/temp/...`(ExtendScript 对反斜杠转义敏感)。
- 抽帧命名 `c<N>_t<T>.png`,`T` = **毫秒**(`t=0.12s` ⇒ `_t120.png`)。
  早期用抽帧下标(0/1/2)会让人读成"0.00 / 0.01 秒",**歧义很坑**。

## 6 完整最小脚本

```javascript
#target aftereffects
var LOG_PATH = "C:/temp/ae_build.log";

function L(s) {
    var f = new File(LOG_PATH);
    f.open("a");
    f.write(s + "\n");
    f.close();
}

app.newProject();
var c = app.project.items.addComp("测试", 2048, 1152, 1, 3, 30);
L("comp ok layers=" + c.numLayers);

app.project.save(new File("C:/temp/test.aep"));
$.sleep(1500);
L("saved exists=" + (new File("C:/temp/test.aep")).exists);
L("DONE");
$.sleep(2500);
app.quit();
```

```powershell
.\run_ae.ps1 -Jsx C:\temp\test.jsx
```

## 7 坑

| 坑 | 表现 | 修法 |
|---|---|---|
| 冷启动未就绪 | 日志空 | 等 `MainWindowTitle` |
| 已存在实例 | 脚本跑进别人的会话 | 先 `Stop-Process` |
| 无 `app.quit()` | runner 超时 | 末尾必须 quit |
| 日志缓冲 | 崩溃后 0 字节 | 逐行 open/close |
| 抽帧异步 | 日志成功、文件不在 | `sleep` + `exists` |
| 非 ASCII 文件名 | 文件不落盘 | ASCII |
| 拼接 AE 对象 | 进程消失 | 只拼标量 |
