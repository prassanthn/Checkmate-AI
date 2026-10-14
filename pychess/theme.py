"""Colors and the Qt stylesheet for the dark, modern look."""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

APP_NAME = "Checkmate AI"

BG = "#0f1218"
SURFACE = "#171b23"
SURFACE_2 = "#1f2430"
HOVER = "#2a3040"
BORDER = "#2a303c"
TEXT = "#e7eaf0"
MUTED = "#8a93a6"
ACCENT = "#f2b84b"
ACCENT_TEXT = "#1a1406"

# Board palette (also used by BoardWidget)
BOARD_LIGHT = QColor("#e3e8ee")
BOARD_DARK = QColor("#7f97ae")

STATUS_COLORS = {
    "your-turn": ("#1f3a2a", "#6ee7a0"),
    "thinking": ("#3a2f17", ACCENT),
    "error": ("#3d1f22", "#ff8a8a"),
    "over": ("#262b36", MUTED),
}
INFO_COLORS = {
    "info": "#7c9cff",
    "warning": ACCENT,
    "error": "#ff6b6b",
}


def stylesheet() -> str:
    status_rules = "\n".join(
        f'QLabel#StatusPill[state="{state}"] {{ background: {bg}; color: {fg}; }}'
        for state, (bg, fg) in STATUS_COLORS.items()
    )
    info_rules = "\n".join(
        f'QFrame#InfoBar[level="{level}"] {{ border-left: 4px solid {color}; }}'
        for level, color in INFO_COLORS.items()
    )
    return f"""
    * {{ color: {TEXT}; }}
    QMainWindow, QDialog, QWidget#Central {{ background: {BG}; }}
    QToolTip {{ background: {SURFACE_2}; color: {TEXT}; border: 1px solid {BORDER}; padding: 4px 8px; }}

    QFrame#Header {{ background: {SURFACE}; border-bottom: 1px solid {BORDER}; }}
    QLabel#AppTitle {{ font-size: 17pt; font-weight: 700; }}
    QLabel#AppSubtitle {{ color: {MUTED}; }}

    QPushButton {{
        background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 8px;
        padding: 7px 14px; font-weight: 500;
    }}
    QPushButton:hover {{ background: {HOVER}; }}
    QPushButton:pressed {{ background: {BORDER}; }}
    QPushButton:disabled {{ color: #4f5666; background: {SURFACE}; }}
    QPushButton#Primary {{ background: {ACCENT}; color: {ACCENT_TEXT}; border: none; font-weight: 700; }}
    QPushButton#Primary:hover {{ background: #f6c768; }}

    QFrame#Segmented {{ background: {BG}; border: 1px solid {BORDER}; border-radius: 9px; }}
    QFrame#Segmented QPushButton {{
        background: transparent; border: none; border-radius: 7px; padding: 6px 10px; color: {MUTED};
    }}
    QFrame#Segmented QPushButton:hover {{ color: {TEXT}; }}
    QFrame#Segmented QPushButton:checked {{ background: {SURFACE_2}; color: {ACCENT}; font-weight: 700; }}

    QFrame#Card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 14px; }}
    QLabel#CardTitle {{ color: {MUTED}; font-size: 8pt; font-weight: 700; letter-spacing: 1px; }}
    QLabel#Muted {{ color: {MUTED}; }}
    QLabel#ModelName {{ font-size: 11pt; font-weight: 600; }}
    QLabel#StatValue {{ font-size: 16pt; font-weight: 700; }}
    QLabel#Clock {{ font-size: 15pt; font-weight: 600; font-family: "Cascadia Mono", "Consolas", monospace; }}

    QLabel#StatusPill {{ border-radius: 10px; padding: 3px 10px; font-weight: 600; font-size: 8.5pt; }}
    {status_rules}

    QTableWidget {{
        background: transparent; border: none; gridline-color: transparent;
        selection-background-color: {SURFACE_2}; outline: none;
    }}
    QTableWidget::item {{ padding: 4px 6px; border: none; }}
    QTableWidget::item:selected {{ background: {SURFACE_2}; color: {ACCENT}; }}
    QHeaderView {{ background: transparent; border: none; }}
    QTableCornerButton::section {{ background: transparent; border: none; }}
    QHeaderView::section {{
        background: transparent; color: {MUTED}; border: none; border-bottom: 1px solid {BORDER};
        padding: 4px 6px; font-weight: 600; font-size: 8.5pt;
    }}

    QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {HOVER}; border-radius: 4px; min-height: 24px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

    QFrame#InfoBar {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; }}
    {info_rules}
    QLabel#InfoText {{ font-size: 10pt; }}

    QLineEdit, QComboBox {{
        background: {BG}; border: 1px solid {BORDER}; border-radius: 8px; padding: 6px 10px;
        selection-background-color: {ACCENT}; selection-color: {ACCENT_TEXT};
    }}
    QLineEdit:focus, QComboBox:focus {{ border: 1px solid {ACCENT}; }}
    QLineEdit:disabled {{ color: #4f5666; }}
    QComboBox::drop-down {{ border: none; width: 22px; }}
    QComboBox QAbstractItemView {{
        background: {SURFACE_2}; border: 1px solid {BORDER}; selection-background-color: {HOVER};
        outline: none; padding: 4px;
    }}
    QLabel#Hint {{ color: {MUTED}; }}
    QMessageBox QLabel {{ font-size: 10pt; }}
    """


def apply(app: QApplication) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: BG, QPalette.ColorRole.Base: BG,
        QPalette.ColorRole.AlternateBase: SURFACE, QPalette.ColorRole.Button: SURFACE_2,
        QPalette.ColorRole.WindowText: TEXT, QPalette.ColorRole.Text: TEXT,
        QPalette.ColorRole.ButtonText: TEXT, QPalette.ColorRole.ToolTipBase: SURFACE_2,
        QPalette.ColorRole.ToolTipText: TEXT, QPalette.ColorRole.Highlight: ACCENT,
        QPalette.ColorRole.HighlightedText: ACCENT_TEXT, QPalette.ColorRole.PlaceholderText: MUTED,
    }
    for role, color in roles.items():
        palette.setColor(role, QColor(color))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#4f5666"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#4f5666"))
    app.setPalette(palette)
    font = QFont()
    font.setFamilies(["Segoe UI Variable Text", "Segoe UI", "Inter", "Helvetica Neue", "Arial"])
    font.setPointSizeF(10)
    app.setFont(font)
    app.setStyleSheet(stylesheet())
