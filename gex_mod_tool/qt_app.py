"""Three-column inspector editor for G-EX Mod Tool."""

from __future__ import annotations

import argparse
import copy
import sys
import uuid
from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher, QSignalBlocker, QTimer, Qt
from PySide6.QtGui import QKeySequence, QShortcut, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea,
    QSizePolicy, QSplitter, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from . import qt_theme
from .catalog import Catalog
from .model import Project, last_project, nearby_game_directory, remember_project
from .qt_widgets import AttributeDialog, AttributeList, ChoiceDialog, PreviewCard, Section


def _clear(layout):
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
        elif item.layout() is not None:
            _clear(item.layout())


def _scroll_area(content):
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setWidget(content)
    return scroll


def _value(row):
    value = row.get("value")
    if value is None or value == "":
        return "—"
    if isinstance(value, float):
        value = f"{value:g}"
    return f"{value} {row.get('unit', '')}".strip()


def _readable_drive_type(name):
    return {"Shooting": "射击", "Fighting": "动作", "Special": "特殊", "Main": "主武器"}.get(name, "驱动")


def _node_key(item):
    value = item.data(0, Qt.ItemDataRole.UserRole)
    return tuple(value) if isinstance(value, (tuple, list)) else None


class MainWindow(QMainWindow):
    def __init__(self, project_arg=None):
        super().__init__()
        self.setWindowTitle("G-EX Mod Tool")
        self.resize(1540, 960)
        self.setMinimumSize(1040, 690)
        self.project = None
        self.catalog = None
        self.selection = None
        self.draft = None
        self.base_draft = None
        self.base_display = {}
        self.preview_rows = []
        self.nodes = {}
        self.section_states = {}
        self.loading_tree = False
        self.setting_fields = False
        self.name_edit = None
        self.description_edit = None
        self._data_paths = set()
        self._style_paths = set()
        self.watcher = QFileSystemWatcher(self)
        self.watcher.fileChanged.connect(self._file_changed)
        self.watcher.directoryChanged.connect(self._file_changed)
        self.data_timer = QTimer(self)
        self.data_timer.setSingleShot(True)
        self.data_timer.setInterval(300)
        self.data_timer.timeout.connect(self._refresh_external)
        self.style_timer = QTimer(self)
        self.style_timer.setSingleShot(True)
        self.style_timer.setInterval(180)
        self.style_timer.timeout.connect(self._reload_style)
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(180)
        self.preview_timer.timeout.connect(self._render_preview)
        self._build_window()
        self.save_shortcut = QShortcut(QKeySequence(QKeySequence.StandardKey.Save), self)
        self.save_shortcut.activated.connect(self.save)
        self._rewatch()
        project = project_arg if project_arg is not None else nearby_game_directory() or last_project()
        if project:
            QTimer.singleShot(0, lambda: self.open_project(project, notify=project_arg is not None))

    def _build_window(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        top = QFrame()
        top.setObjectName("topBar")
        header = QHBoxLayout(top)
        header.setContentsMargins(24, 10, 20, 10)
        header.setSpacing(14)
        logo = QLabel()
        logo.setPixmap(qt_theme.make_icon().pixmap(32, 32))
        header.addWidget(logo)
        brand = QLabel("G-EX Mod Tool")
        brand.setObjectName("brand")
        header.addWidget(brand)
        self.directory_button = QPushButton("▱  选择游戏目录  ▾")
        self.directory_button.setObjectName("directory")
        self.directory_button.clicked.connect(self.choose_project)
        header.addWidget(self.directory_button)
        header.addStretch(1)
        self.dirty_label = QLabel("")
        self.dirty_label.setObjectName("saved")
        header.addWidget(self.dirty_label)
        self.save_button = QPushButton("保存修改")
        self.save_button.setObjectName("primary")
        self.save_button.clicked.connect(self.save)
        header.addWidget(self.save_button)
        layout.addWidget(top)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setContentsMargins(5, 6, 5, 6)
        layout.addWidget(self.splitter, 1)
        self._build_navigation()
        self._build_preview()
        self._build_details()
        self.splitter.setSizes([330, 680, 470])
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 3)
        self.splitter.setStretchFactor(2, 2)
        self.statusBar().showMessage("请选择游戏目录")
        self._show_empty_preview()
        self._show_empty_detail()
        self._update_dirty()

    def _build_navigation(self):
        panel = QFrame()
        panel.setObjectName("sidePanel")
        panel.setMinimumWidth(220)
        box = QVBoxLayout(panel)
        box.setContentsMargins(16, 16, 12, 14)
        box.setSpacing(12)
        heading = QHBoxLayout()
        title = QLabel("部件")
        title.setObjectName("paneTitle")
        heading.addWidget(title)
        heading.addStretch(1)
        self.add_entry_button = QToolButton()
        self.add_entry_button.setObjectName("iconButton")
        self.add_entry_button.setText("＋")
        self.add_entry_button.setToolTip("添加条目")
        self.add_entry_button.clicked.connect(self._add_entry)
        heading.addWidget(self.add_entry_button)
        box.addLayout(heading)
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索部件、条目或驱动")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter_tree)
        box.addWidget(self.search)
        self.tree = QTreeWidget()
        self.tree.setObjectName("navigation")
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(19)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._tree_menu)
        self.tree.currentItemChanged.connect(self._tree_changed)
        self.tree.itemExpanded.connect(self._expand_part)
        box.addWidget(self.tree, 1)
        self.splitter.addWidget(panel)

    def _build_preview(self):
        panel = QFrame()
        panel.setObjectName("previewPanel")
        panel.setMinimumWidth(320)
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        header = QFrame()
        header.setObjectName("previewHeader")
        header_box = QHBoxLayout(header)
        header_box.setContentsMargins(18, 14, 18, 14)
        self.breadcrumb = QLabel("部件目录")
        self.breadcrumb.setObjectName("muted")
        header_box.addWidget(self.breadcrumb)
        header_box.addStretch(1)
        outer.addWidget(header)
        content = QWidget()
        self.preview = QVBoxLayout(content)
        self.preview.setContentsMargins(20, 18, 20, 24)
        self.preview.setSpacing(10)
        self.preview_scroll = _scroll_area(content)
        outer.addWidget(self.preview_scroll, 1)
        self.splitter.addWidget(panel)

    def _build_details(self):
        panel = QFrame()
        panel.setObjectName("detailPanel")
        panel.setMinimumWidth(340)
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)
        content = QWidget()
        self.details = QVBoxLayout(content)
        self.details.setContentsMargins(18, 18, 18, 22)
        self.details.setSpacing(12)
        self.detail_scroll = _scroll_area(content)
        outer.addWidget(self.detail_scroll, 1)
        self.splitter.addWidget(panel)

    def _show_empty_preview(self):
        _clear(self.preview)
        title = QLabel("条目预览")
        title.setObjectName("paneTitle")
        self.preview.addWidget(title)
        text = QLabel("选择部件以查看条目")
        text.setObjectName("emptyState")
        self.preview.addWidget(text)
        self.preview.addStretch(1)
        self.breadcrumb.setText("部件目录")

    def _show_empty_detail(self):
        _clear(self.details)
        self.name_edit = None
        self.description_edit = None
        text = QLabel("选择条目或驱动")
        text.setObjectName("emptyState")
        self.details.addWidget(text)
        self.details.addStretch(1)

    def _update_dirty(self):
        pending = self.draft is not None and self.draft != self.base_draft
        dirty = pending or (self.project is not None and self.project.changed())
        self.dirty_label.setText("●  有未保存的修改" if dirty else ("已保存" if self.project else ""))
        self.dirty_label.setObjectName("dirty" if dirty else "saved")
        self.dirty_label.style().unpolish(self.dirty_label)
        self.dirty_label.style().polish(self.dirty_label)
        self.save_button.setEnabled(self.project is not None)
        self.add_entry_button.setEnabled(self.project is not None and self.selection is not None)

    def choose_project(self):
        if not self._confirm_changes():
            return
        initial = str(self.project.root) if self.project else str(Path.home())
        dialog = QFileDialog(self, "选择游戏目录", initial)
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setOption(QFileDialog.Option.ShowDirsOnly, True)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dialog.setLabelText(QFileDialog.DialogLabel.Accept, "选择")
        dialog.setLabelText(QFileDialog.DialogLabel.Reject, "取消")
        dialog.setLabelText(QFileDialog.DialogLabel.LookIn, "位置")
        dialog.setLabelText(QFileDialog.DialogLabel.FileName, "文件夹")
        qt_theme.dark_titlebar(dialog)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selectedFiles():
            self.open_project(dialog.selectedFiles()[0])

    def _message(self, title, text, error=False):
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(text)
        box.setIcon(QMessageBox.Icon.Critical if error else QMessageBox.Icon.Information)
        box.addButton("确定", QMessageBox.ButtonRole.AcceptRole)
        qt_theme.dark_titlebar(box)
        box.exec()

    def open_project(self, path, notify=True):
        try:
            project = Project(path)
            catalog = Catalog(project)
        except (OSError, UnicodeError, ValueError) as error:
            self.statusBar().showMessage("无法打开游戏目录")
            if notify:
                self._message("无法打开游戏目录", str(error), error=True)
            return False
        self.project, self.catalog = project, catalog
        self.selection = None
        self.draft = self.base_draft = None
        self.directory_button.setText(f"▱  {project.root.name}  ▾")
        self.directory_button.setToolTip(str(project.root))
        try:
            remember_project(project.root)
        except OSError:
            pass
        self._build_tree()
        self._show_empty_preview()
        self._show_empty_detail()
        self._update_dirty()
        self._rewatch()
        self.statusBar().showMessage("已连接游戏目录")
        return True

    def _entry(self, part_id, entry_id):
        if self.catalog is None:
            return None
        return next((item for item in self.catalog.entries(part_id)
                     if item["config"].get("id") == entry_id), None)

    def _drive_name(self, drive_id):
        override = self.project.data["drives"].get(drive_id, {})
        return override.get("title") or self.project.drives.get(drive_id, drive_id)

    def _drive_source(self, drive_id, field):
        document = self.project.drive_documents.get(drive_id, {})
        part = document.get("part", {}) if isinstance(document, dict) else {}
        info = part.get("partInfo", {}) if isinstance(part, dict) else {}
        value = info.get("displayName" if field == "title" else "description", "") if isinstance(info, dict) else ""
        return value if isinstance(value, str) and value else (drive_id if field == "title" else "")

    def _build_tree(self, preselect=None):
        expanded = {key[1] for key, item in self.nodes.items() if key[0] == "part" and item.isExpanded()}
        if preselect:
            expanded.add(preselect[1])
        expanded_entries = {key for key, item in self.nodes.items() if key[0] == "entry" and item.isExpanded()}
        if preselect and preselect[0] in ("entry", "drive"):
            expanded_entries.add(("entry", preselect[1], preselect[2]))
        self.loading_tree = True
        blocker = QSignalBlocker(self.tree)
        self.tree.clear()
        self.nodes = {}
        if self.catalog is not None:
            parts = sorted(self.catalog.parts(), key=lambda item: (item["title"].casefold(), item["id"]))
            for part in parts:
                key = ("part", part["id"])
                item = QTreeWidgetItem([part["title"]])
                item.setData(0, Qt.ItemDataRole.UserRole, key)
                item.setToolTip(0, part["id"])
                self.tree.addTopLevelItem(item)
                self.nodes[key] = item
                QTreeWidgetItem(item, [""])
                if part["id"] in expanded or self.search.text().strip():
                    self._fill_part(item)
                    item.setExpanded(part["id"] in expanded)
                    for child_index in range(item.childCount()):
                        child = item.child(child_index)
                        child.setExpanded(_node_key(child) in expanded_entries)
        if preselect in self.nodes:
            self.tree.setCurrentItem(self.nodes[preselect])
        self.loading_tree = False
        del blocker
        self._filter_tree(self.search.text())

    def _fill_part(self, item):
        key = _node_key(item)
        if not key or key[0] != "part" or item.data(0, int(Qt.ItemDataRole.UserRole) + 1):
            return
        item.takeChildren()
        part_id = key[1]
        for entry in self.catalog.entries(part_id):
            config = entry["config"]
            entry_id = config.get("id")
            if not isinstance(entry_id, str):
                continue
            entry_key = ("entry", part_id, entry_id)
            if self.selection == entry_key and self.draft is not None:
                config = self.draft
                title = self.field_values.get("title", entry["title"])
            else:
                title = entry["title"]
            child = QTreeWidgetItem([title or "未命名条目"])
            child.setData(0, Qt.ItemDataRole.UserRole, entry_key)
            child.setToolTip(0, entry_id)
            item.addChild(child)
            self.nodes[entry_key] = child
            for drive_id in config.get("drives", []):
                if not isinstance(drive_id, str):
                    continue
                drive_key = ("drive", part_id, entry_id, drive_id)
                drive = QTreeWidgetItem([self._drive_name(drive_id)])
                drive.setData(0, Qt.ItemDataRole.UserRole, drive_key)
                drive.setToolTip(0, drive_id)
                child.addChild(drive)
                self.nodes[drive_key] = drive
        item.setData(0, int(Qt.ItemDataRole.UserRole) + 1, True)

    def _expand_part(self, item):
        self._fill_part(item)

    def _filter_tree(self, text):
        if self.catalog is None:
            return
        needle = text.casefold().strip()
        for index in range(self.tree.topLevelItemCount()):
            part = self.tree.topLevelItem(index)
            if needle:
                self._fill_part(part)
            part_key = _node_key(part)
            part_match = not needle or needle in (part.text(0) + " " + part_key[1]).casefold()
            any_entry = False
            for child_index in range(part.childCount()):
                entry = part.child(child_index)
                entry_key = _node_key(entry)
                if not entry_key:
                    continue
                entry_match = part_match or needle in (entry.text(0) + " " + entry_key[2]).casefold()
                any_drive = False
                for drive_index in range(entry.childCount()):
                    drive = entry.child(drive_index)
                    drive_key = _node_key(drive)
                    matches = entry_match or needle in (drive.text(0) + " " + drive_key[3]).casefold()
                    drive.setHidden(not matches)
                    any_drive = any_drive or matches
                entry.setHidden(not (entry_match or any_drive))
                any_entry = any_entry or entry_match or any_drive
                if needle and any_drive:
                    entry.setExpanded(True)
            part.setHidden(not (part_match or any_entry))
            if needle and any_entry:
                part.setExpanded(True)

    def _tree_changed(self, item, _previous):
        if self.loading_tree or item is None:
            return
        key = _node_key(item)
        if not key:
            return
        changed = self._commit_current()
        if changed:
            self._build_tree(preselect=key)
        elif key[0] == "part":
            self._fill_part(item)
            item.setExpanded(True)
        self._present(key)

    def _select(self, key):
        if key not in self.nodes and len(key) > 1:
            part = self.nodes.get(("part", key[1]))
            if part is not None:
                self._fill_part(part)
                part.setExpanded(True)
        item = self.nodes.get(key)
        if item is None:
            return
        parent = item.parent()
        while parent is not None:
            parent.setExpanded(True)
            parent = parent.parent()
        self.tree.setCurrentItem(item)
        self.tree.scrollToItem(item)

    def _present(self, key):
        self.selection = key
        self.draft = self.base_draft = None
        self.base_display = {}
        self.field_values = {}
        if key[0] == "entry":
            entry = self._entry(key[1], key[2])
            if entry is not None:
                self.draft = copy.deepcopy(entry["config"])
                self.base_draft = copy.deepcopy(self.draft)
                self.base_display = {"title": entry["title"], "description": self.draft.get("description", "")}
        elif key[0] == "drive":
            drive = self.catalog.drive(key[3], key[1])
            self.draft = copy.deepcopy(self.project.data["drives"].get(key[3], {}))
            self.base_draft = copy.deepcopy(self.draft)
            self.base_display = {"title": drive.get("title", ""), "description": drive.get("description", "")}
        if self.draft is not None:
            self.field_values = {key: value if isinstance(value, str) else "" for key, value in self.base_display.items()}
        self._render_preview()
        self._render_details()
        self._update_dirty()
        self._rewatch()

    def _commit_current(self):
        if self.catalog is None or self.draft is None or self.draft == self.base_draft:
            return False
        key = self.selection
        if key[0] == "entry":
            self._store_entry(key[1], self.draft)
        elif key[0] == "drive":
            self.catalog.set_drive(key[3], self.draft)
        self.base_draft = copy.deepcopy(self.draft)
        self._update_dirty()
        return True

    def _store_entry(self, part_id, config):
        # Explicit entries are projected before remaining automatic ones. If an
        # automatic row is edited, materialize earlier rows too so it does not
        # jump ahead of its siblings merely because one field was changed.
        entries = self.catalog.entries(part_id)
        index = next((i for i, item in enumerate(entries) if item["config"].get("id") == config.get("id")), None)
        if index is not None and entries[index]["automatic"]:
            preceding = [copy.deepcopy(item["config"]) for item in entries[:index]]
            self.catalog.set_entries(part_id, preceding + [copy.deepcopy(config)])
        else:
            self.catalog.set_entry(part_id, config)

    def _set_field(self, field, text):
        if self.setting_fields or self.draft is None:
            return
        self.field_values[field] = text
        if text == self.base_display.get(field, ""):
            if field in self.base_draft:
                self.draft[field] = copy.deepcopy(self.base_draft[field])
            else:
                self.draft.pop(field, None)
        elif text or (field == "title" and self.selection[0] == "entry"):
            self.draft[field] = text
        else:
            self.draft.pop(field, None)
        if field == "title" and hasattr(self, "detail_heading"):
            self.detail_heading.setText(text or "未命名")
            if self.selection in self.nodes:
                self.nodes[self.selection].setText(0, text or "未命名")
        self.preview_timer.start()
        self._update_dirty()

    def _tree_menu(self, point):
        item = self.tree.itemAt(point)
        if item is None:
            return
        key = _node_key(item)
        if not key:
            return
        self._select(key)
        menu = QMenu(self)
        if key[0] == "part":
            add = menu.addAction("添加条目")
            if menu.exec(self.tree.viewport().mapToGlobal(point)) == add:
                self._add_entry()
        elif key[0] == "entry":
            add = menu.addAction("添加条目")
            up = menu.addAction("上移")
            down = menu.addAction("下移")
            entry = self._entry(key[1], key[2])
            reset = menu.addAction("恢复默认" if entry and not entry["automatic"] else "自动条目")
            reset.setEnabled(bool(entry and not entry["automatic"]))
            chosen = menu.exec(self.tree.viewport().mapToGlobal(point))
            if chosen == add:
                self._add_entry()
            elif chosen == up:
                self._move_entry(-1)
            elif chosen == down:
                self._move_entry(1)
            elif chosen == reset:
                self._remove_entry()
        elif key[0] == "drive":
            remove = menu.addAction("移除关联")
            if menu.exec(self.tree.viewport().mapToGlobal(point)) == remove:
                self._unlink_drive(key)

    def _add_entry(self):
        if self.selection is None or self.catalog is None:
            return
        part_id = self.selection[1]
        self._commit_current()
        config = {"id": "entry_" + uuid.uuid4().hex, "title": "新条目", "resources": [], "drives": []}
        self.catalog.set_entry(part_id, config)
        key = ("entry", part_id, config["id"])
        self._build_tree(preselect=key)
        self._present(key)
        if self.name_edit is not None:
            self.name_edit.setFocus()
            self.name_edit.selectAll()

    def _move_entry(self, step):
        if self.selection is None or self.selection[0] != "entry":
            return
        key = self.selection
        self._commit_current()
        entries = self.catalog.entries(key[1])
        index = next((i for i, item in enumerate(entries) if item["config"].get("id") == key[2]), None)
        if index is None or not 0 <= index + step < len(entries):
            return
        entries[index], entries[index + step] = entries[index + step], entries[index]
        self.catalog.set_entries(key[1], [item["config"] for item in entries])
        self._build_tree(preselect=key)
        self._present(key)

    def _remove_entry(self):
        if self.selection is None or self.selection[0] != "entry":
            return
        key = self.selection
        self._commit_current()
        entry = self._entry(key[1], key[2])
        if entry is None or entry["automatic"]:
            return
        box = QMessageBox(self)
        box.setWindowTitle("恢复默认")
        box.setText("移除此条目的配置并恢复默认显示？")
        accept = box.addButton("恢复默认", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        qt_theme.dark_titlebar(box)
        box.exec()
        if box.clickedButton() != accept:
            return
        part = self.project.data["parts"].get(key[1], {})
        configs = [item for item in part.get("entries", []) if isinstance(item, dict) and item.get("id") != key[2]]
        self.catalog.set_entries(key[1], configs)
        new_key = ("part", key[1])
        self._build_tree(preselect=new_key)
        self._present(new_key)

    def _unlink_drive(self, key):
        self._commit_current()
        entry = self._entry(key[1], key[2])
        if entry is None:
            return
        config = copy.deepcopy(entry["config"])
        config["drives"] = [item for item in config.get("drives", []) if item != key[3]]
        self._store_entry(key[1], config)
        selected = ("entry", key[1], key[2])
        self._build_tree(preselect=selected)
        self._present(selected)

    def _resource_summary(self, part, config):
        by_id = {cost["id"]: cost for cost in part.get("costs", [])}
        result = []
        for tag in config.get("resources", []):
            for resource in by_id.get(tag, {}).get("resources", []):
                if resource.get("value") is not None:
                    result.append(f"{resource.get('title', '')} {_value(resource)}".strip())
        return "  ·  ".join(result[:2])

    def _metrics(self, rows):
        return [(row.get("title", ""), _value(row)) for row in rows
                if isinstance(row, dict) and not row.get("hidden")][:4]

    def _render_preview(self):
        if self.selection is None or self.catalog is None:
            self._show_empty_preview()
            return
        key = self.selection
        part_id = key[1]
        part = self.catalog.part(part_id)
        entries = self.catalog.entries(part_id)
        _clear(self.preview)
        title = QLabel("条目预览")
        title.setObjectName("paneTitle")
        self.preview.addWidget(title)
        identity = QHBoxLayout()
        marker = QLabel("◇")
        marker.setStyleSheet(f"color: {qt_theme.ACCENT}; font-size: 30px;")
        identity.addWidget(marker)
        identity_text = QVBoxLayout()
        part_title = QLabel(part.get("title", part_id))
        part_title.setObjectName("objectTitle")
        part_title.setWordWrap(True)
        identity_text.addWidget(part_title)
        caption = QLabel("部件目录")
        caption.setObjectName("muted")
        identity_text.addWidget(caption)
        identity.addLayout(identity_text, 1)
        self.preview.addLayout(identity)
        self.preview.addSpacing(12)
        current_entry = self._entry(part_id, key[2]) if len(key) > 2 else None
        self.breadcrumb.setText(part.get("title", part_id) +
                                ("  /  " + current_entry["title"] if current_entry else ""))
        for entry in entries:
            config = copy.deepcopy(entry["config"])
            entry_id = config.get("id")
            entry_key = ("entry", part_id, entry_id)
            if key == entry_key and self.draft is not None:
                config = self.draft
                name = self.field_values.get("title", entry["title"])
            else:
                name = entry["title"]
            if not name:
                sources = {cost["id"]: cost["title"] for cost in part.get("costs", [])}
                name = next((sources[tag] for tag in config.get("resources", []) if tag in sources), "")
                if not name and config.get("drives"):
                    name = self._drive_name(config["drives"][0])
            rows = self.catalog.entry_attributes(part_id, config)
            parent = PreviewCard(name or "未命名条目", "entry", entry_key, selected=key == entry_key,
                                 summary=self._resource_summary(part, config),
                                 description=config.get("description", "") if key == entry_key else "",
                                 metrics=self._metrics(rows) if key == entry_key else ())
            parent.clicked.connect(self._select)
            self.preview.addWidget(parent)
            for drive_id in config.get("drives", []):
                if not isinstance(drive_id, str):
                    continue
                drive_key = ("drive", part_id, entry_id, drive_id)
                drive = self.catalog.drive(drive_id, part_id)
                selected = key == drive_key
                if selected and self.draft is not None:
                    drive_name = (self.field_values.get("title", "") if "title" in self.draft
                                  else self._drive_source(drive_id, "title"))
                    description = (self.field_values.get("description", "") if "description" in self.draft
                                   else self._drive_source(drive_id, "description"))
                    drive_rows = self.catalog.drive_attributes(drive_id, part_id, self.draft)
                else:
                    drive_name = drive["title"]
                    description = drive.get("description", "")
                    drive_rows = drive.get("attributes", [])
                line = QHBoxLayout()
                line.setContentsMargins(30, 0, 0, 0)
                card = PreviewCard(drive_name or "未命名驱动", "drive", drive_key, selected=selected,
                                   summary=_readable_drive_type(drive.get("type")),
                                   description=description if selected else "",
                                   metrics=self._metrics(drive_rows) if selected else ())
                card.clicked.connect(self._select)
                line.addWidget(card)
                self.preview.addLayout(line)
            self.preview.addSpacing(5)
        if not entries:
            empty = QLabel("此部件暂无条目")
            empty.setObjectName("emptyState")
            self.preview.addWidget(empty)
        self.preview.addStretch(1)

    def _projected_attributes(self):
        key = self.selection
        if key[0] == "entry":
            return self.catalog.entry_attributes(key[1], self.draft)
        return self.catalog.drive_attributes(key[3], key[1], self.draft)

    def _available_sources(self):
        key = self.selection
        if key[0] == "entry":
            return self.catalog.entry_sources(key[1], self.draft)
        return self.catalog.drive_sources(key[3], key[1])

    def _source_choices(self):
        defaults = [("基础威力", "威力"), ("DP伤害", "冲击力"), ("击穿DP伤害", "击穿冲击力"),
                    ("驱动暴击率", "暴击率"), ("射速", "射速"), ("单枚基础威力", "威力"),
                    ("最大飞行距离", "射程"), ("爆炸半径", "范围"), ("贯穿", "贯穿"),
                    ("着地引信", "着地引信"), ("每次装填", "每次装填"), ("装填间隔", "装填间隔"),
                    ("过热恢复", "过热恢复"), ("修复时间", "修复时间"), ("重量", "重量")]
        return [(row.get("source", ""), row.get("title", "")) for row in self._available_sources()] + defaults

    def _render_details(self):
        _clear(self.details)
        self.name_edit = None
        self.description_edit = None
        key = self.selection
        if key is None or self.draft is None or key[0] == "part":
            self._show_empty_detail()
            return
        name = self.field_values.get("title", "")
        self.detail_heading = QLabel(name or "未命名")
        self.detail_heading.setObjectName("objectTitle")
        self.detail_heading.setWordWrap(True)
        self.details.addWidget(self.detail_heading)
        sub = self._entry(key[1], key[2])
        subtitle = QLabel((sub["title"] + "  /  驱动") if key[0] == "drive" and sub else "条目")
        subtitle.setObjectName("muted")
        self.details.addWidget(subtitle)
        self.details.addSpacing(4)
        name_label = QLabel("名称")
        name_label.setObjectName("fieldLabel")
        self.details.addWidget(name_label)
        self.name_edit = QLineEdit(name)
        self.name_edit.textChanged.connect(lambda text: self._set_field("title", text))
        self.details.addWidget(self.name_edit)
        description = QLabel("说明")
        description.setObjectName("fieldLabel")
        self.details.addWidget(description)
        self.description_edit = QPlainTextEdit()
        self.description_edit.setPlainText(self.field_values.get("description", ""))
        self.description_edit.setMinimumHeight(76)
        self.description_edit.setMaximumHeight(130)
        self.description_edit.textChanged.connect(lambda: self._set_field("description", self.description_edit.toPlainText()))
        self.details.addWidget(self.description_edit)

        attributes = QFrame()
        attributes.setObjectName("sectionHeader")
        bar = QHBoxLayout(attributes)
        bar.setContentsMargins(11, 5, 5, 5)
        heading = QLabel("显示属性")
        heading.setObjectName("sectionTitle")
        bar.addWidget(heading)
        mode = QLabel("自定义" if "attributes" in self.draft else "自动")
        mode.setObjectName("muted")
        bar.addWidget(mode)
        bar.addStretch(1)
        add = QToolButton()
        add.setObjectName("iconButton")
        add.setText("＋")
        add.setToolTip("添加属性")
        add.clicked.connect(self._add_attribute)
        bar.addWidget(add)
        more = QToolButton()
        more.setObjectName("iconButton")
        more.setText("⋯")
        more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(more)
        menu.addAction("恢复自动属性", self._automatic_attributes)
        menu.addAction("清空显示属性", self._clear_attributes)
        more.setMenu(menu)
        bar.addWidget(more)
        self.details.addWidget(attributes)
        projected = self._projected_attributes()
        custom = self.draft.get("attributes") if isinstance(self.draft.get("attributes"), list) else None
        for group, label, expanded in (("attack", "攻击属性", True), ("regular", "常规属性", False)):
            section = Section(label, expanded=self.section_states.get(label, expanded))
            section.toggle.toggled.connect(lambda checked, name=label: self.section_states.__setitem__(name, checked))
            rows = []
            for index, row in enumerate(projected):
                if row.get("group", "regular") != group:
                    continue
                manual = bool(custom is not None and index < len(custom) and isinstance(custom[index], dict)
                              and "value" in custom[index])
                rows.append({"index": index, "title": row.get("title", ""), "display": _value(row),
                             "hidden": bool(row.get("hidden")), "manual": manual})
            listing = AttributeList()
            listing.set_rows(rows)
            listing.editRequested.connect(self._edit_attribute)
            listing.toggleRequested.connect(self._toggle_attribute)
            listing.removeRequested.connect(self._remove_attribute)
            listing.orderChanged.connect(lambda indices, which=group: self._order_attributes(which, indices))
            section.content.addWidget(listing)
            if not rows:
                empty = QLabel("无" if "attributes" in self.draft else "暂无自动属性")
                empty.setObjectName("muted")
                section.content.addWidget(empty)
            self.details.addWidget(section)
        if key[0] == "entry":
            self.details.addWidget(self._binding_section("关联资源", "resources", expanded=True))
            self.details.addWidget(self._binding_section("关联驱动", "drives", expanded=False))
        advanced = Section("高级设置", expanded=self.section_states.get("高级设置", False))
        advanced.toggle.toggled.connect(lambda checked: self.section_states.__setitem__("高级设置", checked))
        advanced.content.addWidget(QLabel("标识"))
        identifier = QLineEdit(key[2] if key[0] == "entry" else key[3])
        identifier.setReadOnly(True)
        advanced.content.addWidget(identifier)
        self.details.addWidget(advanced)
        self.details.addStretch(1)

    def _binding_section(self, title, field, expanded):
        section = Section(title, expanded=self.section_states.get(title, expanded), add=True)
        section.toggle.toggled.connect(lambda checked: self.section_states.__setitem__(title, checked))
        section.add_button.clicked.connect(lambda: self._add_binding(field))
        part = self.catalog.part(self.selection[1])
        names = {cost["id"]: cost["title"] for cost in part.get("costs", [])}
        if field == "drives":
            names = {item: self._drive_name(item) for item in part.get("drives", [])}
        values = self.draft.get(field, [])
        for index, key in enumerate(values if isinstance(values, list) else []):
            row = QHBoxLayout()
            label = QLabel(names.get(key, key))
            label.setWordWrap(True)
            label.setToolTip(key)
            row.addWidget(label, 1)
            for text, callback, tip in (("↑", lambda _checked=False, i=index: self._move_binding(field, i, -1), "上移"),
                                        ("↓", lambda _checked=False, i=index: self._move_binding(field, i, 1), "下移"),
                                        ("×", lambda _checked=False, i=index: self._remove_binding(field, i), "移除关联")):
                button = QToolButton()
                button.setObjectName("iconButton")
                button.setText(text)
                button.setToolTip(tip)
                button.clicked.connect(callback)
                row.addWidget(button)
            section.content.addLayout(row)
        if not values:
            label = QLabel("无")
            label.setObjectName("muted")
            section.content.addWidget(label)
        return section

    def _changed_details(self):
        self._update_dirty()
        self._build_tree(preselect=self.selection)
        self._render_preview()
        self._render_details()
        self._rewatch()

    def _custom_attributes(self):
        if "attributes" not in self.draft:
            self.draft["attributes"] = [
                {"title": row.get("title", ""), "source": row.get("source", ""),
                 "unit": row.get("unit", ""), "group": row.get("group", "regular"),
                 "hidden": bool(row.get("hidden", False))}
                for row in self._projected_attributes() if isinstance(row, dict)
            ]
        return self.draft["attributes"]

    def _add_attribute(self):
        row = {"title": "", "source": "", "unit": "", "group": "regular", "hidden": False}
        dialog = AttributeDialog(row, self._source_choices(), parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._custom_attributes().append(dialog.result_row())
            self._changed_details()

    def _edit_attribute(self, index):
        projected = self._projected_attributes()
        if not 0 <= index < len(projected):
            return
        custom = self.draft.get("attributes")
        if isinstance(custom, list) and index < len(custom) and isinstance(custom[index], dict):
            row = copy.deepcopy(custom[index])
            manual = "value" in row
        else:
            row = copy.deepcopy(projected[index])
            manual = False
        dialog = AttributeDialog(row, self._source_choices(), manual=manual, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            rows = self._custom_attributes()
            if index < len(rows):
                rows[index] = dialog.result_row()
                self._changed_details()

    def _toggle_attribute(self, index):
        rows = self._custom_attributes()
        if 0 <= index < len(rows):
            rows[index]["hidden"] = not bool(rows[index].get("hidden"))
            self._changed_details()

    def _remove_attribute(self, index):
        rows = self._custom_attributes()
        if 0 <= index < len(rows):
            rows.pop(index)
            self._changed_details()

    def _order_attributes(self, group, indices):
        projected = self._projected_attributes()
        positions = [index for index, row in enumerate(projected) if row.get("group", "regular") == group]
        if positions == indices:
            return
        rows = self._custom_attributes()
        if len(positions) == len(indices) and all(0 <= index < len(rows) for index in indices):
            ordered = [rows[index] for index in indices]
            for position, row in zip(positions, ordered):
                rows[position] = row
            self._changed_details()

    def _automatic_attributes(self):
        self.draft.pop("attributes", None)
        self._changed_details()

    def _clear_attributes(self):
        self.draft["attributes"] = []
        self._changed_details()

    def _add_binding(self, field):
        part = self.catalog.part(self.selection[1])
        used = self.draft.get(field, [])
        if field == "resources":
            choices = [(cost["id"], cost["title"]) for cost in part.get("costs", []) if cost["id"] not in used]
            title = "选择资源"
        else:
            choices = [(drive_id, self._drive_name(drive_id)) for drive_id in part.get("drives", []) if drive_id not in used]
            title = "选择驱动"
        if not choices:
            self._message(title, "没有可添加的项目。")
            return
        dialog = ChoiceDialog(title, choices, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected() is not None:
            self.draft.setdefault(field, []).append(dialog.selected())
            self._changed_details()

    def _remove_binding(self, field, index):
        values = self.draft.get(field, [])
        if 0 <= index < len(values):
            values.pop(index)
            self._changed_details()

    def _move_binding(self, field, index, step):
        values = self.draft.get(field, [])
        other = index + step
        if 0 <= index < len(values) and 0 <= other < len(values):
            values[index], values[other] = values[other], values[index]
            self._changed_details()

    def _rewatch(self):
        paths = set()
        if self.catalog is not None:
            paths.update(self.catalog.watch_paths())
        self._data_paths = {str(Path(path)) for path in paths}
        style_paths = set()
        for path in qt_theme.stylesheet_paths():
            if path.is_file():
                style_paths.add(str(path))
            parent = path.parent
            while not parent.exists() and parent != parent.parent:
                parent = parent.parent
            if parent.is_dir():
                style_paths.add(str(parent))
        self._style_paths = style_paths
        wanted = self._data_paths | self._style_paths
        existing = set(self.watcher.files()) | set(self.watcher.directories())
        obsolete = list(existing - wanted)
        missing = [path for path in wanted - existing if Path(path).exists()]
        if obsolete:
            self.watcher.removePaths(obsolete)
        if missing:
            self.watcher.addPaths(missing)

    def _file_changed(self, path):
        normalized = str(Path(path))
        if normalized in self._style_paths:
            self.style_timer.start()
        if normalized in self._data_paths:
            self.data_timer.start()

    def _reload_style(self):
        try:
            QApplication.instance().setStyleSheet(qt_theme.load_stylesheet())
        except (OSError, UnicodeError):
            self.statusBar().showMessage("界面样式暂时无法读取", 5000)
        self._rewatch()

    def _refresh_external(self):
        if self.catalog is None:
            return
        if QApplication.activeModalWidget() is not None:
            self.data_timer.start(700)
            return
        focused = QApplication.focusWidget()
        focus_name = focused is self.name_edit
        focus_description = focused is self.description_edit
        cursor_position = None
        cursor_anchor = None
        if focus_name and self.name_edit is not None:
            cursor_position = self.name_edit.cursorPosition()
        elif focus_description and self.description_edit is not None:
            cursor = self.description_edit.textCursor()
            cursor_position, cursor_anchor = cursor.position(), cursor.anchor()
        key = self.selection
        self._commit_current()
        try:
            result = self.catalog.refresh()
        except (OSError, UnicodeError, ValueError, TypeError) as error:
            self.statusBar().showMessage(f"内容暂时无法刷新：{error}", 7000)
            self._rewatch()
            return
        self._build_tree(preselect=key)
        if key is not None and key in self.nodes:
            self._present(key)
        elif key is not None and ("part", key[1]) in self.nodes:
            self._present(("part", key[1]))
        else:
            self.selection = None
            self.draft = self.base_draft = None
            self._show_empty_preview()
            self._show_empty_detail()
            self._update_dirty()
        if focus_name and self.name_edit is not None:
            self.name_edit.setFocus()
            self.name_edit.setCursorPosition(min(cursor_position, len(self.name_edit.text())))
        elif focus_description and self.description_edit is not None:
            self.description_edit.setFocus()
            cursor = self.description_edit.textCursor()
            limit = len(self.description_edit.toPlainText())
            cursor.setPosition(min(cursor_anchor, limit))
            cursor.setPosition(min(cursor_position, limit), QTextCursor.MoveMode.KeepAnchor)
            self.description_edit.setTextCursor(cursor)
        conflicts = result.get("conflicts", [])
        if conflicts:
            self.statusBar().setToolTip("\n".join(str(item) for item in conflicts))
            self.statusBar().showMessage("部分内容同时修改，已保留本地编辑", 9000)
        else:
            self.statusBar().setToolTip("")
            self.statusBar().showMessage("内容已刷新", 3500)
        self._update_dirty()
        self._rewatch()
    def save(self):
        if self.project is None:
            return False
        committed = self._commit_current()
        if committed and self.selection is not None:
            self._build_tree(preselect=self.selection)
            self._present(self.selection)
        try:
            changed = self.project.save()
        except (OSError, ValueError, TypeError) as error:
            self._message("保存失败", str(error), error=True)
            return False
        self.statusBar().showMessage("已保存" if changed else "没有需要保存的更改", 4000)
        self._update_dirty()
        self._rewatch()
        return True

    def _confirm_changes(self):
        if self.project is None:
            return True
        if self.draft == self.base_draft and not self.project.changed():
            return True
        box = QMessageBox(self)
        box.setWindowTitle("未保存的修改")
        box.setText("是否保存当前修改？")
        save = box.addButton("保存", QMessageBox.ButtonRole.AcceptRole)
        discard = box.addButton("不保存", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save)
        qt_theme.dark_titlebar(box)
        box.exec()
        if box.clickedButton() == save:
            return self.save()
        return box.clickedButton() == discard

    def closeEvent(self, event):
        if self._confirm_changes():
            event.accept()
        else:
            event.ignore()


def main():
    parser = argparse.ArgumentParser(description="G-EX Mod Tool")
    parser.add_argument("--project", help="游戏目录")
    args = parser.parse_args()
    application = QApplication.instance() or QApplication([sys.argv[0]])
    application.setApplicationName("G-EX Mod Tool")
    qt_theme.apply(application)
    window = MainWindow(args.project)
    qt_theme.dark_titlebar(window)
    window.show()
    return application.exec()
