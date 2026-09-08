"""启动页（StartTab）窄宽度响应式重排与自适应优化。

1. StartCard：
   - 宽屏（视口足够容纳单行）时采用标准紧凑单行模式（70px 高），
     图标、标题/版本、状态条、三个操作按钮均在同一水平线上，完全消除高度错位与空白。
   - 窄屏（视口不足以容纳单行）时自适应平滑折行为紧凑双行模式，
     第一行放图标、标题与状态条，第二行右对齐容纳截图/刷新/启动按钮。
   - 状态条随视口收窄自动进行省略处理并附加完整提示 Tooltip。

2. 实时截图与控制栏（实时截图行）：
   - 实时截图框随窗口横向拉伸按 16:9 比例放大，直到高度顶格（结合当前视口高度动态求取上限）。
   - 截图框达到顶格高度上限后固定宽度与高度，剩余水平拉伸空间完全由右侧
     “开发工具”与“手动调整分辨率”两栏向右充分铺开。
   - 视口过窄（如窄于 560px）时截图行自适应平滑堆叠为上下排列。

3. 选择窗口/截图方式/交互方式列表以及 Debug 工具栏：
   - 列表横向策略支持 Ignored 收窄，Card 解除强制 minimumSize 约束。
   - 工具栏和顶栏按钮复用 WrapLayout 换行，防止撑死整页最小宽度。
"""

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import QBoxLayout, QHBoxLayout, QLayout, QSizePolicy, QVBoxLayout, QWidget

from src.ui.live_screenshot import install_start_tab_responsive
from src.ui.wrap_layout import WrapLayout

_QWIDGETSIZE_MAX = 16777215

# 实时截图行并排的最低舒适视口宽度：预览最小 240 + 侧栏约 230 + 页边距。
# 堆叠/恢复之间留 40px 滞回，避免竖滚动条出现/消失引起的来回抖动。
_LOWER_ROW_STACK_BELOW = 560
_LOWER_ROW_UNSTACK_ABOVE = 600


def _enable_height_for_width(widget):
    policy = widget.sizePolicy()
    policy.setHeightForWidth(True)
    widget.setSizePolicy(policy)


