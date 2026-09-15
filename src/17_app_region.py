# ============================================
# 17_app_region.py
# 双模式 + 设置窗口整合版
#   Shift+T  全屏持续翻译（开关）
#   Shift+R  一次性框选翻译
#   Alt+R    清除框选译文
#   托盘右键 → 设置
# ============================================

import sys
import os
import time
import ctypes
import mss
import numpy as np
import cv2

# ★ 打包后运行时：config.py 在 exe 同级目录
#   开发环境下：从源文件往上找 config.py
if getattr(sys, "frozen", False):
    _root = os.path.dirname(sys.executable)
else:
    _here = os.path.dirname(os.path.abspath(__file__))
    _root = _here
    while not os.path.exists(os.path.join(_root, "config.py")):
        _parent = os.path.dirname(_root)
        if _parent == _root:
            raise RuntimeError("找不到 config.py")
        _root = _parent

sys.path.append(_root)

from config import DEEPSEEK_API_KEY
from settings import Settings
from settings import Settings

from paddleocr import PaddleOCR
from openai import OpenAI

from PyQt5.QtWidgets import (QApplication, QWidget, QSystemTrayIcon,
                              QMenu, QAction)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject, QRect
from PyQt5.QtGui import (QPainter, QColor, QFont, QFontMetrics,
                          QPixmap, QIcon, QPen, QRegion)

from pynput import keyboard


# ================== 全局 settings 单例 ==================
_settings = Settings.load()

def S():
    """快捷访问全局 settings"""
    return _settings


# 图像差异检测用的固定比例（与外观无关，不暴露给用户）
DIFF_SCALE = 0.125


# ================== 翻译缓存 ==================
class TranslationCache:
    def __init__(self):
        self._data = {}
    def get(self, text):
        return self._data.get(text)
    def put(self, src, dst):
        self._data[src] = dst
    def size(self):
        return len(self._data)


# ================== 翻译引擎 ==================
class Translator:
    def __init__(self):
        self.client = OpenAI(api_key=DEEPSEEK_API_KEY,
                             base_url="https://api.deepseek.com")
        self.cache = TranslationCache()
        self.hit = 0
        self.total = 0

    def translate_batch(self, texts):
        if not texts:
            return []
        results = [None] * len(texts)
        to_translate, to_translate_idx = [], []

        for i, t in enumerate(texts):
            self.total += 1
            cached = self.cache.get(t)
            if cached is not None:
                results[i] = cached
                self.hit += 1
            else:
                to_translate.append(t)
                to_translate_idx.append(i)

        if not to_translate:
            return results

        system_prompt = (
            "你是专业屏幕翻译引擎。用户会给你一组从屏幕 OCR 识别出的文本"
            "（可能来自网页、软件界面、游戏）。请结合上下文翻译成自然流畅的简体中文。\n"
            "重要：输入是 OCR 结果，可能存在识别错误（l/1、rn/m、0/O 混淆，"
            "字符被截断，或粘连错字）。请根据上下文推断正确的原文再翻译；"
            "若某行完全无法理解，就原样输出，不要硬翻。\n"
            "要求：\n"
            "1. 每行一个译文，与输入行数严格一一对应\n"
            "2. 不要添加编号、解释或空行，只输出译文\n"
            "3. 专有名词（品牌名、角色名、地名、代码变量名）保留原文\n"
            "4. 代码片段、URL、单个数字/符号原样返回\n"
            "5. 译文要简洁，尽量避免比原文长太多"
        )
        user_prompt = "请翻译以下文本：\n" + "\n".join(to_translate)

        resp = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )
        lines = resp.choices[0].message.content.strip().split("\n")
        if len(lines) < len(to_translate):
            lines += to_translate[len(lines):]
        elif len(lines) > len(to_translate):
            lines = lines[:len(to_translate)]

        for idx, src, dst in zip(to_translate_idx, to_translate, lines):
            self.cache.put(src, dst)
            results[idx] = dst
        return results


