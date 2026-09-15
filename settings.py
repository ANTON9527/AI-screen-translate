# ============================================
# settings.py
# 配置项定义 + JSON 读写
# ============================================

import json
import os
import sys


# ---------- 所有可配置项的默认值 ----------
DEFAULTS = {
    "hotkey_full":   "<shift>+t",
    "hotkey_region": "<shift>+r",
    "hotkey_clear":  "<alt>+r",

    "font_family":  "Microsoft YaHei",
    "min_font":     9,
    "max_font":     36,
    "bg_color":     [0, 0, 0],
    "bg_alpha":     245,
    "text_color":   [255, 255, 255],
    "pad_x":        2,
    "pad_y":        1,

    "check_interval":  0.15,
    "diff_threshold":  3.0,
    "stable_frames":   2,

    "scale":           1.0,
    "region_upscale":  1.5,
    "min_confidence":  0.6,

    "window_width":    640,
    "window_height":   800,
}


class Settings:
    """轻量配置对象，用字典 + JSON 文件存储"""

    def __init__(self, data=None):
        self.data = dict(DEFAULTS)
        if data:
            for k, v in data.items():
                if k in DEFAULTS:
                    self.data[k] = v

    @classmethod
    def load(cls, path=None):
        if path is None:
            path = cls.default_path()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return cls(json.load(f))
            except Exception as e:
                print(f"[settings] 读取失败 {e}，使用默认值")
        return cls()

    def save(self, path=None):
        if path is None:
            path = self.default_path()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def reset(self):
        self.data = dict(DEFAULTS)

    def __getitem__(self, key):
        return self.data.get(key, DEFAULTS.get(key))

    def __setitem__(self, key, value):
        self.data[key] = value

    @staticmethod
    def default_path():
        # ★ 打包后：settings.json 放在 exe 同级目录
        #   开发环境：放在项目根目录
        if getattr(sys, "frozen", False):
            base = os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base, "settings.json")