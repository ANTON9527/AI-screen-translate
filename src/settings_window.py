# ============================================
# settings_window.py
# 图形化设置窗口（纯文字 + 可缩放 + 滚轮防误触）
# ============================================

import sys
import os

_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_here)
sys.path.append(_root)

from settings import Settings, DEFAULTS

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QSpinBox, QDoubleSpinBox, QSlider, QPushButton,
    QComboBox, QFrame, QColorDialog, QScrollArea
)
from PyQt5.QtCore import Qt, QEvent, pyqtSignal
from PyQt5.QtGui import QColor, QIcon, QPixmap, QCursor


# ---------- 配色常量 ----------
C_BG       = "#1e1e1e"
C_PANEL    = "#252526"
C_INPUT    = "#3c3c3c"
C_BORDER   = "#3e3e42"
C_TEXT     = "#e0e0e0"
C_TEXT_DIM = "#969696"
C_ACCENT   = "#007acc"
C_ACCENT_H = "#1a8ad4"
C_DANGER   = "#c42b1c"

RESIZE_MARGIN = 8


# ---------- 全局 QSS ----------
GLOBAL_QSS = f"""
QWidget {{
    background: {C_BG};
    color: {C_TEXT};
    font-family: "Microsoft YaHei";
    font-size: 13px;
}}
QFrame#Panel {{
    background: {C_PANEL};
    border: 1px solid {C_BORDER};
    border-radius: 6px;
}}
QFrame#RootFrame {{
    background: {C_BG};
    border: 1px solid {C_BORDER};
    border-radius: 8px;
}}
QFrame#TitleBar {{
    background: {C_PANEL};
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
}}
QLabel#Title {{
    font-size: 15px;
    font-weight: bold;
    color: {C_TEXT};
    background: transparent;
}}
QLabel#GroupTitle {{
    font-size: 13px;
    font-weight: bold;
    color: {C_TEXT};
    background: transparent;
    padding: 2px 0;
}}
QLabel#FieldLabel {{
    color: {C_TEXT_DIM};
    background: transparent;
}}
QLabel#Hint {{
    color: {C_TEXT_DIM};
    font-size: 11px;
    background: transparent;
}}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {C_INPUT};
    border: 1px solid {C_BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    color: {C_TEXT};
    selection-background-color: {C_ACCENT};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1px solid {C_ACCENT};
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background: {C_INPUT};
    color: {C_TEXT};
    selection-background-color: {C_ACCENT};
    border: 1px solid {C_BORDER};
}}
QSlider::groove:horizontal {{
    height: 4px;
    background: {C_INPUT};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {C_ACCENT};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}
QSlider::handle:horizontal:hover {{
    background: {C_ACCENT_H};
}}
QPushButton {{
    background: {C_INPUT};
    border: 1px solid {C_BORDER};
    border-radius: 4px;
    padding: 6px 16px;
    color: {C_TEXT};
}}
QPushButton:hover {{
    background: #4a4a4d;
}}
QPushButton#Primary {{
    background: {C_ACCENT};
    border: 1px solid {C_ACCENT};
    color: white;
    font-weight: bold;
}}
QPushButton#Primary:hover {{
    background: {C_ACCENT_H};
}}
QPushButton#CloseBtn {{
    background: transparent;
    border: none;
    color: {C_TEXT_DIM};
    font-size: 13px;
    padding: 4px 10px;
    font-weight: bold;
}}
QPushButton#CloseBtn:hover {{
    background: {C_DANGER};
    color: white;
    border-radius: 4px;
}}
QScrollArea {{
    border: none;
    background: {C_BG};
}}
QScrollBar:vertical {{
    background: {C_BG};
    width: 8px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: {C_BORDER};
    border-radius: 4px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background: {C_ACCENT};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
"""


