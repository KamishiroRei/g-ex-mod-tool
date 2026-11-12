"""Colors and typography for the G-EX Mod Tool desktop application."""

from pathlib import Path
import sys

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPainterPath, QPalette, QPen, QPixmap


BACKGROUND = "#111a23"
PANEL = "#19242e"
PANEL_DARK = "#151f29"
SURFACE = "#22313d"
BORDER = "#344451"
TEXT = "#edf1f3"
MUTED = "#a9b5bd"
ACCENT = "#73ccc4"


def stylesheet_paths():
    bundled = Path(__file__).resolve().parent / "editor.qss"
    if getattr(sys, "frozen", False):
        external = Path(sys.executable).resolve().parent / "gex_mod_tool" / "editor.qss"
        return [external, bundled] if external != bundled else [bundled]
    return [bundled]


def stylesheet_path():
    paths = stylesheet_paths()
    return next((path for path in paths if path.is_file()), paths[-1])


def load_stylesheet():
    return stylesheet_path().read_text(encoding="utf-8-sig")





def apply(application):
    application.setStyle("Fusion")
    hints = application.styleHints()
    if hasattr(hints, "setColorScheme") and hasattr(Qt, "ColorScheme"):
        hints.setColorScheme(Qt.ColorScheme.Dark)
    families = set(QFontDatabase.families())
    name = next((item for item in ("Microsoft YaHei UI", "Microsoft YaHei", "Noto Sans CJK SC", "Segoe UI")
                 if item in families), application.font().family())
    font = QFont(name)
    font.setPixelSize(14)
    application.setFont(font)
    palette = QPalette()
    for role, color in ((QPalette.ColorRole.Window, BACKGROUND), (QPalette.ColorRole.WindowText, TEXT),
                        (QPalette.ColorRole.Base, PANEL_DARK), (QPalette.ColorRole.AlternateBase, SURFACE),
                        (QPalette.ColorRole.Text, TEXT), (QPalette.ColorRole.Button, SURFACE),
                        (QPalette.ColorRole.ButtonText, TEXT), (QPalette.ColorRole.Highlight, "#315d60"),
                        (QPalette.ColorRole.HighlightedText, "#ffffff")):
        palette.setColor(role, QColor(color))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#6d7d88"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#6d7d88"))
    application.setPalette(palette)
    application.setStyleSheet(load_stylesheet())
    application.setWindowIcon(make_icon())


def dark_titlebar(window):
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes
        dwm = ctypes.WinDLL("dwmapi", use_last_error=True)
        dwm.DwmSetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
        enabled = ctypes.c_int(1)
        for attribute in (20, 19):
            if dwm.DwmSetWindowAttribute(int(window.winId()), attribute,
                                        ctypes.byref(enabled), ctypes.sizeof(enabled)) == 0:
                break
    except (AttributeError, OSError, TypeError, ValueError):
        pass


def make_icon():
    image = QPixmap(64, 64)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(ACCENT), 6)
    pen.setCapStyle(Qt.PenCapStyle.SquareCap)
    pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
    painter.setPen(pen)
    path = QPainterPath(QPointF(47, 15))
    path.lineTo(32, 7)
    path.lineTo(13, 17)
    path.lineTo(13, 47)
    path.lineTo(32, 57)
    path.lineTo(48, 48)
    path.lineTo(48, 33)
    path.lineTo(33, 33)
    painter.drawPath(path)
    painter.end()
    return QIcon(image)
