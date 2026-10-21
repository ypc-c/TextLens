# TextLens

一个常驻桌面的猫爪浮窗，**框一下屏幕，文字自动进剪贴板**。

基于 Windows 系统自带的 `Windows.Media.Ocr` 引擎，完全离线运行，不联网、不上传、不需要申请任何 Key。

---

## 功能

| 操作 | 效果 |
| --- | --- |
| **单击**猫爪 | 进入全屏选框模式，拖拽绘制矩形，松开即 OCR 并复制文字 |
| **长按**（约 0.35 秒）猫爪 | 进入拖动模式，把浮窗拖到屏幕任意位置 |
| **右键**猫爪 | 弹出菜单，退出程序 |
| 选框内 **右键 / ESC** | 取消本次取字 |

取字过程中浮窗会显示状态：`识别中…` → `已复制 N字` / `无文字` / `识别失败`，随后自动复原。每次操作猫爪都会有一个收缩—舒张的回弹动画。

识别语言自动跟随 Windows 用户配置语言（中文 / 英文），无需手动切换。

---

## 运行要求

- **Windows 10 / 11**（依赖 Windows Runtime OCR，不支持 macOS / Linux）
- 系统已安装中文或英文语言包（设置 → 时间和语言 → 语言）
- 源码运行需要 **Python 3.9+**（推荐 3.11 ~ 3.13）
- 打包后的 `dist/TextLens.exe` 自包含，**无需 Python 环境**

---

## 快速开始

### 方式一：直接用打包好的 exe（推荐）

双击 `dist/TextLens.exe` 即可。这是单文件绿色程序，可以单独拷贝到任何一台 Windows 电脑上。

### 方式二：从源码运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动
python main.py
```

> 如果不想看到控制台窗口，用 `pythonw main.py` 启动。

### 方式三：桌面快捷启动器

`launcher.py` 是一个可选的入口脚本，适合打包成独立启动器放在桌面。它会以无控制台方式拉起 `TextLens/main.py`。使用前需要把里面的 `PYTHONW` 路径改成你本机实际的 `pythonw.exe` 路径：

```python
PYTHONW = r"C:\你的路径\pythonw.exe"
```

---

## 打包

改动 `main.py` 后重新执行打包脚本：

```bash
python build_exe.py            # 增量打包，约 30~60 秒
python build_exe.py --clean    # 清空缓存从头打包（依赖变动时用）
```

产物为 `dist/TextLens.exe`（`--onefile` 单文件、`--windowed` 无控制台）。脚本会自动清理生成的 `.spec` 文件。

打包要点：winrt 是一组原生 `.pyd`，必须用 `--collect-all=winrt` 整体收集；同时剔除了 numpy / pandas / torch 等无关大库以压缩体积。

---

## 目录结构

```
TextLens/
├── main.py            # 主程序：浮窗 UI + 选框 + OCR 调度
├── launcher.py        # 可选启动器（无控制台拉起 main.py）
├── build_exe.py       # PyInstaller 打包脚本
├── test_ocr.py        # OCR 管线自检脚本
├── requirements.txt   # 依赖清单
├── assets/
│   ├── float.png      # 猫爪浮窗图标
│   └── app.ico        # 应用图标
└── dist/
    └── TextLens.exe   # 打包产物
```

---

## 实现要点

- **DPI 精确截图**：启动即调用 `SetProcessDpiAwareness(2)` 并关闭 Qt 自动缩放，让 Qt 逻辑坐标与物理像素 1:1 对齐。否则在高分屏 + 缩放（125%、150%）下选框位置会偏移。
- **截图**：`mss` 抓取物理像素区域，转 PIL Image。
- **OCR**：图片短边不足 1200px 时先 LANCZOS 放大（最多 3 倍）再送入 OCR，明显提升小字号识别率。
- **线程模型**：OCR 在子线程执行，完成后通过自定义 `QEvent` 投递回主线程更新 UI，避免阻塞界面。
- **资源路径**：兼容开发态与 PyInstaller 的 `sys._MEIPASS` 解压目录。
- **降级**：`assets/float.png` 缺失时自动回退为文字样式浮窗，不会崩。

---

## 常见问题

**Q：提示"未找到可用的 Windows OCR 引擎"？**
系统缺少 OCR 语言包。在「设置 → 时间和语言 → 语言」中添加中文（简体）或 English，安装"基本输入"和"手写/语音识别"后重启程序。

**Q：能验证 OCR 本身是否正常吗？**
```bash
python test_ocr.py
```
它会合成一张含中英文的图片走一遍 OCR 管线，正常会打印 `OCR result: 'Hello World 你好世界 2026'`。

**Q：选框位置和实际截到的内容对不上？**
通常是多屏 + 不同缩放率导致的。代码已做逐显示器 DPI 感知，若仍有问题请检查是否有显示器设置了非整数倍缩放。

**Q：识别结果去哪了？**
直接写进了系统剪贴板，在目标位置 `Ctrl + V` 粘贴即可。程序本身不保留任何历史记录。

**Q：会上传我的屏幕内容吗？**
不会。OCR 全程调用 Windows 本地 API，无任何网络请求。

---

## 依赖

```
PySide6            # 浮窗与选框 UI
mss                # 跨屏截图
pillow             # 图像处理
winrt-runtime      # Windows Runtime 绑定
winrt-Windows.Media.Ocr
winrt-Windows.Graphics.Imaging
winrt-Windows.Storage.Streams
winrt-Windows.Globalization
winrt-Windows.Foundation
```
