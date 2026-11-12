"""Reusable Qt controls for the inspector editor."""

from __future__ import annotations

import copy

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu,
    QPushButton, QSizePolicy, QStyle, QStyledItemDelegate, QToolButton, QVBoxLayout, QWidget,
)

from .qt_theme import ACCENT, BORDER, MUTED, TEXT, dark_titlebar


class Section(QWidget):
    def __init__(self, title, expanded=True, add=False, menu=False, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        header = QFrame()
        header.setObjectName("sectionHeader")
        row = QHBoxLayout(header)
        row.setContentsMargins(0, 0, 5, 0)
        row.setSpacing(2)
        self.toggle = QToolButton()
        self.toggle.setObjectName("sectionToggle")
        self.toggle.setText(title)
        self.toggle.setCheckable(True)
        self.toggle.setChecked(expanded)
        self.toggle.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        row.addWidget(self.toggle, 1)
        self.add_button = None
        if add:
            self.add_button = QToolButton()
            self.add_button.setObjectName("iconButton")
            self.add_button.setText("＋")
            self.add_button.setToolTip("添加")
            row.addWidget(self.add_button)
        self.menu_button = None
        if menu:
            self.menu_button = QToolButton()
            self.menu_button.setObjectName("iconButton")
            self.menu_button.setText("⋯")
            self.menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            row.addWidget(self.menu_button)
        outer.addWidget(header)
        self.body = QFrame()
        self.body.setObjectName("sectionBody")
        self.content = QVBoxLayout(self.body)
        self.content.setContentsMargins(10, 7, 10, 8)
        self.content.setSpacing(6)
        outer.addWidget(self.body)
        self.body.setVisible(expanded)
        self.toggle.toggled.connect(self._toggle)

    def _toggle(self, checked):
        self.body.setVisible(checked)
        self.toggle.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)


class _AttributeDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        return QSize(200, 43)

    def paint(self, painter, option, index):
        data = index.data(Qt.ItemDataRole.UserRole) or {}
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(rect, QColor("#28444a"))
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(rect, QColor("#21343e"))
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawLine(rect.left() + 5, rect.bottom(), rect.right() - 5, rect.bottom())
        painter.setPen(QColor(MUTED))
        painter.drawText(QRect(rect.left() + 8, rect.top(), 23, rect.height()), Qt.AlignmentFlag.AlignCenter, "⋮⋮")
        muted = data.get("hidden", False)
        painter.setPen(QColor(MUTED if muted else TEXT))
        available = max(40, rect.width() // 3 - 25)
        name = painter.fontMetrics().elidedText(str(data.get("title", "")), Qt.TextElideMode.ElideRight, available)
        painter.drawText(QRect(rect.left() + 38, rect.top(), available, rect.height()), Qt.AlignmentFlag.AlignVCenter, name)
        value_x = rect.left() + max(135, rect.width() // 2)
        value_width = max(20, rect.right() - value_x - 112)
        value = painter.fontMetrics().elidedText(str(data.get("display", "—")), Qt.TextElideMode.ElideRight, value_width)
        painter.drawText(QRect(value_x, rect.top(), value_width, rect.height()), Qt.AlignmentFlag.AlignVCenter, value)
        badge = "隐藏" if muted else ("手填" if data.get("manual") else "自动")
        badge_rect = QRect(rect.right() - 95, rect.top() + 9, 52, rect.height() - 18)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#354852"))
        painter.drawRoundedRect(badge_rect, 5, 5)
        painter.setPen(QColor(MUTED if muted else TEXT))
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge)
        painter.setPen(QColor(TEXT))
        painter.drawText(QRect(rect.right() - 34, rect.top(), 27, rect.height()), Qt.AlignmentFlag.AlignCenter, "⋮")
        painter.restore()


class AttributeList(QListWidget):
    editRequested = Signal(int)
    toggleRequested = Signal(int)
    removeRequested = Signal(int)
    orderChanged = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("attributeList")
        self.setItemDelegate(_AttributeDelegate(self))
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragDropOverwriteMode(False)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)
        self.itemDoubleClicked.connect(lambda item: self.editRequested.emit(item.data(Qt.ItemDataRole.UserRole)["index"]))

    def set_rows(self, rows):
        self.clear()
        for row in rows:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, row)
            item.setSizeHint(QSize(200, 43))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsDropEnabled)
            self.addItem(item)
        self.setFixedHeight(max(4, len(rows) * 43 + 2))

    def _moved(self, *_args):
        self.orderChanged.emit([self.item(index).data(Qt.ItemDataRole.UserRole)["index"] for index in range(self.count())])

    def dropEvent(self, event):
        super().dropEvent(event)
        if event.isAccepted():
            self._moved()

    def mouseReleaseEvent(self, event):
        item = self.itemAt(event.position().toPoint())
        super().mouseReleaseEvent(event)
        if item and event.button() == Qt.MouseButton.LeftButton:
            if event.position().x() >= self.viewport().width() - 40:
                self._menu(event.position().toPoint())

    def _menu(self, point):
        item = self.itemAt(point)
        if item is None:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        index = data["index"]
        menu = QMenu(self)
        edit = menu.addAction("编辑")
        toggle = menu.addAction("显示" if data.get("hidden") else "隐藏")
        remove = menu.addAction("删除")
        chosen = menu.exec(self.viewport().mapToGlobal(point))
        if chosen == edit:
            self.editRequested.emit(index)
        elif chosen == toggle:
            self.toggleRequested.emit(index)
        elif chosen == remove:
            self.removeRequested.emit(index)