# ---------- 可拖拽标题栏 ----------
class TitleBar(QFrame):
    def __init__(self, title, parent_window):
        super().__init__()
        self.setObjectName("TitleBar")
        self.setFixedHeight(40)
        self.parent_window = parent_window
        self._drag_pos = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 8, 0)

        title_label = QLabel(title)
        title_label.setObjectName("Title")
        layout.addWidget(title_label)
        layout.addStretch()

        btn_close = QPushButton("关闭")
        btn_close.setObjectName("CloseBtn")
        btn_close.setFixedSize(48, 28)
        btn_close.clicked.connect(parent_window.close)
        layout.addWidget(btn_close)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = (e.globalPos()
                              - self.parent_window.frameGeometry().topLeft())

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() == Qt.LeftButton:
            self.parent_window.move(e.globalPos() - self._drag_pos)

    def mouseReleaseEvent(self, e):
        self._drag_pos = None


# ---------- 颜色按钮 ----------
class ColorButton(QPushButton):
    def __init__(self, color_list):
        super().__init__()
        self._color = QColor(*color_list)
        self.setFixedWidth(100)
        self._refresh()

    def _refresh(self):
        self.setText(f"  #{self._color.red():02X}"
                     f"{self._color.green():02X}"
                     f"{self._color.blue():02X}")
        pixmap = QPixmap(14, 14)
        pixmap.fill(self._color)
        self.setIcon(QIcon(pixmap))

    def get_color(self):
        return [self._color.red(), self._color.green(), self._color.blue()]

    def mousePressEvent(self, e):
        c = QColorDialog.getColor(self._color, self, "选择颜色")
        if c.isValid():
            self._color = c
            self._refresh()