class StartCardResponsiveController(QObject):
    """管理 StartCard 在宽屏单行与窄屏折行之间的自适应切换。"""

    def __init__(self, card):
        super().__init__(card)
        self.card = card
        self.buttons = (card.capture_button, card.refresh_button, card.start_button)
        self.status_bar = card.status_bar
        self.icon_label = card.iconLabel
        self.header = card.hBoxLayout

        # 清空原卡片布局，准备自适应容器
        while self.header.count():
            item = self.header.takeAt(0)
            del item

        self.header.setContentsMargins(0, 0, 0, 0)
        self.header.setSpacing(0)

        for label in (card.titleLabel, card.contentLabel):
            policy = label.sizePolicy()
            policy.setHorizontalPolicy(QSizePolicy.Preferred)
            label.setSizePolicy(policy)

        # 标题与版本号放入专属容器，避免在布局间跨父级转移 QLayout
        self.title_widget = QWidget(card)
        self.title_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.title_layout = QVBoxLayout(self.title_widget)
        self.title_layout.setContentsMargins(0, 0, 0, 0)
        self.title_layout.setSpacing(2)
        self.title_layout.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.title_layout.addWidget(card.titleLabel)
        self.title_layout.addWidget(card.contentLabel)

        # 顶层容器
        self.root_widget = QWidget(card)
        self.root_layout = QVBoxLayout(self.root_widget)
        self.root_layout.setContentsMargins(16, 0, 20, 0)
        self.root_layout.setSpacing(4)

        # 第 1 行：图标 + 标题/版本号 + 状态条 + 伸缩空白（单行模式时三个按钮排在此行）
        self.row1_widget = QWidget(self.root_widget)
        self.row1_layout = QHBoxLayout(self.row1_widget)
        self.row1_layout.setContentsMargins(0, 0, 0, 0)
        self.row1_layout.setSpacing(16)
        self.row1_layout.setAlignment(Qt.AlignVCenter)
        self.row1_layout.addWidget(self.icon_label, 0, Qt.AlignVCenter)
        self.row1_layout.addWidget(self.title_widget, 0, Qt.AlignVCenter)
        self.row1_layout.addWidget(self.status_bar, 0, Qt.AlignVCenter)
        self.row1_layout.addStretch(1)

        # 第 2 行：窄屏折行模式时容纳右对齐的三个操作按钮（流式布局，保证超窄时不溢出）
        self.row2_widget = QWidget(self.root_widget)
        self.row2_layout = WrapLayout(self.row2_widget, alignment=Qt.AlignRight)
        self.row2_layout.setContentsMargins(0, 0, 0, 0)
        self.row2_layout.setSpacing(6)

        self.root_layout.addWidget(self.row1_widget)
        self.root_layout.addWidget(self.row2_widget)
        self.header.addWidget(self.root_widget, 1)

        _enable_height_for_width(self.root_widget)
        _enable_height_for_width(self.row2_widget)
        _enable_height_for_width(self.card)

        self.card_policy = card.sizePolicy()
        self.card_policy.setHorizontalPolicy(QSizePolicy.Expanding)
        self.card_policy.setVerticalPolicy(QSizePolicy.Preferred)
        self.card.setSizePolicy(self.card_policy)

        self.current_mode = None
        self._available_width = card.width()
        self.set_mode("single")

        # 状态条长文本动态省略
        self.original_set_title = self.status_bar.setTitle
        self.status_bar.setTitle = self._set_title
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self._refresh)
        self.status_bar.installEventFilter(self)
        self.card.installEventFilter(self)

    def eventFilter(self, watched, event):
        if event.type() in (
            QEvent.ShowToParent, QEvent.HideToParent, QEvent.LayoutRequest, QEvent.FontChange,
        ):
            self._refresh_timer.start(0)
        return False

    def _refresh(self):
        self.update_width(self._available_width)

    def _set_title(self, title):
        self.status_bar._bd2_full_title = title
        self._refresh()

    def _row_width(self, include_buttons):
        widgets = [self.icon_label, self.title_widget]
        if not self.status_bar.isHidden():
            widgets.append(self.status_bar)
        if include_buttons:
            widgets.extend(self.buttons)
        margins = self.root_layout.contentsMargins()
        width = margins.left() + margins.right()
        # 伸缩占位符也占一个布局槽，间距数量等于可见控件数量。
        width += self.row1_layout.spacing() * len(widgets)
        for widget in widgets:
            if widget is self.status_bar:
                full = getattr(widget, "_bd2_full_title", widget.title)
                width += widget.titleLabel.fontMetrics().horizontalAdvance(full) + 50
            else:
                width += max(widget.minimumWidth(), widget.sizeHint().width())
        return width

    def apply_status_elision(self, width):
        full = getattr(self.status_bar, "_bd2_full_title", self.status_bar.title)
        metrics = self.status_bar.titleLabel.fontMetrics()
        natural = metrics.horizontalAdvance(full) + 50
        reserve = self._row_width(self.current_mode == "single")
        if not self.status_bar.isHidden():
            reserve -= natural
        cap = max(50, width - reserve)
        if metrics.horizontalAdvance(full) + 50 <= cap:
            text = full
        else:
            text = metrics.elidedText(full, Qt.ElideRight, cap - 50)
        self.status_bar.setToolTip(text != full and full or "")
        if text == self.status_bar.titleLabel.text():
            return
        self.original_set_title(text)
        self.status_bar.updateGeometry()
        self.row1_widget.updateGeometry()
        self.root_widget.updateGeometry()
        self.card.updateGeometry()

    def set_mode(self, mode):
        if self.current_mode == mode:
            return
        self.current_mode = mode

        if mode == "single":
            self.row2_widget.hide()
            for b in self.buttons:
                self.row2_layout.removeWidget(b)
                self.row1_layout.addWidget(b, 0, Qt.AlignVCenter)
                b.show()
            self.card.setMinimumHeight(70)
            self.card.setMaximumHeight(70)
        else:
            for b in self.buttons:
                self.row1_layout.removeWidget(b)
                self.row2_layout.addWidget(b)
                b.show()
            self.row2_widget.show()
            self.card.setMinimumHeight(0)
            self.card.setMaximumHeight(_QWIDGETSIZE_MAX)
            self.card.adjustSize()

        self.row1_widget.updateGeometry()
        self.row2_widget.updateGeometry()
        self.root_widget.updateGeometry()
        self.card.updateGeometry()

    def update_width(self, width):
        self._available_width = max(1, width)
        required_w = self._row_width(include_buttons=True)

        if width >= required_w:
            self.set_mode("single")
        else:
            self.set_mode("double")

        self.apply_status_elision(width)


