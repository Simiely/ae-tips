---
name: ae-crash-diagnose
description: AE 脚本侧失败定位——`afterfx -r` 跑完没反应、进程闪退、日志 0 字节、日志全成功但没文件、属性变红、存盘缺合成。当用户说「AE 没反应」「脚本像没跑」「跑完了没产物」「AE 崩了」「日志是空的」「表达式报错但没弹窗」时使用。按命中率排序的七条路径 + 日志纪律 + 失败模式速查表 + 七步排查顺序。
agent_created: true
---

# 脚本崩溃与静默失败排查

上游:`ae-script-runner`(通道本身)。
本 skill 只管**已经失败了,怎么三分钟内定位到那一行**。

**核心结论先行**:AE 的失败**几乎都不抛异常**。
能接住的是语法错,接不住的是"进程消失";能看见的是红框,看不见的是"日志说有、磁盘没有"。

## 铁律

1. **先看日志文件存不存在**,再看内容 —— 这两个答案指向完全不同的原因
2. **不信"成功"读数**:`saveFrameToPng` 返回值 / `openInViewer` 返回值都不代表落盘
3. **日志必须逐行 open/append/close**,否则崩一次日志就是空的
4. **只拼标量**,任何 AE 对象进字符串都视为"这一行会崩"
5. **中文界面按索引取默认属性**,自己命名的中文名才可以按名字取
6. **表达式错不弹窗**,必须自己递归扫 `expressionError`,判据 0 条
7. **改一处只改一处**,再跑一次;不要一次改三处让归因失效

---

## §1 七条路径(按命中率)

| # | 现象 | 最可能的原因 | 一眼判据 |
|---|---|---|---|
| 1 | 进程**直接消失**,日志停在某一行 | 把 **AE 对象**拼进了字符串 | 最后一行有没有 `+ 对象` |
| 2 | 进程活着、日志**0 字节** | 冷启动未就绪 / 日志没逐行落盘 | 日志文件大小 |
| 3 | 日志说成功、**文件不存在** | 抽帧异步 / 非 ASCII 文件名 | `exists=true` 行数 vs 磁盘文件数 |
| 4 | `null is not an object` | 中文界面按**英文名**取默认属性 | 报错行取的是不是 `"Slider"` / `"Blurriness"` |
| 5 | 属性变红、画面没动画 | 表达式语法错 | 递归扫 `expressionError` |
| 6 | 图层整体偏 | 素材透明边距左右不等 | 文件 alpha bbox 是否对称 |
| 7 | 存盘成功但重开缺合成 | 存盘/抽帧顺序错、或被 kill | `.aep` 字节数是否明显偏小 |

## §2 头号嫌疑:拼接 AE 对象

```javascript
// 两处都实测崩过 —— 不是抛异常,是进程消失, try/catch 接不住
L("openInViewer " + ok);        // ok 是 Viewer
L("ret=" + r);                  // r 是 saveFrameToPng 返回值
```

修法:**只拼标量**。

```javascript
L("openInViewer ok");                                   // 不拼对象
L("frame " + fn + " exists=" + (new File(fn)).exists);  // exists 是布尔
```

这就是 `L()` 不该做成"万能日志"的原因:一旦允许传任意对象,总有一次会传进去。

## §3 日志:0 字节 = 不可诊断

ExtendScript 的 `File` 写入先进缓冲,`close()` 才提交。进程硬崩 ⇒ 缓冲全丢。

```javascript
function L(s) {
    var f = new File(LOG_PATH);
    f.open("a");
    f.write(new Date().toString() + "  " + s + "\n");
    f.close();
}
```

代价是 IO 慢,换来"崩溃点永远可见"。实测:`dimensionsSeparated` 那次崩溃,日志最后一行正好停在被崩的语句。

## §4 冷启动:进程存在 ≠ 就绪

`Start-Process` 后立即 `-r`,AE 还在加载 ⇒ **脚本被丢弃**、日志为空。
必须先轮询 `MainWindowTitle -ne ""`,再 `sleep 1500ms`。

- 日志**根本不存在** ⇒ 这条(或路径写错)
- 日志存在但空 ⇒ 日志落盘问题(§3)

## §5 中文界面:名字 vs 索引

```javascript
fx.property("Blurriness")   // null(中文版叫"模糊度")
fx.property(1)              // 对
```

规律:

- **默认英文名**在中文界面**取不到**;
- **自己用脚本命名**的中文名(`fx.name = "图标时长"`)可以正常取。

⇒ 读别人的效果参数用**索引**;读自己命名的滑块用**名字**。

## §6 表达式体检

```javascript
function scanExpr(prop, path) {
    if (prop.numProperties > 0) {
        for (var i = 1; i <= prop.numProperties; i++) {
            scanExpr(prop.property(i), path + "/" + prop.property(i).name);
        }
    } else if (prop.expressionError !== "") {
        L("EXPR_ERR " + path + " :: " + prop.expressionError);
    }
}
```

- 表达式写错时 AE **不弹窗**,属性只是变红;
- 无人值守时没人看红框 ⇒ 必须自己扫,判据 **0 条**;
- 遍历时对 `numProperties` / `expressionError` 都套 `try`,不同属性类型支持度不同。

## §7 排查顺序(照做)

1. 日志**存在吗**?→ 不存在 = 冷启动;存在但空 = 落盘。
2. 日志**最后一行**是什么?→ 定位到语句。
3. 那行有 `+` 拼接对象吗?→ 有就删掉。
4. 有 `DONE` 吗?→ 没有 = 中途崩在它之前。
5. 有 `saved ... exists=true` 吗?→ 没有 = 存盘失败。
6. `frame ... exists=false` 有几个?→ 有 = 异步/文件名。
7. 跑一次 `ae-frame-verify` → `FAIL=0` 才算完。

## §8 失败模式速查

| 你看到的 | 真实原因 |
|---|---|
| "脚本没跑" | 冷启动未就绪 |
| "跑完了但没日志" | `L()` 没逐行落盘 |
| "日志全成功但没文件" | 异步写盘 + 立即 quit |
| "进程闪退" | 拼接 AE 对象 / `setTemporalEaseAtKey` 多维亚参数 |
| "属性是红的" | 表达式语法/引用错 |
| "值不跟着滑块变" | 滑块名/索引错 |
| "位置差半个字" | 素材边距不对称 |

## §9 脚本与文档

- [`../scripts/ae-headless-run/run_ae.ps1`](../scripts/ae-headless-run/run_ae.ps1) —— 退出码 `0/1/2` 就是第一层分诊
- [`../scripts/ae-headless-run/jsxlib.jsx`](../scripts/ae-headless-run/jsxlib.jsx) —— `L()` / `shoot()` / `reportExprErrors()` 的正确写法
- 文档:[`../docs/AE脚本崩溃排查.md`](../docs/AE脚本崩溃排查.md)

## 与相邻 skill 的边界

| Skill | 分工 |
|---|---|
| `ae-crash-diagnose`(本) | 脚本**为什么没产出** |
| `ae-script-runner` | 正常通道怎么搭(本 skill 是它的失败分支) |
| `ae-frame-verify` | 产物有了,**对不对** |
| `ae-expression-tween` | 缓动方案本身(不含它的崩溃) |