# ---------- 设置窗口 ----------
class SettingsWindow(QWidget):
    # ★ 保存完成信号，主程序连接它做热重载
    settings_saved = pyqtSignal()

    def __init__(self, settings=None):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 如果传入了 settings 对象就复用，否则自己加载
        if settings is not None:
            self.settings = settings
        else:
            self.settings = Settings.load()

        self._widgets = {}
        self._scroll = None

        self.setMinimumSize(480, 560)
        w = self.settings["window_width"]
        h = self.settings["window_height"]
        self.resize(max(480, w), max(560, h))

        self._drag_mode = None
        self._drag_start_geo = None
        self._drag_start_pos = None

        self.setMouseTracking(True)

        self._build_ui()
        self._load_values()
        self._install_filters()

        screen = QApplication.primaryScreen().geometry()
        self.move((screen.width() - self.width()) // 2,
                  (screen.height() - self.height()) // 2)

    # ---------- 构建 UI ----------
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        root = QFrame()
        root.setObjectName("RootFrame")
        outer.addWidget(root)

        main = QVBoxLayout(root)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        main.addWidget(TitleBar("屏幕翻译 · 设置", self))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        scroll.setWidget(content)
        self._scroll = scroll
        main.addWidget(scroll, 1)

        vbox = QVBoxLayout(content)
        vbox.setContentsMargins(20, 16, 20, 16)
        vbox.setSpacing(18)

        vbox.addWidget(self._build_group_hotkey())
        vbox.addWidget(self._build_group_appearance())
        vbox.addWidget(self._build_group_speed())
        vbox.addWidget(self._build_group_ocr())
        vbox.addStretch()

        # ---- 底部按钮栏 ----
        bottom = QFrame()
        bottom.setFixedHeight(60)
        bottom.setStyleSheet(
            f"QFrame {{ background: {C_PANEL};"
            f" border-top: 1px solid {C_BORDER};"
            f" border-bottom-left-radius: 8px;"
            f" border-bottom-right-radius: 8px; }}"
        )
        b_layout = QHBoxLayout(bottom)
        b_layout.setContentsMargins(20, 0, 20, 0)

        btn_reset = QPushButton("恢复默认")
        btn_reset.clicked.connect(self._on_reset)
        b_layout.addWidget(btn_reset)

        b_layout.addStretch()

        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.close)
        b_layout.addWidget(btn_cancel)

        btn_save = QPushButton("保存")
        btn_save.setObjectName("Primary")
        btn_save.clicked.connect(self._on_save)
        b_layout.addWidget(btn_save)

        main.addWidget(bottom)

    def _make_panel(self):
        panel = QFrame()
        panel.setObjectName("Panel")
        layout = QGridLayout(panel)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setHorizontalSpacing(14)
        layout.setVerticalSpacing(10)
        layout.setColumnStretch(1, 1)
        return panel, layout

    def _build_group_hotkey(self):
        container = QWidget()
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(8)

        title = QLabel("快捷键")
        title.setObjectName("GroupTitle")
        vbox.addWidget(title)

        panel, grid = self._make_panel()
        vbox.addWidget(panel)

        self._add_field(grid, 0, "全屏翻译", QLineEdit(), "hotkey_full")
        self._add_field(grid, 1, "框选翻译", QLineEdit(), "hotkey_region")
        self._add_field(grid, 2, "清除译文", QLineEdit(), "hotkey_clear")

        hint = QLabel("格式示例：  <shift>+t      <ctrl>+<alt>+r")
        hint.setObjectName("Hint")
        vbox.addWidget(hint)
        return container

    def _build_group_appearance(self):
        container = QWidget()
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(8)

        title = QLabel("覆盖层外观")
        title.setObjectName("GroupTitle")
        vbox.addWidget(title)

        panel, grid = self._make_panel()
        vbox.addWidget(panel)

        font_box = QComboBox()
        font_box.addItems([
            "Microsoft YaHei", "SimHei", "SimSun", "KaiTi",
            "Source Han Sans CN", "PingFang SC", "Arial"
        ])
        self._add_field(grid, 0, "字体", font_box, "font_family")

        row_widget = QWidget()
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self._widgets["min_font"] = QSpinBox()
        self._widgets["min_font"].setRange(6, 60)
        self._widgets["max_font"] = QSpinBox()
        self._widgets["max_font"].setRange(10, 120)
        row.addWidget(self._widgets["min_font"])
        row.addWidget(QLabel("~"))
        row.addWidget(self._widgets["max_font"])
        row.addStretch()
        grid.addWidget(QLabel("字号范围"), 1, 0)
        grid.addWidget(row_widget, 1, 1)

        self._widgets["bg_color"] = ColorButton([0, 0, 0])
        grid.addWidget(QLabel("背景色"), 2, 0)
        grid.addWidget(self._widgets["bg_color"], 2, 1)

        alpha_widget = QWidget()
        alpha_lay = QHBoxLayout(alpha_widget)
        alpha_lay.setContentsMargins(0, 0, 0, 0)
        alpha_lay.setSpacing(8)
        self._widgets["bg_alpha"] = QSlider(Qt.Horizontal)
        self._widgets["bg_alpha"].setRange(0, 255)
        self._alpha_label = QLabel("245")
        self._alpha_label.setFixedWidth(36)
        self._alpha_label.setStyleSheet(f"color: {C_TEXT};")
        self._widgets["bg_alpha"].valueChanged.connect(
            lambda v: self._alpha_label.setText(str(v))
        )
        alpha_lay.addWidget(self._widgets["bg_alpha"], 1)
        alpha_lay.addWidget(self._alpha_label)
        grid.addWidget(QLabel("背景透明度"), 3, 0)
        grid.addWidget(alpha_widget, 3, 1)

        self._widgets["text_color"] = ColorButton([255, 255, 255])
        grid.addWidget(QLabel("文字颜色"), 4, 0)
        grid.addWidget(self._widgets["text_color"], 4, 1)

        pad_widget = QWidget()
        pad_lay = QHBoxLayout(pad_widget)
        pad_lay.setContentsMargins(0, 0, 0, 0)
        pad_lay.setSpacing(8)
        self._widgets["pad_x"] = QSpinBox()
        self._widgets["pad_x"].setRange(0, 20)
        self._widgets["pad_y"] = QSpinBox()
        self._widgets["pad_y"].setRange(0, 20)
        pad_lay.addWidget(self._widgets["pad_x"])
        pad_lay.addWidget(QLabel("/"))
        pad_lay.addWidget(self._widgets["pad_y"])
        pad_lay.addStretch()
        grid.addWidget(QLabel("边距 (X / Y)"), 5, 0)
        grid.addWidget(pad_widget, 5, 1)

        return container

    def _build_group_speed(self):
        container = QWidget()
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(8)

        title = QLabel("响应速度")
        title.setObjectName("GroupTitle")
        vbox.addWidget(title)

        panel, grid = self._make_panel()
        vbox.addWidget(panel)

        w1 = QDoubleSpinBox(); w1.setRange(0.05, 2.0); w1.setSingleStep(0.05)
        w1.setDecimals(2)
        self._add_field(grid, 0, "检测频率 (秒)", w1, "check_interval")

        w2 = QDoubleSpinBox(); w2.setRange(0.5, 30.0); w2.setSingleStep(0.5)
        w2.setDecimals(1)
        self._add_field(grid, 1, "差异阈值", w2, "diff_threshold")

        w3 = QSpinBox(); w3.setRange(1, 10)
        self._add_field(grid, 2, "静止帧数", w3, "stable_frames")

        hint = QLabel("检测频率越低反应越快；差异阈值越低越敏感；"
                      "静止帧数越高越稳")
        hint.setObjectName("Hint")
        vbox.addWidget(hint)
        return container

    def _build_group_ocr(self):
        container = QWidget()
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(8)

        title = QLabel("OCR")
        title.setObjectName("GroupTitle")
        vbox.addWidget(title)

        panel, grid = self._make_panel()
        vbox.addWidget(panel)

        w1 = QDoubleSpinBox(); w1.setRange(0.3, 2.0); w1.setSingleStep(0.1)
        w1.setDecimals(2)
        self._add_field(grid, 0, "图像缩放", w1, "scale")

        w2 = QDoubleSpinBox(); w2.setRange(1.0, 3.0); w2.setSingleStep(0.1)
        w2.setDecimals(2)
        self._add_field(grid, 1, "框选放大", w2, "region_upscale")

        w3 = QDoubleSpinBox(); w3.setRange(0.1, 0.95); w3.setSingleStep(0.05)
        w3.setDecimals(2)
        self._add_field(grid, 2, "最小置信度", w3, "min_confidence")

        hint = QLabel("图像缩放越高 OCR 越准但越慢；"
                      "最小置信度以下的识别结果将被丢弃")
        hint.setObjectName("Hint")
        vbox.addWidget(hint)
        return container

    def _add_field(self, grid, row, label_text, widget, key):
        label = QLabel(label_text)
        label.setObjectName("FieldLabel")
        grid.addWidget(label, row, 0)
        grid.addWidget(widget, row, 1)
        self._widgets[key] = widget

    def _load_values(self):
        s = self.settings
        for key, w in self._widgets.items():
            val = s[key]
            if isinstance(w, QLineEdit):
                w.setText(str(val))
            elif isinstance(w, QComboBox):
                idx = w.findText(str(val))
                if idx >= 0:
                    w.setCurrentIndex(idx)
            elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
                w.setValue(val)
            elif isinstance(w, QSlider):
                w.setValue(int(val))

        self._widgets["bg_color"]._color = QColor(*s["bg_color"])
        self._widgets["bg_color"]._refresh()
        self._widgets["text_color"]._color = QColor(*s["text_color"])
        self._widgets["text_color"]._refresh()

    def _collect_values(self):
        result = {}
        for key, w in self._widgets.items():
            if isinstance(w, QLineEdit):
                result[key] = w.text().strip()
            elif isinstance(w, QComboBox):
                result[key] = w.currentText()
            elif isinstance(w, QSpinBox):
                result[key] = int(w.value())
            elif isinstance(w, QDoubleSpinBox):
                result[key] = float(w.value())
            elif isinstance(w, QSlider):
                result[key] = int(w.value())
            elif isinstance(w, ColorButton):
                result[key] = w.get_color()
        result["window_width"] = self.width()
        result["window_height"] = self.height()
        return result

    # ---------- 按钮回调 ----------
    def _on_reset(self):
        for key, w in self._widgets.items():
            val = DEFAULTS[key]
            if isinstance(w, QLineEdit):
                w.setText(str(val))
            elif isinstance(w, QComboBox):
                idx = w.findText(str(val))
                if idx >= 0:
                    w.setCurrentIndex(idx)
            elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
                w.setValue(val)
            elif isinstance(w, QSlider):
                w.setValue(int(val))

        self._widgets["bg_color"]._color = QColor(*DEFAULTS["bg_color"])
        self._widgets["bg_color"]._refresh()
        self._widgets["text_color"]._color = QColor(*DEFAULTS["text_color"])
        self._widgets["text_color"]._refresh()

    # ★ 保存：带异常兜底，即使出错也不会拖垮主程序
    def _on_save(self):
        try:
            vals = self._collect_values()
            for k, v in vals.items():
                self.settings[k] = v
            self.settings.save()
            print(f"[设置] 已保存到 {Settings.default_path()}")
            # 发送信号，主程序收到后做热重载
            self.settings_saved.emit()
            self.close()
        except Exception as e:
            import traceback
            print(f"[设置] 保存失败：{type(e).__name__} - {e}")
            traceback.print_exc()

    # ==========================================
    # 事件过滤器
    # ==========================================
    def _install_filters(self):
        for w in self.findChildren(QWidget):
            w.setMouseTracking(True)
            w.installEventFilter(self)

    def eventFilter(self, obj, event):
        et = event.type()

        if et in (QEvent.MouseMove, QEvent.MouseButtonPress,
                  QEvent.MouseButtonRelease):
            try:
                gpos = event.globalPos()
            except Exception:
                gpos = None
            local = self.mapFromGlobal(gpos) if gpos is not None else None
        else:
            local = None

        if et == QEvent.MouseMove and local is not None:
            if self._drag_mode:
                self._apply_resize(gpos)
                return True
            edge = self._edge_at(local)
            if edge:
                self.setCursor(QCursor(self._cursor_for(edge)))
            else:
                self.setCursor(QCursor(Qt.ArrowCursor))
            return False

        if (et == QEvent.MouseButtonPress
                and event.button() == Qt.LeftButton
                and local is not None):
            edge = self._edge_at(local)
            if edge:
                self._drag_mode = edge
                self._drag_start_geo = (self.x(), self.y(),
                                        self.width(), self.height())
                self._drag_start_pos = gpos
                return True
            return False

        if et == QEvent.MouseButtonRelease and self._drag_mode:
            self._drag_mode = None
            self._drag_start_geo = None
            self._drag_start_pos = None
            return True

        if et == QEvent.Wheel:
            if isinstance(obj, (QSpinBox, QDoubleSpinBox,
                                QComboBox, QSlider)):
                if self._scroll is not None:
                    QApplication.sendEvent(self._scroll.viewport(), event)
                return True

        return super().eventFilter(obj, event)

    def _edge_at(self, pos):
        if pos is None:
            return None
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        m = RESIZE_MARGIN

        if x < -m or x > w + m or y < -m or y > h + m:
            return None

        left   = x < m
        right  = x > w - m
        top    = y < m
        bottom = y > h - m

        if top and left:     return 'tl'
        if top and right:    return 'tr'
        if bottom and left:  return 'bl'
        if bottom and right: return 'br'
        if left:             return 'l'
        if right:            return 'r'
        if top:              return 't'
        if bottom:           return 'b'
        return None

    def _cursor_for(self, edge):
        return {
            'l':  Qt.SizeHorCursor,
            'r':  Qt.SizeHorCursor,
            't':  Qt.SizeVerCursor,
            'b':  Qt.SizeVerCursor,
            'tl': Qt.SizeFDiagCursor,
            'br': Qt.SizeFDiagCursor,
            'tr': Qt.SizeBDiagCursor,
            'bl': Qt.SizeBDiagCursor,
        }.get(edge, Qt.ArrowCursor)

    def _apply_resize(self, global_pos):
        if not self._drag_mode:
            return
        delta = global_pos - self._drag_start_pos
        dx, dy = delta.x(), delta.y()
        x0, y0, w0, h0 = self._drag_start_geo
        min_w, min_h = self.minimumWidth(), self.minimumHeight()

        new_x, new_y, new_w, new_h = x0, y0, w0, h0
        mode = self._drag_mode

        if 'l' in mode:
            new_w = max(min_w, w0 - dx)
            new_x = x0 + (w0 - new_w)
        if 'r' in mode:
            new_w = max(min_w, w0 + dx)
        if 't' in mode:
            new_h = max(min_h, h0 - dy)
            new_y = y0 + (h0 - new_h)
        if 'b' in mode:
            new_h = max(min_h, h0 + dy)

        self.setGeometry(new_x, new_y, new_w, new_h)


# ---------- 独立运行入口 ----------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(GLOBAL_QSS)
    win = SettingsWindow()
    win.show()
    sys.exit(app.exec_())