# ================== 帧差异检测 ==================
class FrameWatcher:
    def __init__(self):
        self.prev = None
    def has_changed(self, gray_small):
        if self.prev is None:
            self.prev = gray_small
            return True
        diff = cv2.absdiff(self.prev, gray_small)
        mean_diff = float(diff.mean())
        self.prev = gray_small
        # 阈值从 settings 实时读取
        return mean_diff > S()["diff_threshold"]


# ================== 布局 ==================
def layout_item(x, y, w, h, text):
    s = S()
    min_font   = s["min_font"]
    max_font   = s["max_font"]
    font_fam   = s["font_family"]
    pad_x      = s["pad_x"]
    pad_y      = s["pad_y"]

    bx, by = x - pad_x, y - pad_y
    bw, bh = w + pad_x * 2, h + pad_y * 2

    for size in range(max_font, min_font - 1, -1):
        font = QFont(font_fam, size)
        fm = QFontMetrics(font)
        if fm.horizontalAdvance(text) <= bw - 6 and fm.height() <= bh + 4:
            return bx, by, bw, bh, size

    font = QFont(font_fam, min_font)
    fm = QFontMetrics(font)
    need_w = fm.horizontalAdvance(text) + 10
    return bx, by, max(bw, need_w), bh, min_font


# ================== 覆盖层 ==================
class Overlay(QWidget):
    def __init__(self):
        super().__init__()
        self.items = []
        self._capture_excluded = False
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._capture_excluded:
            try:
                hwnd = int(self.winId())
                WDA_EXCLUDEFROMCAPTURE = 0x00000011
                if ctypes.windll.user32.SetWindowDisplayAffinity(
                        hwnd, WDA_EXCLUDEFROMCAPTURE):
                    self._capture_excluded = True
            except Exception:
                pass

    def update_items(self, items):
        self.items = items
        self.update()

    def clear(self):
        self.items = []
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        s = S()
        bg_rgb   = s["bg_color"]
        bg_alpha = s["bg_alpha"]
        text_rgb = s["text_color"]
        font_fam = s["font_family"]
        min_font = s["min_font"]

        layouts = []
        for x, y, w, h, text in self.items:
            bx, by, bw, bh, size = layout_item(x, y, w, h, text)
            layouts.append([bx, by, bw, bh, size, text])

        layouts.sort(key=lambda it: it[1])
        for i in range(len(layouts)):
            a = layouts[i]
            a_bottom = a[1] + a[3]
            a_right = a[0] + a[2]
            for j in range(i + 1, len(layouts)):
                b = layouts[j]
                b_right = b[0] + b[2]
                if a[0] < b_right and a_right > b[0]:
                    if a_bottom > b[1]:
                        new_h = b[1] - a[1] - 1
                        a[3] = max(8, new_h)
                        break

        r, g, b = bg_rgb
        tr, tg, tb = text_rgb
        for bx, by, bw, bh, size, text in layouts:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(r, g, b, bg_alpha))
            painter.drawRect(bx, by, bw, bh)
            real_size = min(size, max(min_font, int(bh * 0.85)))
            painter.setFont(QFont(font_fam, real_size))
            painter.setPen(QColor(tr, tg, tb))
            painter.drawText(QRect(bx, by, bw, bh), Qt.AlignCenter, text)


# ================== 提示浮窗 ==================
class Toast(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.text = ""
        self.visible = False
        screen = QApplication.primaryScreen().geometry()
        w, h = 320, 60
        self.setGeometry(screen.width() // 2 - w // 2,
                         screen.height() - 200, w, h)
        self.hide()

    def show_toast(self, text):
        self.text = text
        self.visible = True
        self.show()
        self.update()

    def hide_toast(self):
        self.visible = False
        self.hide()

    def paintEvent(self, event):
        if not self.visible:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 220))
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 8, 8)
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont(S()["font_family"], 12))
        painter.drawText(self.rect(), Qt.AlignCenter, self.text)


