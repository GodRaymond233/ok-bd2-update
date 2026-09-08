"""可被布局压缩的 QLabel：minimumSizeHint 归零，空间不足时省略号收尾。

不换行 QLabel 的 minimumSizeHint 等于全文宽度，会把宿主卡片/整页钉死在文本宽度上；
setMinimumWidth(0) 又会被 Qt 视为「未设置」而回退到 minimumSizeHint。这个子类把
minimumSizeHint 显式归零：空间够时按自然宽度显示全文，不够时收缩并省略号截断，
tooltip 始终保留全文。
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QLabel


class ShrinkableLabel(QLabel):
    def minimumSizeHint(self) -> QSize:
        hint = super().minimumSizeHint()
        return QSize(0, hint.height())

    def setText(self, text: str) -> None:
        super().setText(text)
        self.setToolTip(text)

    def paintEvent(self, event) -> None:
        full = self.text()
        metrics = self.fontMetrics()
        if not full or metrics.horizontalAdvance(full) <= self.width():
            super().paintEvent(event)
            return
        elided = metrics.elidedText(full, Qt.TextElideMode.ElideRight, self.width())
        painter = QPainter(self)
        self.style().drawItemText(
            painter,
            self.rect(),
            int(self.alignment()) | Qt.TextFlag.TextSingleLine,
            self.palette(),
            self.isEnabled(),
            elided,
        )
        painter.end()
