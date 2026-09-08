"""Design tokens for the quest-style task UI (mockup V2, 2026-08-18).

One-to-one translation of ``.local-dev/experiments/ui-redesign-20260818/mockup.html``
into Qt: a light and a dark palette plus small QSS builders shared by the task
cards, the daily board banner, the run panel and the navigation section labels.
The framework keeps managing the global accent color; these tokens only style
the widgets introduced by the quest UI so the two never fight.
"""

from __future__ import annotations

from pathlib import Path

from qfluentwidgets import isDarkTheme

BODY_FONT = '"MiSans", "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif'
MONO_FONT = (
    '"JetBrains Mono", "Cascadia Mono", "Cascadia Code", Consolas,'
    ' "Microsoft YaHei UI", monospace'
)

# Preferred global UI font stack, best first. Qt and qfluentwidgets resolve
# unavailable families through the platform fallback chain.
APP_FONT_FAMILIES = ("MiSans", "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI")


def _install_framework_fonts() -> None:
    """Keep upstream QSS from overriding the application's UI font families."""
    from ok.ui.qt.common.style_sheet import StyleSheet
    from ok.ui.qt.start.LogWindow import LogWindow
    from ok.ui.qt.util import app as app_module

    if getattr(StyleSheet, "_bd2_fonts_installed", False):
        return
    original_content = StyleSheet.content
    original_log_theme = LogWindow._apply_theme
    original_init = app_module.init_app_config
    families = ", ".join(f"'{family}'" for family in APP_FONT_FAMILIES)

    def content(self, *args, **kwargs):
        qss = original_content(self, *args, **kwargs)
        qss = qss.replace("'Segoe UI', 'Microsoft YaHei', 'PingFang SC'", families)
        qss = qss.replace(
            '\"Segoe UI SemiBold\", \"Microsoft YaHei\", \'PingFang SC\'',
            families + "; font-weight: 600",
        )
        return qss.replace("'Microsoft YaHei Light'", families + "; font-weight: 300")

    def log_theme(self):
        original_log_theme(self)
        self.status_label.setStyleSheet(f"font-family: {families};")

    def init_app_config():
        result = original_init()
        apply_app_font()
        return result

    StyleSheet.content = content
    LogWindow._apply_theme = log_theme
    app_module.init_app_config = init_app_config
    StyleSheet._bd2_fonts_installed = True


def apply_app_font() -> None:
    """Apply the project font stack before qfluentwidgets builds controls."""
    # Importing the app config first ensures its ui_config.json load cannot
    # overwrite the project stack after this call.
    from ok.ui.qt.common.config import cfg as _cfg  # noqa: F401
    from PySide6.QtWidgets import QApplication
    from qfluentwidgets import setFontFamilies

    families = list(APP_FONT_FAMILIES)
    setFontFamilies(families, save=False)
    _install_framework_fonts()

    app = QApplication.instance()
    if app is None:
        return
    if not app.property("bd2_bundled_font_loaded"):
        from PySide6.QtGui import QFontDatabase

        folder = Path(__file__).resolve().parents[2] / "assets/fonts"
        font_ids = [
            QFontDatabase.addApplicationFont(str(folder / f"MiSans-{style}.otf"))
            for style in ("Regular", "Bold")
        ]
        app.setProperty("bd2_bundled_font_loaded", all(font_id >= 0 for font_id in font_ids))
    font = app.font()
    font.setFamilies(families)
    app.setFont(font)

_LIGHT = {
    "bg": "#F3F3F3",
    "bg_panel": "#FAFAFA",
    "card": "#FFFFFF",
    "inset": "#F7F7F7",
    "line": "#E5E5E5",
    "line_strong": "#D1D1D1",
    "ink": "#1B1B1B",
    "ink_dim": "#5C5C5C",
    "ink_faint": "#8A8A8A",
    "accent": "#0F6CBD",
    "accent_hi": "#115EA3",
    "accent_deep": "#0B5A9E",
    "accent_soft": "rgba(15,108,189,0.10)",
    "ok": "#107C10",
    "ok_soft": "rgba(16,124,16,0.08)",
    "info": "#0E7386",
    "info_soft": "rgba(14,115,134,0.08)",
    "warn": "#C50F1F",
    "warn_soft": "rgba(197,15,31,0.07)",
    "warn_ink": "#B26A00",
    "beta": "#5C2E91",
    "beta_soft": "rgba(92,46,145,0.08)",
    "seal_idle": "#B0ADA8",
    "seal_off": "#D0CDC7",
    "seg_skip": "#C8C6C4",
}

_DARK = {
    "bg": "#202020",
    "bg_panel": "#272727",
    "card": "#2B2B2B",
    "inset": "#1C1C1C",
    "line": "#3A3A3A",
    "line_strong": "#4A4A4A",
    "ink": "#F0F0F0",
    "ink_dim": "#B8B8B8",
    "ink_faint": "#7F7F7F",
    "accent": "#479EF5",
    "accent_hi": "#62ABF5",
    "accent_deep": "#2B7CD3",
    "accent_soft": "rgba(71,158,245,0.14)",
    "ok": "#54B054",
    "ok_soft": "rgba(84,176,84,0.12)",
    "info": "#58B7C7",
    "info_soft": "rgba(88,183,199,0.12)",
    "warn": "#F1707B",
    "warn_soft": "rgba(241,112,123,0.10)",
    "warn_ink": "#F0B23E",
    "beta": "#B39DDB",
    "beta_soft": "rgba(179,157,219,0.12)",
    "seal_idle": "#6B6B6B",
    "seal_off": "#4A4A4A",
    "seg_skip": "#5A5A5A",
}


def palette(dark: bool | None = None) -> dict[str, str]:
    """Return the active token palette (follows qfluentwidgets' theme)."""
    if dark is None:
        dark = isDarkTheme()
    return dict(_DARK if dark else _LIGHT)


def chip_qss(color: str, soft: str) -> str:
    """Badge chip style: tinted text, soft background, thin colored border."""
    return (
        f"color: {color};"
        f" background-color: {soft};"
        f" border: 1px solid {rgba(color, 0.38)};"
        " border-radius: 5px;"
        " padding: 1px 7px;"
        " font-size: 11px;"
        " font-weight: 700;"
    )


def rgba(hex_color: str, alpha: float) -> str:
    """'#RRGGBB' + alpha → 'rgba(r,g,b,a)' for QSS."""
    r, g, b = _hex_rgb(hex_color)
    return f"rgba({r},{g},{b},{alpha:.2f})"


def mix(base: str, tint: str, t: float) -> str:
    """Opaque blend of ``tint`` into ``base`` ('#RRGGBB').

    Qt QSS stacks no background layers, so the mockup's translucent accent
    wash over a card is baked as an opaque gradient stop instead.
    """
    r1, g1, b1 = _hex_rgb(base)
    r2, g2, b2 = _hex_rgb(tint)
    return "#{:02X}{:02X}{:02X}".format(
        round(r1 + (r2 - r1) * t),
        round(g1 + (g2 - g1) * t),
        round(b1 + (b2 - b1) * t),
    )


def _hex_rgb(color: str) -> tuple[int, int, int]:
    value = color.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def on_theme_changed(callback, owner) -> None:
    """Re-run ``callback`` on theme changes until ``owner`` is destroyed."""
    from qfluentwidgets import qconfig

    def _update(*_args):
        callback()

    def _disconnect(*_args):
        try:
            qconfig.themeChanged.disconnect(_update)
        except (RuntimeError, TypeError):
            pass

    qconfig.themeChanged.connect(_update)
    owner.destroyed.connect(_disconnect)