# ================== 区域选择器 ==================
class RegionSelector(QWidget):
    region_selected = pyqtSignal(int, int, int, int)
    cancelled = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)

        self.start_pos = None
        self.current_pos = None
        self.dragging = False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self.dragging and self.start_pos and self.current_pos:
            sel_rect = QRect(self.start_pos, self.current_pos).normalized()
            full_region = QRegion(self.rect())
            hole = QRegion(sel_rect)
            painter.setClipRegion(full_region.subtracted(hole))

        painter.fillRect(self.rect(), QColor(0, 0, 0, 130))
        painter.setClipping(False)

        if self.dragging and self.start_pos and self.current_pos:
            sel_rect = QRect(self.start_pos, self.current_pos).normalized()
            pen = QPen(QColor(0, 180, 255), 2)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(sel_rect)

            size_text = f"{sel_rect.width()} × {sel_rect.height()}"
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont(S()["font_family"], 11))
            text_y = sel_rect.top() - 8
            if text_y < 20:
                text_y = sel_rect.top() + 20
            painter.drawText(sel_rect.left(), text_y, size_text)

        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont(S()["font_family"], 14))
        hint = "拖拽鼠标选择翻译区域    |    Esc 取消"
        painter.drawText(self.rect(),
                         Qt.AlignTop | Qt.AlignHCenter,
                         "\n" + hint)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_pos = event.pos()
            self.current_pos = event.pos()
            self.dragging = True
            self.update()

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.current_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.dragging:
            self.dragging = False
            sel_rect = QRect(self.start_pos, self.current_pos).normalized()

            if sel_rect.width() < 20 or sel_rect.height() < 20:
                self.cancelled.emit()
                self.close()
                return

            self.region_selected.emit(
                sel_rect.left(), sel_rect.top(),
                sel_rect.width(), sel_rect.height()
            )
            self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.cancelled.emit()
            self.close()


# ================== 全屏模式工作线程 ==================
class FullWorker(QThread):
    result_ready = pyqtSignal(list)
    clear_signal = pyqtSignal()
    toast_signal = pyqtSignal(str, bool)
    status_update = pyqtSignal(str)

    def __init__(self, ocr, translator):
        super().__init__()
        self.ocr = ocr
        self.translator = translator
        self.running = False
        self.watcher = FrameWatcher()
        self.stable_frames = 0
        self.is_showing = False

    def _grab_gray_small(self):
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            shot = sct.grab(monitor)
            img = np.array(shot)[:, :, :3]
            small = cv2.resize(img, None, fx=DIFF_SCALE, fy=DIFF_SCALE,
                               interpolation=cv2.INTER_AREA)
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        return gray

    def run(self):
        while self.running:
            try:
                t0 = time.time()
                gray = self._grab_gray_small()
                changed = self.watcher.has_changed(gray)

                if changed:
                    if self.is_showing:
                        self.clear_signal.emit()
                        self.is_showing = False
                    self.stable_frames = 0
                else:
                    self.stable_frames += 1
                    stable_need = S()["stable_frames"]
                    if self.stable_frames == stable_need and not self.is_showing:
                        self.toast_signal.emit("正在识别...", True)
                        t_ocr = time.time()
                        texts, boxes = self._do_ocr()
                        t_ocr_done = time.time()
                        if not self.running:
                            break
                        translations = self.translator.translate_batch(texts)
                        t_trans_done = time.time()
                        items = [(b[0], b[1], b[2], b[3], tr)
                                 for b, tr in zip(boxes, translations)]
                        if self.running:
                            self.result_ready.emit(items)
                            self.is_showing = True
                            self.toast_signal.emit("", False)
                        self.status_update.emit(
                            f"[全屏] 识别 {len(texts):>3} 条 | "
                            f"OCR {t_ocr_done-t_ocr:>4.2f}s | "
                            f"翻译 {t_trans_done-t_ocr_done:>4.2f}s | "
                            f"总计 {t_trans_done-t0:>4.2f}s"
                        )
            except Exception as e:
                if self.running:
                    self.status_update.emit(f"错误：{type(e).__name__} - {e}")
            # 间隔从 settings 实时读取
            time.sleep(S()["check_interval"])

    def _do_ocr(self):
        s = S()
        scale = s["scale"]
        min_conf = s["min_confidence"]

        with mss.mss() as sct:
            monitor = sct.monitors[1]
            shot = sct.grab(monitor)
            img = np.array(shot)[:, :, :3]
            img_small = cv2.resize(img, None, fx=scale, fy=scale,
                                   interpolation=cv2.INTER_AREA)

        result = self.ocr.ocr(img_small, cls=False)
        texts, boxes = [], []
        if result and result[0]:
            for line in result[0]:
                box = line[0]
                text = line[1][0].strip()
                conf = line[1][1]
                if not text or conf < min_conf:
                    continue
                only_symbol = all(
                    not c.isalnum() and not ('\u4e00' <= c <= '\u9fff')
                    for c in text
                )
                if only_symbol or text.isdigit():
                    continue
                xs = [p[0] / scale for p in box]
                ys = [p[1] / scale for p in box]
                x, y = int(min(xs)), int(min(ys))
                w, h = int(max(xs) - min(xs)), int(max(ys) - min(ys))
                boxes.append((x, y, w, h))
                texts.append(text)
        return texts, boxes

    def stop(self):
        self.running = False


