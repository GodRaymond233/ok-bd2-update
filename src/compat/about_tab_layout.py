"""关于页窄窗口布局补丁。

上游 AboutTab 有两处固定最小宽度来源，窗口收窄时右侧内容被无声裁掉（水平滚动条
被 Tab 基类禁用）：

- 「相关项目」的 QGridLayout 固定两列，列宽由 ProjectCard 的自然宽度撑死；
- VersionCard 内 LinksBar 的一排链接按钮排满单行；
- ProjectCard 标题/链接标签的最小宽度等于全文宽度，卡片无法压缩。

两处容器都换成 WrapLayout（真 QLayout 版流式布局），标签换成 ShrinkableLabel：
宽度不足时折行/省略，而不是整体溢出。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from src.ui.shrinkable_label import ShrinkableLabel
from src.ui.wrap_layout import WrapLayout, wrap_container

PATCH_MARKER = "_ok_bd2_about_tab_layout_enabled"


def _drain_widgets(layout) -> list[QWidget]:
    widgets = []
    while layout.count():
        item = layout.takeAt(0)
        if item is not None and item.widget() is not None:
            widgets.append(item.widget())
    return widgets


def _replace_widget(host_layout, old_widget, new_widget, stretch=0) -> None:
    for index in range(host_layout.count()):
        item = host_layout.itemAt(index)
        if item is not None and item.widget() is old_widget:
            host_layout.removeItem(item)
            host_layout.insertWidget(index, new_widget, stretch)
            old_widget.deleteLater()
            return


def _shrink_setting_card_labels(card, *label_names) -> None:
    """把框架创建的文本标签原位换成 ShrinkableLabel（保留文本/字体/样式选择器）。"""
    vbox = getattr(card, "vBoxLayout", None)
    if vbox is None:
        return
    for name in label_names:
        old = getattr(card, name, None)
        if old is None:
            continue
        new = ShrinkableLabel(old.text(), card)
        new.setObjectName(old.objectName())
        new.setFont(old.font())
        new.setStyleSheet(old.styleSheet())
        new.setAlignment(old.alignment())
        new.setSizePolicy(old.sizePolicy())
        if old.maximumWidth() < 16777215:
            new.setMaximumWidth(old.maximumWidth())
        vbox.replaceWidget(old, new)
        old.deleteLater()
        setattr(card, name, new)


def _flow_links_bar(version_card) -> None:
    from ok.ui.qt.about.LinksBar import LinksBar

    links_bar = version_card.findChild(LinksBar)
    if links_bar is None:
        return
    widgets = _drain_widgets(links_bar.layout)
    if not widgets:
        return
    # LinksBar 是分享按钮的槽接收者，须保留其生命周期，只替换内部布局。
    old_layout_host = QWidget()
    old_layout_host.setLayout(links_bar.layout)
    old_layout_host.deleteLater()
    wrap = WrapLayout(links_bar, alignment=Qt.AlignmentFlag.AlignRight)
    wrap.setSpacing(8)
    for widget in widgets:
        wrap.addWidget(widget)
    links_bar.layout = wrap
    policy = links_bar.sizePolicy()
    policy.setHeightForWidth(True)
    links_bar.setSizePolicy(policy)
    version_card.hBoxLayout.setStretchFactor(links_bar, 1)
    # SettingCard 把高度钉在 70，折成两行时按钮会被上下裁掉，放行高度。
    version_card.setMinimumHeight(70)
    version_card.setMaximumHeight(16777215)


def _flow_project_grid(about_tab) -> None:

    group_card = getattr(about_tab, "group", None)
    grid_widget = getattr(group_card, "widget", None)
    if group_card is None or grid_widget is None:
        return
    cards = _drain_widgets(grid_widget.layout())
    if not cards:
        return
    for card in cards:
        _shrink_setting_card_labels(card, "titleLabel", "contentLabel")
    container, _wrap = wrap_container(cards, spacing=10)
    _replace_widget(group_card.topLayout, grid_widget, container, group_card.stretch)


def install_about_tab_layout() -> None:
    from ok.ui.qt.about.AboutTab import AboutTab

    if getattr(AboutTab, PATCH_MARKER, False):
        return

    original_init = AboutTab.__init__

    def responsive_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        _flow_links_bar(self.version_card)
        _flow_project_grid(self)

    AboutTab.__init__ = responsive_init
    setattr(AboutTab, PATCH_MARKER, True)