def _shrink_selector_row(start_tab):
    for attr in ("device_list", "capture_list", "interaction_list"):
        widget = getattr(start_tab, attr, None)
        if widget is None:
            continue
        policy = widget.sizePolicy()
        policy.setHorizontalPolicy(QSizePolicy.Ignored)
        widget.setSizePolicy(policy)
        widget.setMinimumWidth(0)

    for attr in ("device_container", "capture_container", "interaction_container"):
        container = getattr(start_tab, attr, None)
        if container is None:
            continue
        for layout in (
            container.layout(),
            getattr(container, "cardLayout", None),
            getattr(container, "topLayout", None),
        ):
            if layout is not None:
                layout.setSizeConstraint(QLayout.SetDefaultConstraint)
        container.setMinimumWidth(0)
        policy = container.sizePolicy()
        policy.setHorizontalPolicy(QSizePolicy.Ignored)
        container.setSizePolicy(policy)


class _NarrowLayoutFilter(QObject):
    """视口 resize 时的响应式联动调度。"""

    def __init__(self, start_tab, controller):
        super().__init__(start_tab)
        self._start_tab = start_tab
        self._controller = controller

    def eventFilter(self, _watched, event):
        if event.type() != QEvent.Resize:
            return False
        self.refresh()
        return False

    def refresh(self):
        viewport = self._start_tab.viewport()
        viewport_w = viewport.width()
        viewport_h = viewport.height()

        # 1. 顶栏根据宽度平滑切换单行/折行与状态省略
        margins = self._start_tab.vBoxLayout.contentsMargins()
        self._controller.update_width(viewport_w - margins.left() - margins.right())

        # 2. 截图行根据宽度决定并排还是堆叠
        lower_row = getattr(self._start_tab, "live_screenshot_row", None)
        layout = lower_row.layout() if lower_row is not None else None
        if layout is not None:
            direction = layout.direction()
            if direction != QBoxLayout.TopToBottom and viewport_w < _LOWER_ROW_STACK_BELOW:
                layout.setDirection(QBoxLayout.TopToBottom)
            elif direction != QBoxLayout.LeftToRight and viewport_w > _LOWER_ROW_UNSTACK_ABOVE:
                layout.setDirection(QBoxLayout.LeftToRight)
            layout.setStretch(1, 0 if layout.direction() == QBoxLayout.TopToBottom else 1)

        # 3. 动态计算实时截图框的最大允许高度与宽度，使其随窗口高度顶格放大，多余宽度交给右侧侧栏
        live_card = getattr(self._start_tab, "live_screenshot_card", None)
        if live_card is not None and layout is not None:
            if layout.direction() == QBoxLayout.TopToBottom:
                live_card.setMaximumWidth(_QWIDGETSIZE_MAX)
            else:
                # 顶部占位高度（StartCard + 列表栏 + 外间距边距）约 440px
                start_card = getattr(self._start_tab, "start_card", None)
                selector = getattr(self._start_tab, "selector_widget", None)
                top_h = (start_card.height() if start_card else 70) + (
                    selector.height() if selector else 320
                ) + 50
                avail_h = max(240, viewport_h - top_h - 20)
                # 预览卡片头部文字及间距约占 84px，
                # 画面最高不超过 avail_h - 84，同时设置合理硬上限 450px
                max_preview_h = min(450, max(135, avail_h - 84))
                max_preview_w = int(max_preview_h * 16 / 9)
                live_card.setMaximumWidth(max_preview_w + 32)


def install_responsive_start_tab(start_tab) -> bool:
    card = getattr(start_tab, "start_card", None)
    if card is None or getattr(card, "_bd2_responsive_installed", False):
        return False

    install_start_tab_responsive(start_tab)
    controller = StartCardResponsiveController(card)
    _shrink_selector_row(start_tab)

    view = getattr(start_tab, "view", None)
    if view is not None:
        _enable_height_for_width(view)

    layout_filter = _NarrowLayoutFilter(start_tab, controller)
    start_tab.viewport().installEventFilter(layout_filter)
    layout_filter.refresh()

    card._bd2_responsive_installed = True
    return True
