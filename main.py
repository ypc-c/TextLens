# -*- coding: utf-8 -*-
"""
TextLens - 桌面浮窗文字提取工具
- 屏幕常驻半透明浮窗
- 单击浮窗：进入全屏选框模式，拖拽绘制矩形，松开后 OCR 提取文字并复制到剪贴板
- 长按浮窗：拖动浮窗到屏幕任意位置
- 右键浮窗：退出
OCR 使用 Windows 内置 Windows.Media.Ocr 引擎，离线支持中英文。
"""
import os
import sys
import ctypes
import io
import re
import asyncio
import threading

# ---------- DPI 处理：让 Qt 逻辑坐标 == 物理像素，保证截图区域精确 ----------
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
os.environ["QT_SCALE_FACTOR"] = "1"
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_DPI_AWARE
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

from PySide6.QtCore import Qt, QTimer, QPoint, QRect, Signal, QObject, QVariantAnimation
from PySide6.QtGui import QPainter, QColor, QPen, QCursor, QGuiApplication, QFont, QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QWidget, QMenu

import mss
from PIL import Image

# 打包成 exe 后，资源会被解压到 sys._MEIPASS；开发态就用脚本所在目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, "frozen", False):
    BASE_DIR = getattr(sys, "_MEIPASS", BASE_DIR)  # 资源被加在 _MEIPASS/assets/ 下

# ---------- Windows OCR ----------
from winrt.windows.media.ocr import OcrEngine
from winrt.windows.globalization import Language
from winrt.windows.storage.streams import InMemoryRandomAccessStream, DataWriter
from winrt.windows.graphics.imaging import BitmapDecoder

_ocr_engine = OcrEngine.try_create_from_user_profile_languages()
if _ocr_engine is None:
    try:
        _ocr_engine = OcrEngine.try_create_from_language(Language("zh-Hans-CN"))
    except Exception:
        _ocr_engine = None


# CJK 字符范围（含扩展 A、兼容区、全角符号等）
_CJK_CLASS = r"[\u3000\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef]"
# 去掉与 CJK 相邻的空格（含全角空格/制表符），保留英文词间空格；不碰换行符
_CJK_SPACE_RE = re.compile(
    r"(?<=" + _CJK_CLASS + r")[ \t\u3000]+|[ \t\u3000]+(?=" + _CJK_CLASS + r")"
)


def _clean_ocr_spaces(text: str) -> str:
    """去除中文 OCR 常见的逐字/逐词空格：凡是挨着中文字符的空格都删掉，
    仅保留两个西文词之间的空格；换行符 \\n 不受影响。"""
    return _CJK_SPACE_RE.sub("", text)


async def _ocr_async(png_bytes: bytes) -> str:
    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream)
    writer.write_bytes(png_bytes)
    await writer.store_async()
    stream.seek(0)
    decoder = await BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()
    result = await _ocr_engine.recognize_async(bitmap)
    if result is None:
        return ""
    # 直接取 result.text（已含行内/行间结构），再清洗中文周围的多余空格
    return _clean_ocr_spaces(result.text or "")


def ocr_pil_image(img: Image.Image) -> str:
    """对 PIL 图片做 OCR，返回识别文本。"""
    if _ocr_engine is None:
        return ""
    # 小图放大，提升识别率
    w, h = img.size
    if max(w, h) < 1200:
        scale = min(3.0, 1200 / max(w, h))
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return asyncio.run(_ocr_async(buf.getvalue()))


def capture_region(rect: QRect) -> Image.Image:
    """按物理像素截图指定区域。"""
    with mss.mss() as sct:
        shot = sct.grab({
            "left": rect.x(),
            "top": rect.y(),
            "width": rect.width(),
            "height": rect.height(),
        })
        return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")