# ================== 框选模式工作线程 ==================
class RegionWorker(QThread):
    result_ready = pyqtSignal(list)
    status_update = pyqtSignal(str)

    def __init__(self, ocr, translator, region):
        super().__init__()
        self.ocr = ocr
        self.translator = translator
        self.region = region

    def run(self):
        try:
            t0 = time.time()
            x, y, w, h = self.region
            s = S()
            upscale = s["region_upscale"]
            min_conf = s["min_confidence"]

            with mss.mss() as sct:
                shot = sct.grab({"left": x, "top": y,
                                 "width": w, "height": h})
                img = np.array(shot)[:, :, :3]

            if upscale != 1.0:
                img = cv2.resize(img, None,
                                 fx=upscale, fy=upscale,
                                 interpolation=cv2.INTER_CUBIC)

            t_ocr = time.time()
            result = self.ocr.ocr(img, cls=False)
            t_ocr_done = time.time()

            texts, boxes = [], []
            if result and result[0]:
                for line in result[0]:
                    box = line[0]
                    text = line[1][0].strip()
                    conf = line[1][1]
                    if not text or conf < min_conf - 0.1:
                        continue
                    only_symbol = all(
                        not c.isalnum() and not ('\u4e00' <= c <= '\u9fff')
                        for c in text
                    )
                    if only_symbol or text.isdigit():
                        continue
                    xs = [p[0] / upscale + x for p in box]
                    ys = [p[1] / upscale + y for p in box]
                    bx = int(min(xs))
                    by = int(min(ys))
                    bw = int(max(xs) - min(xs))
                    bh = int(max(ys) - min(ys))
                    boxes.append((bx, by, bw, bh))
                    texts.append(text)

            t_trans = time.time()
            translations = self.translator.translate_batch(texts)
            t_trans_done = time.time()

            items = [(b[0], b[1], b[2], b[3], tr)
                     for b, tr in zip(boxes, translations)]

            self.result_ready.emit(items)
            self.status_update.emit(
                f"[框选] 识别 {len(texts):>3} 条 | "
                f"OCR {t_ocr_done-t_ocr:>4.2f}s | "
                f"翻译 {t_trans_done-t_trans:>4.2f}s | "
                f"总计 {t_trans_done-t0:>4.2f}s"
            )
        except Exception as e:
            self.status_update.emit(f"框选错误：{type(e).__name__} - {e}")


# ================== 快捷键信号桥 ==================
class HotkeyBridge(QObject):
    triggered = pyqtSignal()