class AttributeDialog(QDialog):
    def __init__(self, row, sources, manual=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("属性")
        self.setMinimumWidth(480)
        self.original = copy.deepcopy(row)
        self.manual = manual
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(16)
        title = QLabel("属性")
        title.setObjectName("paneTitle")
        layout.addWidget(title)
        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.name = QLineEdit(str(row.get("title", "")))
        form.addRow("显示名", self.name)
        self.source = QComboBox()
        self.source.setEditable(True)
        for item in sources:
            if isinstance(item, tuple):
                source, label = item
            else:
                source, label = str(item), str(item)
            if source and self.source.findText(str(source)) < 0:
                self.source.addItem(str(source), str(label))
        self.source.setCurrentText(str(row.get("source", "") or ""))
        self.source.activated.connect(self._source_selected)
        form.addRow("原属性名", self.source)
        self.custom = QCheckBox("手填值")
        self.custom.setChecked(manual)
        self.value = QLineEdit(str(row.get("value", "")) if manual else "")
        self.value.setEnabled(manual)
        self.custom.toggled.connect(self.value.setEnabled)
        form.addRow(self.custom, self.value)
        self.unit = QLineEdit(str(row.get("unit", "") or ""))
        form.addRow("单位", self.unit)
        self.group = QComboBox()
        self.group.addItem("攻击", "attack")
        self.group.addItem("常规", "regular")
        self.group.setCurrentIndex(0 if row.get("group") == "attack" else 1)
        form.addRow("区域", self.group)
        self.hidden = QCheckBox("隐藏此属性")
        self.hidden.setChecked(bool(row.get("hidden", False)))
        form.addRow("", self.hidden)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("确定")
        buttons.button(QDialogButtonBox.StandardButton.Ok).setObjectName("primary")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        dark_titlebar(self)

    def _source_selected(self, _index):
        if not self.name.text():
            self.name.setText(self.source.currentData() or self.source.currentText())

    def result_row(self):
        item = copy.deepcopy(self.original)
        item.update({"title": self.name.text(), "source": self.source.currentText(),
                     "unit": self.unit.text(), "group": self.group.currentData(), "hidden": self.hidden.isChecked()})
        item.pop("origin", None)
        item.pop("automatic", None)
        if self.custom.isChecked():
            old = self.original.get("value", "")
            if not self.manual or self.value.text() != str(old):
                item["value"] = self.value.text()
        else:
            item.pop("value", None)
        return item


class ChoiceDialog(QDialog):
    def __init__(self, title, choices, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(520, 500)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        heading = QLabel(title)
        heading.setObjectName("paneTitle")
        layout.addWidget(heading)
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索")
        layout.addWidget(self.search)
        self.list = QListWidget()
        self.list.setObjectName("choices")
        for key, name in choices:
            item = QListWidgetItem(name or key)
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setToolTip(key)
            self.list.addItem(item)
        layout.addWidget(self.list, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("选择")
        buttons.button(QDialogButtonBox.StandardButton.Ok).setObjectName("primary")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.search.textChanged.connect(self._filter)
        self.list.itemDoubleClicked.connect(lambda _item: self._accept())
        if self.list.count():
            self.list.setCurrentRow(0)
        dark_titlebar(self)

    def _filter(self, text):
        needle = text.casefold().strip()
        first = None
        for index in range(self.list.count()):
            item = self.list.item(index)
            shown = needle in (item.text() + " " + str(item.data(Qt.ItemDataRole.UserRole))).casefold()
            item.setHidden(not shown)
            if shown and first is None:
                first = item
        if first is not None:
            self.list.setCurrentItem(first)

    def _accept(self):
        if self.list.currentItem() is not None and not self.list.currentItem().isHidden():
            self.accept()

    def selected(self):
        item = self.list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None


class PreviewCard(QFrame):
    clicked = Signal(object)

    def __init__(self, title, kind, key, selected=False, summary="", description="", metrics=(), parent=None):
        super().__init__(parent)
        self.key = key
        self.setObjectName("entryCard" if kind == "entry" else "driveCard")
        self.setProperty("selected", selected)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(9)
        line = QHBoxLayout()
        marker = QLabel("▤" if kind == "entry" else "▷")
        marker.setStyleSheet(f"color: {ACCENT}; font-size: 20px;")
        line.addWidget(marker)
        label = QLabel(title)
        label.setObjectName("cardTitle")
        label.setWordWrap(True)
        line.addWidget(label, 1)
        if summary:
            value = QLabel(summary)
            value.setObjectName("muted")
            line.addWidget(value)
        layout.addLayout(line)
        if metrics:
            row = QHBoxLayout()
            row.setSpacing(22)
            for name, value in list(metrics)[:4]:
                metric = QVBoxLayout()
                caption = QLabel(str(name))
                caption.setObjectName("muted")
                number = QLabel(str(value))
                number.setStyleSheet("font-weight: 700; font-size: 16px;")
                metric.addWidget(caption)
                metric.addWidget(number)
                row.addLayout(metric)
            row.addStretch(1)
            layout.addLayout(row)
        if description:
            line = QLabel(description)
            line.setWordWrap(True)
            layout.addWidget(line)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(self.key)
        super().mouseReleaseEvent(event)