# ---------- 选框层 ----------
class RegionSelector(QWidget):
    """全屏半透明遮罩，拖拽绘制矩形选框。"""
    region_selected = Signal(QRect)
    cancelled = Signal()

    def __init__(self):
        super().__init__()
        geo = QRect()
        for s in QGuiApplication.screens():
            geo = geo.united(s.geometry())
        self._origin = geo.topLeft()
        self.setGeometry(geo)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setCursor(Qt.CrossCursor)
        self._start = QPoint()
        self._current = QRect()
        self._dragging = False

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._start = e.position().toPoint()
            self._current = QRect(self._start, self._start)
            self._dragging = True
            self.update()
        elif e.button() == Qt.RightButton:
            self._cancel()

    def mouseMoveEvent(self, e):
        if self._dragging:
            self._current = QRect(self._start, e.position().toPoint()).normalized()
            self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self._dragging:
            self._dragging = False
            local = QRect(self._start, e.position().toPoint()).normalized()
            if local.width() >= 8 and local.height() >= 8:
                global_rect = QRect(local.translated(self._origin))
                self.region_selected.emit(global_rect)
            else:
                self._cancel()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self._cancel()

    def _cancel(self):
        self.cancelled.emit()

    def paintEvent(self, _):
        p = QPainter(self)
        # 全屏半透明遮罩
        p.fillRect(self.rect(), QColor(0, 0, 0, 70))
        if not self._current.isNull():
            r = self._current.normalized()
            # 选区内提亮（擦除遮罩）
            p.setCompositionMode(QPainter.CompositionMode_Clear)
            p.fillRect(r, Qt.transparent)
            p.setCompositionMode(QPainter.CompositionMode_SourceOver)
            # 选框描边
            p.setPen(QPen(QColor(0, 150, 255), 2))
            p.drawRect(r.adjusted(1, 1, -1, -1))
            # 尺寸提示
            label = f"{r.width()} x {r.height()}"
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 120, 215, 220))
            lx, ly = r.left(), r.top() - 26 if r.top() - 26 >= 0 else r.bottom() + 6
            p.drawRoundedRect(lx, ly, max(110, len(label) * 9), 22, 4, 4)
            p.setPen(QColor(255, 255, 255))
            p.drawText(lx + 8, ly + 16, label)
        # 顶部提示
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 120))
        tip = "拖拽绘制选框，松开提取文字  |  ESC 取消"
        p.drawRoundedRect(self.width() // 2 - 180, 20, 360, 30, 6, 6)
        p.setPen(QColor(255, 255, 255))
        f = p.font()
        f.setPointSize(10)
        p.setFont(f)
        p.drawText(self.width() // 2 - 180, 40, tip)
        p.end()


# ---------- 浮窗 ----------
class FloatWindow(QWidget):
    LONG_PRESS_MS = 350

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(80, 80)
        self._press_pos = None
        self._drag_offset = None
        self._moving = False
        self._busy = False
        self._msg = "取字"
        self._msg_color = QColor(255, 255, 255)
        # 猫爪图标（assets/float.png），缺失时回退为文字样式
        self._paw = None
        paw_path = os.path.join(BASE_DIR, "assets", "float.png")
        if os.path.exists(paw_path):
            self._paw = QPixmap(paw_path)
        self._paw_scale = 1.0
        self._long_press_timer = QTimer(self)
        self._long_press_timer.setSingleShot(True)
        self._long_press_timer.timeout.connect(self._enter_move_mode)
        # 初始位置：屏幕右上角附近
        geo = QGuiApplication.primaryScreen().geometry()
        self.move(geo.right() - 120, geo.top() + 120)

    # --- 绘制 ---
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        if self._paw is not None:
            # 猫爪铺满浮窗（无底色，带回弹缩放动画）
            s = self._paw_scale
            pw = 78 * s
            c = 40
            p.drawPixmap(QRect(int(c - pw / 2), int(c - pw / 2), int(pw), int(pw)),
                         self._paw)
        if self._msg != "取字":
            # 状态文字叠在肉垫上（白字黑描边，浅色背景也可读）
            f = QFont("Microsoft YaHei", 8)
            f.setBold(True)
            p.setFont(f)
            rect = QRect(4, 36, 72, 30)
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                p.setPen(QColor(0, 0, 0, 170))
                p.drawText(rect.translated(dx, dy), Qt.AlignCenter, self._msg)
            p.setPen(QColor(255, 255, 255))
            p.drawText(rect, Qt.AlignCenter, self._msg)
        elif self._paw is None:
            # 无图标资源时的回退：居中显示文字
            p.setPen(self._msg_color)
            f = QFont("Microsoft YaHei", 11 if len(self._msg) <= 2 else 8)
            f.setBold(True)
            p.setFont(f)
            p.drawText(self.rect(), Qt.AlignCenter, self._msg)
        p.end()

    # --- 交互 ---
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._press_pos = e.globalPosition().toPoint()
            self._moving = False
            self._long_press_timer.start(self.LONG_PRESS_MS)
        elif e.button() == Qt.RightButton:
            menu = QMenu(self)
            act = menu.addAction("退出")
            if menu.exec(QCursor.pos()) == act:
                QApplication.quit()

    def mouseMoveEvent(self, e):
        if self._press_pos is None:
            return
        delta = e.globalPosition().toPoint() - self._press_pos
        if self._moving:
            self.move(self.pos() + delta)
            self._press_pos = e.globalPosition().toPoint()
        elif delta.manhattanLength() > 10 and self._long_press_timer.isActive():
            # 按下后快速大幅移动，也视为拖动
            self._long_press_timer.stop()
            self._moving = True

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or self._press_pos is None:
            return
        was_moving = self._moving
        self._long_press_timer.stop()
        self._press_pos = None
        self._moving = False
        if was_moving:
            self._play_squish()  # 松手的瞬间再收缩舒张一下
        elif not self._busy:
            self.start_capture()

    def _enter_move_mode(self):
        self._moving = True
        self._play_squish()  # 抓起的瞬间收缩舒张一下

    # --- 取字流程 ---
    def start_capture(self):
        self._busy = True
        self.hide()
        self._selector = RegionSelector()
        self._selector.region_selected.connect(self._on_region)
        self._selector.cancelled.connect(self._on_cancel)
        self._selector.show()

    def _on_cancel(self):
        self._selector.close()
        self._busy = False
        self.show()
        self.activateWindow()

    def _on_region(self, rect: QRect):
        self._selector.close()
        self._set_status("识别中…", QColor(255, 210, 90))
        self.show()
        threading.Thread(target=self._ocr_worker, args=(rect,), daemon=True).start()

    def _ocr_worker(self, rect: QRect):
        try:
            img = capture_region(rect)
            text = ocr_pil_image(img).strip()
        except Exception as exc:
            text = ""
            err = str(exc)
        else:
            err = ""
        # 回到主线程更新 UI
        QApplication.instance().postEvent(
            self, _OcrDoneEvent(text, err)
        )

    def customEvent(self, e):
        if isinstance(e, _OcrDoneEvent):
            self._on_ocr_done(e.text, e.err)

    def _on_ocr_done(self, text: str, err: str):
        self._busy = False
        if text:
            QApplication.clipboard().setText(text)
            n = len(text.replace("\n", ""))
            self._set_status(f"已复制\n{n}字", QColor(120, 255, 160))
        elif err:
            self._set_status("识别失败", QColor(255, 120, 120))
        else:
            self._set_status("无文字", QColor(255, 180, 120))
        self._play_squish()
        QTimer.singleShot(1600, self._reset_status)

    def _set_status(self, msg, color):
        self._msg = msg
        self._msg_color = color
        self.update()

    def _reset_status(self):
        self._set_status("取字", QColor(255, 255, 255))

    # --- 猫爪回弹动画：使用功能后收缩再舒张 ---
    def _play_squish(self):
        if getattr(self, "_squish_anim", None) is not None:
            self._squish_anim.stop()
        anim = QVariantAnimation(self)
        anim.setDuration(520)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.valueChanged.connect(self._on_squish_frame)
        anim.finished.connect(lambda: setattr(self, "_squish_anim", None))
        self._squish_anim = anim
        anim.start()

    def _on_squish_frame(self, v):
        t = float(v)
        if t < 0.35:
            s = 1.0 - (t / 0.35) * 0.22            # 收缩到 0.78
        elif t < 0.75:
            s = 0.78 + ((t - 0.35) / 0.40) * 0.30  # 舒张回弹到 1.08
        else:
            s = 1.08 - ((t - 0.75) / 0.25) * 0.08  # 落回 1.0
        self._paw_scale = s
        self.update()


from PySide6.QtCore import QEvent


class _OcrDoneEvent(QEvent):
    TYPE = QEvent.Type(QEvent.registerEventType())

    def __init__(self, text, err):
        super().__init__(self.TYPE)
        self.text = text
        self.err = err


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    icon_path = os.path.join(BASE_DIR, "assets", "app.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    if _ocr_engine is None:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(None, "TextLens", "未找到可用的 Windows OCR 引擎，请确认系统语言包包含中文/英文。")
        sys.exit(1)
    w = FloatWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