# ================== 主应用 ==================
class ScreenTranslatorApp:
    def __init__(self):
        print("加载 OCR 模型...")
        self.ocr = PaddleOCR(
            use_angle_cls=False, lang='ch', show_log=False,
            det_limit_side_len=960,
            det_db_unclip_ratio=2.0,
            rec_batch_num=6
        )
        print("OCR 模型就绪")

        self.translator = Translator()
        self.overlay = Overlay()
        self.overlay.show()
        self.overlay.hide()
        self.toast = Toast()

        self.full_worker = None
        self.region_worker = None
        self.region_selector = None
        self.settings_window = None
        self.mode = None

        # 信号桥
        self.hotkey_full_bridge = HotkeyBridge()
        self.hotkey_full_bridge.triggered.connect(self.toggle_full)
        self.hotkey_region_bridge = HotkeyBridge()
        self.hotkey_region_bridge.triggered.connect(self.trigger_region)
        self.hotkey_clear_bridge = HotkeyBridge()
        self.hotkey_clear_bridge.triggered.connect(self.clear_region_result)

        self._setup_hotkeys()
        self._setup_tray()
        self._print_ready()

    def _print_ready(self):
        s = S()
        print(f"\n准备就绪！")
        print(f"  {s['hotkey_full']}     →  全屏持续翻译（开关）")
        print(f"  {s['hotkey_region']}     →  框选一次性翻译")
        print(f"  {s['hotkey_clear']}      →  清除框选译文")
        print(f"  右键托盘图标 → 设置 / 退出\n")

    # ================== 快捷键 ==================
    def _setup_hotkeys(self):
        self._stop_hotkeys()
        s = S()

        def make_listener(hotkey_str, bridge, attr_name):
            def on_activate():
                bridge.triggered.emit()
            hk = keyboard.HotKey(keyboard.HotKey.parse(hotkey_str), on_activate)
            def for_canonical(f):
                return lambda k: f(listener.canonical(k))
            listener = keyboard.Listener(
                on_press=for_canonical(hk.press),
                on_release=for_canonical(hk.release),
            )
            listener.start()
            setattr(self, attr_name, listener)

        make_listener(s["hotkey_full"], self.hotkey_full_bridge,
                      "_listener_full")
        make_listener(s["hotkey_region"], self.hotkey_region_bridge,
                      "_listener_region")
        make_listener(s["hotkey_clear"], self.hotkey_clear_bridge,
                      "_listener_clear")

    def _stop_hotkeys(self):
        for name in ("_listener_full", "_listener_region", "_listener_clear"):
            l = getattr(self, name, None)
            if l is not None:
                try:
                    l.stop()
                except Exception:
                    pass
                setattr(self, name, None)

    # ================== 托盘 ==================
    def _make_tray_icon(self):
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor(50, 120, 220))
        p.setPen(Qt.NoPen)
        p.drawEllipse(2, 2, 60, 60)
        p.setPen(QColor(255, 255, 255))
        p.setFont(QFont("Microsoft YaHei", 32, QFont.Bold))
        p.drawText(pixmap.rect(), Qt.AlignCenter, "译")
        p.end()
        return QIcon(pixmap)

    def _setup_tray(self):
        self.tray = QSystemTrayIcon()
        self.tray.setIcon(self._make_tray_icon())
        self.tray.setToolTip("屏幕翻译")

        menu = QMenu()

        a_full = QAction(f"全屏模式 ({S()['hotkey_full']})", menu)
        a_full.triggered.connect(self.toggle_full)
        menu.addAction(a_full)

        a_region = QAction(f"框选模式 ({S()['hotkey_region']})", menu)
        a_region.triggered.connect(self.trigger_region)
        menu.addAction(a_region)

        menu.addSeparator()

        a_clear = QAction(f"清除译文 ({S()['hotkey_clear']})", menu)
        a_clear.triggered.connect(self.clear_region_result)
        menu.addAction(a_clear)

        menu.addSeparator()

        a_settings = QAction("设置...", menu)
        a_settings.triggered.connect(self.open_settings)
        menu.addAction(a_settings)

        menu.addSeparator()

        a_quit = QAction("退出", menu)
        a_quit.triggered.connect(self.quit)
        menu.addAction(a_quit)

        self.tray.setContextMenu(menu)
        self.tray.show()
        self.tray.setVisible(True)
        self.tray.activated.connect(self._on_tray_activated)

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.toggle_full()

    # ================== 设置窗口 ==================
    def open_settings(self):
        if self.settings_window is not None and self.settings_window.isVisible():
            self.settings_window.raise_()
            self.settings_window.activateWindow()
            return

        # 延迟导入避免循环导入
        from settings_window import SettingsWindow, GLOBAL_QSS
        QApplication.instance().setStyleSheet(GLOBAL_QSS)

        self.settings_window = SettingsWindow(settings=S())
        self.settings_window.settings_saved.connect(self._on_settings_saved)
        self.settings_window.show()

    def _on_settings_saved(self):
        """设置保存后：做热重载"""
        print("[设置] 应用新配置...")
        # 1. 重新注册快捷键
        self._setup_hotkeys()
        # 2. 覆盖层重绘（颜色、字体等会立即生效）
        self.overlay.update()
        # 3. 刷新托盘提示
        self.tray.setToolTip("屏幕翻译")
        print("[设置] 新配置已生效")

    # ================== 全屏模式 ==================
    def toggle_full(self):
        if self.mode == "full":
            self.stop_full()
        else:
            self.stop_region_translation()
            self.start_full()

    def start_full(self):
        print("[启动] 全屏翻译循环")
        self.mode = "full"
        self.overlay.clear()
        self.overlay.show()
        self.toast.show_toast("等待屏幕稳定...")

        self.full_worker = FullWorker(self.ocr, self.translator)
        self.full_worker.result_ready.connect(self.overlay.update_items)
        self.full_worker.clear_signal.connect(self.overlay.clear)
        self.full_worker.status_update.connect(self._on_status)
        self.full_worker.toast_signal.connect(self._on_toast)
        self.full_worker.running = True
        self.full_worker.start()

    def stop_full(self):
        if self.mode != "full":
            return
        print("[停止] 全屏翻译循环")
        self.mode = None
        if self.full_worker is not None:
            self.full_worker.stop()
            self.full_worker.wait()
            self.full_worker = None
        self.overlay.clear()
        self.overlay.hide()
        self.toast.hide_toast()

    # ================== 框选模式 ==================
    def trigger_region(self):
        self.stop_full()
        self.stop_region_translation()
        self.overlay.clear()
        self.overlay.hide()
        self.toast.hide_toast()

        print("[框选] 等待用户选择区域...")
        self.region_selector = RegionSelector()
        self.region_selector.region_selected.connect(self._on_region_selected)
        self.region_selector.cancelled.connect(self._on_region_cancelled)
        self.region_selector.showFullScreen()
        self.region_selector.activateWindow()

    def _on_region_cancelled(self):
        print("[框选] 用户取消")
        self.region_selector = None

    def clear_region_result(self):
        if self.mode == "full":
            print("[清除] 全屏模式运行中，请用全屏快捷键停止")
            return
        if self.region_worker is None and not self.overlay.items:
            return
        print("[清除] 移除框选译文")
        self.stop_region_translation()
        self.overlay.clear()
        self.overlay.hide()
        self.toast.hide_toast()

    def _on_region_selected(self, x, y, w, h):
        print(f"[框选] 区域 ({x}, {y}, {w}, {h})，开始翻译...")
        self.region_selector = None

        self.overlay.show()
        self.toast.show_toast("正在翻译选中区域...")

        self.region_worker = RegionWorker(self.ocr, self.translator,
                                          (x, y, w, h))
        self.region_worker.result_ready.connect(self._on_region_result)
        self.region_worker.status_update.connect(self._on_status)
        self.region_worker.finished.connect(self._on_region_finished)
        self.region_worker.start()

    def _on_region_result(self, items):
        self.overlay.update_items(items)
        self.toast.hide_toast()

    def _on_region_finished(self):
        self.region_worker = None

    def stop_region_translation(self):
        if self.region_worker is not None:
            self.region_worker.wait()
            self.region_worker = None

    # ================== 状态回调 ==================
    def _on_status(self, msg):
        print(f"  {msg}")

    def _on_toast(self, text, show):
        if show:
            self.toast.show_toast(text)
        else:
            self.toast.hide_toast()

    def quit(self):
        print("\n退出中...")
        self.stop_full()
        self.stop_region_translation()
        self._stop_hotkeys()
        self.tray.hide()
        QApplication.quit()


# ================== 入口 ==================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    controller = ScreenTranslatorApp()
    sys.exit(app.exec_())