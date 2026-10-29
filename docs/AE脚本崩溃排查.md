# AE 脚本崩溃排查

**场景**:`afterfx -r` 跑完没反应;日志为空;进程消失;工程存了但抽帧没了。
**结论**:AE 的失败模式**几乎都不抛异常**。按命中率查。

## 1 七条路径(按命中率排序)

| # | 现象 | 最可能的原因 | 判据 |
|---|---|---|---|
| 1 | 进程**直接消失**,日志停在某一行 | 把 **AE 对象**拼进了字符串 | 该行是否有 `+ 对象` |
| 2 | 进程活着、日志**0 字节** | 冷启动未就绪 / 日志没逐行落盘 | 日志文件大小 |
| 3 | 日志说成功、**文件不存在** | 抽帧异步 / 非 ASCII 文件名 | `exists=true` 出现几次 vs 磁盘几个文件 |
| 4 | `null is not an object` | 中文界面按**英文名**取默认属性 | 报错行取的是不是 `"Slider"`/`"Blurriness"` |
| 5 | 属性变红、画面没动画 | 表达式语法错 | 递归扫 `expressionError` |
| 6 | 图层整体偏 | 素材透明边距左右不等 | alpha bbox 是否对称 |
| 7 | 存盘成功但重开缺合成 | 存盘在抽帧前被 kill | `.aep` 字节数是否明显偏小 |

## 2 头号嫌疑:拼接 AE 对象

```javascript
// 两处都实测崩过 —— 不是抛异常,是进程消失,try/catch 接不住
L("openInViewer " + ok);        // ok 是 Viewer
L("ret=" + r);                  // r 是 saveFrameToPng 返回值
```

修法:**只拼标量**。

```javascript
L("openInViewer ok");           // 不拼对象
L("frame " + fn + " exists=" + (new File(fn)).exists);   // exists 是布尔
```

这就是为什么 `L()` 的签名不该是"万能日志":一旦允许传任意对象,总有一次会传进去。

## 3 日志:0 字节 = 不可诊断

ExtendScript 的 `File` 写入先进缓冲,`close()` 才提交。进程硬崩 ⇒ 缓冲全丢。

```javascript
function L(s) {
    var f = new File(LOG_PATH);
    f.open("a");
    f.write(s + "\n");
    f.close();
}
```

代价是 IO 慢,换来"崩溃点永远可见"。
实测:`dimensionsSeparated` 那次崩溃,日志最后一行正好停在被崩的语句。

## 4 冷启动:进程存在 ≠ 就绪

`Start-Process` 后立即 `-r`,AE 还在加载 ⇒ **脚本被丢弃**,日志为空。
必须先轮询 `MainWindowTitle -ne ""`,再 `sleep 1500ms`。

判据:日志文件**根本不存在** ⇒ 这条;日志有但空 ⇒ 日志落盘问题。

## 5 中文界面:名字 vs 索引

```javascript
fx.property("Blurriness")   // null(中文版叫"模糊度")
fx.property(1)              // 对
```

规律:

- **默认英文名**在中文界面**取不到**;
- **自己用脚本命名**的中文名(`fx.name = "图标时长"`)可以正常取。

⇒ 读别人的效果参数用索引,读自己命名的滑块用名字。

## 6 表达式体检

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

## 7 失败模式速查表

| 你看到的 | 真实原因 |
|---|---|
| "脚本没跑" | 冷启动未就绪 |
| "跑完了但没日志" | `L()` 没逐行落盘 |
| "日志全成功但没文件" | 异步写盘 + 立即 quit |
| "进程闪退" | 拼接 AE 对象 |
| "属性是红的" | 表达式语法/引用错 |
| "值不跟着滑块变" | 滑块名/索引错 |
| "位置差半个字" | 素材边距不对称 |

## 8 排查顺序(照做)

1. 日志存在吗?→ 不存在 = 冷启动;存在但空 = 落盘。
2. 日志最后一行是什么?→ 定位到语句。
3. 那行有 `+` 拼接对象吗?→ 有就删掉。
4. 有没有 `DONE`?→ 没有 = 中途崩。
5. `saved ... exists=true` 有吗?→ 没有 = 存盘失败。
6. `frame ... exists=false` 有几个?→ 有 = 异步/文件名。
7. 最后跑一次 `verify_frames.py` → `FAIL=0` 才算完。
