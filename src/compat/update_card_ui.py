from __future__ import annotations

# 「应用更新」卡片状态标签的宽度策略。标签按自然单行宽度定宽（短状态绝不折行），
# 超过单行上限的长文本（错误详情、双语指引）收敛到定宽并允许折行。
UPDATE_CARD_STATUS_WRAP_WIDTH = 260

# pyappify.get_version_list 要求启动器 PYAPPIFY_VERSION >= 1.2.2 才支持“检查更新”
# （pyappify/__init__.py 的 _is_supported_pyappify_version）；更老的启动器只会抛
# RuntimeError。提前拦截并给出下载重装指引，避免把英文异常直接甩给用户。
MIN_CHECK_UPDATES_LAUNCHER_VERSION = (1, 2, 2)

PATCH_MARKER = "_ok_bd2_update_card_ui_enabled"

# 状态标签左右内边距补偿，避免定宽后末字贴边。
_STATUS_HORIZONTAL_PADDING = 8


def parse_launcher_version(version) -> tuple[int, ...] | None:
    """解析启动器版本号为全数字元组；无法解析（如开发环境未注入）时返回 None。"""
    if not isinstance(version, str):
        return None
    parts = version.lstrip("v").split(".")
    if not parts or not all(part.isdigit() for part in parts):
        return None
    return tuple(int(part) for part in parts)


def launcher_supports_update_check(version) -> bool | None:
    """启动器是否支持检查更新；版本不可解析时返回 None（不拦截，交由上游处理）。"""
    parsed = parse_launcher_version(version)
    if parsed is None:
        return None
    return parsed >= MIN_CHECK_UPDATES_LAUNCHER_VERSION


def _too_old_message(version) -> str:
    return (
        f"启动器版本 {version} 过旧，无法检查更新；请点击「下载」重新安装最新版以升级启动器。"
        f"Launcher {version} is too old to check for updates; click Download to reinstall."
    )


def status_width_for_text(label, message: str) -> int:
    """状态标签的目标宽度：短文本自然单行，长文本收敛到折行宽度。"""
    if not message:
        return 0
    natural = label.fontMetrics().horizontalAdvance(message) + _STATUS_HORIZONTAL_PADDING
    return min(natural, UPDATE_CARD_STATUS_WRAP_WIDTH)


def _refit_status_label(card) -> None:
    width = status_width_for_text(card.status_label, card.status_label.text())
    card.status_label.setVisible(width > 0)
    card.status_label.setFixedWidth(width)


def _flow_controls_row(card) -> None:
    """把控件行换成 WrapLayout：窗口过窄时按钮折到下一行，而不是被右缘裁掉。"""
    from src.ui.wrap_layout import WrapLayout

    layout = card.layout()
    controls = card.controls_layout
    widgets = []
    for index in range(controls.count()):
        item = controls.itemAt(index)
        if item is not None and item.widget() is not None:
            widgets.append(item.widget())
    wrap = WrapLayout()
    wrap.setSpacing(8)
    layout.insertLayout(0, wrap)
    layout.removeItem(controls)
    for widget in widgets:
        wrap.addWidget(widget)
    controls.deleteLater()
    card.controls_wrap = wrap


def install_update_card_ui() -> None:
    from ok.ui.qt.about.UpdateCard import UpdateCard

    if getattr(UpdateCard, PATCH_MARKER, False):
        return

    original_init = UpdateCard.__init__
    original_check_for_updates = UpdateCard.check_for_updates
    original_set_status = UpdateCard._set_status

    def stable_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.status_label.setMinimumWidth(0)
        _flow_controls_row(self)
        _refit_status_label(self)

    def stable_check_for_updates(self):
        version = getattr(self.pyappify_module, "pyappify_version", None)
        if launcher_supports_update_check(version) is False:
            self._show_error(_too_old_message(version))
            return
        original_check_for_updates(self)

    def stable_set_status(self, message, error=False):
        original_set_status(self, message, error)
        _refit_status_label(self)

    UpdateCard.__init__ = stable_init
    UpdateCard.check_for_updates = stable_check_for_updates
    UpdateCard._set_status = stable_set_status
    setattr(UpdateCard, PATCH_MARKER, True)
