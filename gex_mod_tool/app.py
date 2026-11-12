"""Native desktop editor for the G-EX inspector configuration."""

from __future__ import annotations

import argparse
import copy
import tkinter as tk
from tkinter import ttk
import uuid

from . import theme
from . import theme as messagebox
from .model import Project, last_project, nearby_game_directory, remember_project


ATTRIBUTE_SOURCES = (
    "基础威力", "DP伤害", "击穿DP伤害", "驱动暴击率", "射速", "单枚基础威力",
    "最大飞行距离", "爆炸半径", "贯穿", "着地引信", "每次装填", "装填间隔",
    "过热恢复", "修复时间", "重量",
)
ATTRIBUTE_LABELS = {
    "基础威力": "威力", "单枚基础威力": "威力", "DP伤害": "冲击力",
    "最大飞行距离": "射程", "爆炸半径": "范围",
}


def _display_name(key, name):
    return f"{name}  [{key}]" if name and name != key else key


def _read_text(widget):
    return widget.get("1.0", "end-1c")


def _set_text(widget, value, enabled=True):
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", value if isinstance(value, str) else "")
    widget.configure(state="normal" if enabled else "disabled")


def _description_text(value):
    return value if isinstance(value, str) else ""


class Picker(ttk.Frame):
    """Filterable picker whose values retain their actual definition IDs."""

    def __init__(self, master, on_select=None, search_width=13, **kwargs):
        super().__init__(master, **kwargs)
        self._pairs = []
        self._labels = {}
        self.search = tk.StringVar()
        self.value = tk.StringVar()
        ttk.Label(self, text="筛选").grid(row=0, column=0, padx=(0, 4))
        ttk.Entry(self, textvariable=self.search, width=search_width).grid(row=0, column=1, sticky="ew", padx=(0, 5))
        self.combo = ttk.Combobox(self, textvariable=self.value, state="readonly", width=34)
        self.combo.grid(row=0, column=2, sticky="ew")
        self.columnconfigure(2, weight=1)
        self.search.trace_add("write", lambda *_: self._filter())
        if on_select:
            self.combo.bind("<<ComboboxSelected>>", lambda _event: on_select(self.selected()))

    def set_choices(self, pairs):
        self._pairs = sorted(((str(key), _display_name(str(key), name)) for key, name in pairs),
                             key=lambda pair: (pair[1].casefold(), pair[0]))
        self._labels = {label: key for key, label in self._pairs}
        self._filter()

    def _filter(self):
        needle = self.search.get().casefold().strip()
        self.combo.configure(values=[label for key, label in self._pairs if needle in label.casefold()])

    def selected(self):
        return self._labels.get(self.value.get())

    def clear(self):
        self.search.set("")
        self.value.set("")

    def select(self, key):
        self.search.set("")
        self.value.set(next((label for item_key, label in self._pairs if item_key == key), ""))


class AttributeDialog(tk.Toplevel):
    def __init__(self, parent, initial):
        super().__init__(parent)
        self.configure(background=theme.BACKGROUND)
        self.title("属性")
        self.transient(parent.winfo_toplevel())
        self.resizable(False, False)
        self.result = None
        self.initial = copy.deepcopy(initial)
        self.vars = {key: tk.StringVar(value=str(initial.get(key, "") or ""))
                     for key in ("title", "source", "unit")}
        original_value = initial.get("value", "")
        self.value = tk.StringVar(value=str(original_value) if original_value is not None else "")
        self.has_value = tk.BooleanVar(value="value" in initial)
        self.group = tk.StringVar(value="攻击" if initial.get("group") == "attack" else "常规")
        self.hidden = tk.BooleanVar(value=bool(initial.get("hidden", False)))
        body = ttk.Frame(self, padding=20)
        body.grid(sticky="nsew")
        body.columnconfigure(1, weight=1)
        ttk.Label(body, text="显示名").grid(row=0, column=0, sticky="w", pady=4, padx=(0, 12))
        ttk.Entry(body, textvariable=self.vars["title"], width=45).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Label(body, text="原属性名").grid(row=1, column=0, sticky="w", pady=4, padx=(0, 12))
        self.source_combo = ttk.Combobox(body, textvariable=self.vars["source"], values=ATTRIBUTE_SOURCES, width=43)
        self.source_combo.grid(row=1, column=1, sticky="ew", pady=4)
        self.source_combo.bind("<KeyRelease>", self._filter_sources)
        self.source_combo.bind("<<ComboboxSelected>>", self._selected_source)
        ttk.Checkbutton(body, text="手填值", variable=self.has_value, command=self._value_state).grid(
            row=2, column=0, sticky="w", pady=4)
        self.value_entry = ttk.Entry(body, textvariable=self.value, width=45)
        self.value_entry.grid(row=2, column=1, sticky="ew", pady=4)
        ttk.Label(body, text="单位").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Entry(body, textvariable=self.vars["unit"], width=45).grid(row=3, column=1, sticky="ew", pady=4)
        ttk.Label(body, text="区域").grid(row=4, column=0, sticky="w", pady=4)
        ttk.Combobox(body, textvariable=self.group, values=("攻击", "常规"), state="readonly", width=12).grid(
            row=4, column=1, sticky="w", pady=4)
        ttk.Checkbutton(body, text="隐藏此属性", variable=self.hidden).grid(row=5, column=1, sticky="w", pady=4)
        buttons = ttk.Frame(body)
        buttons.grid(row=6, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="取消", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="确定", command=self._accept, style="Accent.TButton").pack(side="right", padx=6)
        self._value_state()
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _event: self.destroy())
        theme.apply_window(self)
        self.wait_visibility()
        self.grab_set()
        self.focus_set()

    def _value_state(self):
        self.value_entry.configure(state="normal" if self.has_value.get() else "disabled")

    def _filter_sources(self, _event):
        value = self.vars["source"].get().casefold().strip()
        self.source_combo.configure(values=[source for source in ATTRIBUTE_SOURCES if value in source.casefold()])

    def _selected_source(self, _event):
        source = self.vars["source"].get()
        if not self.vars["title"].get():
            self.vars["title"].set(ATTRIBUTE_LABELS.get(source, source))

    def _accept(self):
        item = copy.deepcopy(self.initial)
        for key, variable in self.vars.items():
            current = variable.get()
            previous = str(self.initial.get(key, "") or "")
            if current != previous:
                item[key] = current
        group = "attack" if self.group.get() == "攻击" else "regular"
        if group != self.initial.get("group", "regular"):
            item["group"] = group
        if self.hidden.get() != bool(self.initial.get("hidden", False)):
            item["hidden"] = self.hidden.get()
        if self.has_value.get():
            old_value = self.initial.get("value", "")
            old_text = str(old_value) if old_value is not None else ""
            if "value" not in self.initial or self.value.get() != old_text:
                item["value"] = self.value.get()
        else:
            item.pop("value", None)
        self.result = item
        self.destroy()


class AttributeEditor(ttk.LabelFrame):
    def __init__(self, master, target, on_change, **kwargs):
        super().__init__(master, text="属性", padding=10, **kwargs)
        self.target = target
        self.on_change = on_change
        self.status = tk.StringVar(value="自动")
        toolbar = ttk.Frame(self)
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 5))
        ttk.Label(toolbar, textvariable=self.status, style="Muted.TLabel").pack(side="left", padx=(0, 14))
        for text, command in (("添加", self.add), ("编辑", self.edit), ("删除", self.remove),
                              ("上移", lambda: self.move(-1)), ("下移", lambda: self.move(1)),
                              ("清空", self.clear), ("恢复自动", self.auto)):
            ttk.Button(toolbar, text=text, command=command).pack(side="left", padx=(0, 4))
        columns = ("title", "source", "value", "unit", "group", "hidden")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="browse", height=5)
        for key, title, width in (("title", "显示名", 145), ("source", "原属性名", 155),
                                  ("value", "手填值", 100), ("unit", "单位", 65),
                                  ("group", "区域", 65), ("hidden", "隐藏", 55)):
            anchor = "e" if key == "value" else "center" if key in ("unit", "group", "hidden") else "w"
            self.tree.heading(key, text=title, anchor=anchor)
            self.tree.column(key, width=width, minwidth=45, anchor=anchor, stretch=key in ("title", "source", "value"))
        scroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.grid(row=1, column=0, sticky="nsew")
        scroll.grid(row=1, column=1, sticky="ns")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.tree.bind("<Double-1>", lambda _event: self.edit())

    def _get_target(self):
        target = self.target()
        if target is None:
            messagebox.showinfo("属性", "请先选择条目或驱动。", parent=self)
        return target

    def refresh(self, selected=None):
        self.tree.delete(*self.tree.get_children())
        target = self.target()
        if target is None:
            self.status.set("未选择")
            return
        if "attributes" not in target:
            self.status.set("自动")
            return
        rows = target.get("attributes")
        if not isinstance(rows, list):
            self.status.set("属性格式无效")
            return
        self.status.set(f"自定义（{len(rows)} 项）")
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            values = (row.get("title", ""), row.get("source", ""), row.get("value", ""),
                      row.get("unit", ""), "攻击" if row.get("group") == "attack" else "常规",
                      "是" if row.get("hidden") else "否")
            self.tree.insert("", "end", iid=str(index), values=values)
        if selected is not None and self.tree.exists(str(selected)):
            self.tree.selection_set(str(selected))
            self.tree.see(str(selected))

    def _selected(self):
        selected = self.tree.selection()
        return int(selected[0]) if selected else None

    def _finish(self, index=None):
        self.on_change()
        self.refresh(index)

    def add(self):
        target = self._get_target()
        if target is None:
            return
        dialog = AttributeDialog(self, {"title": "", "source": "", "unit": "", "group": "regular", "hidden": False})
        self.wait_window(dialog)
        if dialog.result is not None:
            rows = target.setdefault("attributes", [])
            rows.append(dialog.result)
            self._finish(len(rows) - 1)

    def edit(self):
        target = self._get_target()
        index = self._selected()
        if target is None or index is None:
            return
        rows = target.get("attributes", [])
        dialog = AttributeDialog(self, rows[index])
        self.wait_window(dialog)
        if dialog.result is not None:
            rows[index] = dialog.result
            self._finish(index)

    def remove(self):
        target = self._get_target()
        index = self._selected()
        if target is None or index is None:
            return
        rows = target["attributes"]
        rows.pop(index)
        self._finish(min(index, len(rows) - 1) if rows else None)

    def move(self, step):
        target = self._get_target()
        index = self._selected()
        if target is None or index is None:
            return
        rows = target["attributes"]
        new_index = index + step
        if 0 <= new_index < len(rows):
            rows[index], rows[new_index] = rows[new_index], rows[index]
            self._finish(new_index)

    def clear(self):
        target = self._get_target()
        if target is not None:
            target["attributes"] = []
            self._finish()

    def auto(self):
        target = self._get_target()
        if target is not None:
            target.pop("attributes", None)
            self._finish()


class BindingEditor(ttk.LabelFrame):
    def __init__(self, master, title, field, get_target, open_selection=None, **kwargs):
        super().__init__(master, text=title, padding=10, **kwargs)
        self.field = field
        self.get_target = get_target
        self.open_selection = open_selection
        self.names = {}
        self.picker = Picker(self, search_width=9)
        self.picker.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 5))
        ttk.Button(self, text="加入", command=self.add).grid(row=0, column=2, padx=(5, 0))
        self.list = tk.Listbox(self, height=4, exportselection=False, activestyle="none")
        self.list.grid(row=1, column=0, columnspan=2, sticky="nsew")
        scroll = ttk.Scrollbar(self, orient="vertical", command=self.list.yview)
        scroll.grid(row=1, column=2, sticky="nsw")
        self.list.configure(yscrollcommand=scroll.set)
        controls = ttk.Frame(self)
        controls.grid(row=2, column=0, columnspan=3, sticky="w", pady=(5, 0))
        for text, command in (("移除", self.remove), ("上移", lambda: self.move(-1)), ("下移", lambda: self.move(1))):
            ttk.Button(controls, text=text, command=command).pack(side="left", padx=(0, 4))
        if open_selection is not None:
            ttk.Button(controls, text="详情", command=self.open_detail).pack(side="left", padx=(0, 4))
            self.list.bind("<Double-1>", lambda _event: self.open_detail())
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

    def set_choices(self, pairs):
        self.names = dict(pairs)
        self.picker.clear()
        self.picker.set_choices(self.names.items())
        self.refresh()

    def refresh(self, index=None):
        self.list.delete(0, "end")
        target = self.get_target()
        values = target.get(self.field, []) if target is not None else []
        if not isinstance(values, list):
            return
        for key in values:
            self.list.insert("end", _display_name(key, self.names.get(key, key)))
        if index is not None and 0 <= index < len(values):
            self.list.selection_set(index)
            self.list.see(index)

    def _target(self):
        target = self.get_target()
        if target is None:
            messagebox.showinfo("选择条目", "请先选择一个条目。", parent=self)
        return target

    def add(self):
        target = self._target()
        key = self.picker.selected()
        if target is None:
            return
        if key is None:
            messagebox.showinfo("选择项目", "请先从列表中选择要加入的项目。", parent=self)
            return
        values = target.setdefault(self.field, [])
        if key not in values:
            values.append(key)
            self.refresh(len(values) - 1)

    def remove(self):
        target = self._target()
        selected = self.list.curselection()
        if target is None or not selected:
            return
        values = target[self.field]
        index = selected[0]
        values.pop(index)
        self.refresh(min(index, len(values) - 1) if values else None)

    def move(self, step):
        target = self._target()
        selected = self.list.curselection()
        if target is None or not selected:
            return
        values = target[self.field]
        index = selected[0]
        new_index = index + step
        if 0 <= new_index < len(values):
            values[index], values[new_index] = values[new_index], values[index]
            self.refresh(new_index)

    def open_detail(self):
        target = self._target()
        selected = self.list.curselection()
        if target is not None and selected:
            self.open_selection(target[self.field][selected[0]])


class PartEditor(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=14)
        self.app = app
        self.part_id = None
        self.entry = None
        self.entry_index = None
        self.initial_title = ""
        self.initial_description = ""
        self._refreshing = False
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)
        bar = ttk.Frame(self)
        bar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        bar.columnconfigure(1, weight=1)
        ttk.Label(bar, text="部件").grid(row=0, column=0, padx=(0, 8))
        self.part_picker = Picker(bar, on_select=self.select_part)
        self.part_picker.grid(row=0, column=1, sticky="ew")
        sidebar = ttk.LabelFrame(self, text="条目", padding=10)
        sidebar.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        sidebar.rowconfigure(0, weight=1)
        sidebar.columnconfigure(0, weight=1)
        self.entries = tk.Listbox(sidebar, width=25, exportselection=False, activestyle="none")
        self.entries.grid(row=0, column=0, columnspan=2, sticky="nsew")
        scroll = ttk.Scrollbar(sidebar, command=self.entries.yview)
        self.entries.configure(yscrollcommand=scroll.set)
        scroll.grid(row=0, column=2, sticky="ns")
        self.entries.bind("<<ListboxSelect>>", self._entry_selected)
        controls = ttk.Frame(sidebar)
        controls.grid(row=1, column=0, columnspan=3, sticky="w", pady=(7, 0))
        for text, command in (("添加", self.add_entry), ("删除", self.remove_entry),
                              ("↑", lambda: self.move_entry(-1)), ("↓", lambda: self.move_entry(1))):
            ttk.Button(controls, text=text, command=command, width=5).pack(side="left", padx=(0, 3))
        ttk.Button(sidebar, text="导入默认条目", command=self.import_defaults).grid(
            row=2, column=0, columnspan=3, sticky="ew", pady=(5, 0))
        detail = ttk.Frame(self)
        detail.grid(row=1, column=1, sticky="nsew")
        detail.columnconfigure(0, weight=1)
        detail.rowconfigure(3, weight=1)
        form = ttk.Frame(detail)
        form.grid(row=0, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text="名称").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 5))
        self.title_var = tk.StringVar()
        self.title_entry = ttk.Entry(form, textvariable=self.title_var)
        self.title_entry.grid(row=0, column=1, sticky="ew", pady=(0, 5))
        self.title_entry.bind("<FocusOut>", lambda _event: self.commit())
        self.id_text = tk.StringVar(value="")
        ttk.Label(form, textvariable=self.id_text, style="Muted.TLabel").grid(row=1, column=1, sticky="w", pady=(0, 5))
        ttk.Label(form, text="说明").grid(row=2, column=0, sticky="nw", padx=(0, 8))
        self.description = tk.Text(form, height=3, wrap="word", undo=True)
        self.description.grid(row=2, column=1, sticky="ew")
        lists = ttk.Frame(detail)
        lists.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        lists.columnconfigure(0, weight=1, uniform="binding")
        lists.columnconfigure(1, weight=1, uniform="binding")
        self.resources = BindingEditor(lists, "资源", "resources", lambda: self.entry)
        self.resources.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        self.drives = BindingEditor(lists, "驱动", "drives", lambda: self.entry, open_selection=self.app.open_drive)
        self.drives.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        self.attributes = AttributeEditor(detail, lambda: self.entry, lambda: None)
        self.attributes.grid(row=3, column=0, sticky="nsew", pady=(8, 0))
        self._show_entry(None, None)

    def load(self):
        self.part_id = None
        self.entry = None
        self.entry_index = None
        self.part_picker.clear()
        self.part_picker.set_choices((key, value["name"]) for key, value in self.app.project.parts.items())
        self.drives.set_choices(self.app.project.drives.items())
        self.resources.set_choices([])
        self._refresh_entries()
        self._show_entry(None, None)

    def _part_entries(self):
        if self.app.project is None or self.part_id is None:
            return []
        part = self.app.project.data["parts"].get(self.part_id, {})
        return part.get("entries", []) if isinstance(part, dict) else []

    def select_part(self, definition_id):
        self.commit()
        self.part_id = definition_id
        self.entry = None
        self.entry_index = None
        costs = self.app.project.parts.get(definition_id, {}).get("costs", [])
        self.resources.set_choices(costs)
        self._refresh_entries()
        self._show_entry(None, None)

    def _refresh_entries(self, selected=None):
        self._refreshing = True
        self.entries.delete(0, "end")
        for entry in self._part_entries():
            self.entries.insert("end", entry.get("title", "") if isinstance(entry, dict) else "（无效条目）")
        if selected is not None and 0 <= selected < self.entries.size():
            self.entries.selection_set(selected)
            self.entries.see(selected)
        self._refreshing = False

    def _entry_selected(self, _event=None):
        if self._refreshing:
            return
        selection = self.entries.curselection()
        if not selection:
            return
        index = selection[0]
        if self.entry_index == index:
            return
        self.commit()
        entries = self._part_entries()
        entry = entries[index] if 0 <= index < len(entries) and isinstance(entries[index], dict) else None
        self._show_entry(entry, index if entry is not None else None)

    def _show_entry(self, entry, index):
        self.entry = entry
        self.entry_index = index
        self.initial_title = _description_text(entry.get("title", "")) if entry else ""
        self.initial_description = _description_text(entry.get("description", "")) if entry else ""
        self.title_var.set(self.initial_title)
        self.title_entry.configure(state="normal" if entry is not None else "disabled")
        self.id_text.set(f"ID：{entry.get('id', '')}" if entry is not None else "")
        _set_text(self.description, self.initial_description, enabled=entry is not None)
        self.resources.refresh()
        self.drives.refresh()
        self.attributes.refresh()

    def commit(self):
        if self.entry is None:
            return
        title = self.title_var.get()
        description = _read_text(self.description)
        if title != self.initial_title:
            self.entry["title"] = title
            self.initial_title = title
            if self.entry_index is not None and self.entry_index < self.entries.size():
                selected = self.entries.curselection()
                self.entries.delete(self.entry_index)
                self.entries.insert(self.entry_index, title)
                self.entries.selection_clear(0, "end")
                for index in selected:
                    self.entries.selection_set(index)
        if description != self.initial_description:
            if description:
                self.entry["description"] = description
            else:
                self.entry.pop("description", None)
            self.initial_description = description

    def add_entry(self):
        if self.app.project is None or self.part_id is None:
            messagebox.showinfo("选择部件", "请先选择部件。", parent=self)
            return
        self.commit()
        part = self.app.project.data["parts"].setdefault(self.part_id, {"entries": []})
        entries = part.setdefault("entries", [])
        entry = {"id": "entry_" + uuid.uuid4().hex, "title": "新条目", "resources": [], "drives": []}
        entries.append(entry)
        index = len(entries) - 1
        self._refresh_entries(index)
        self._show_entry(entry, index)
        self.title_entry.focus_set()
        self.title_entry.select_range(0, "end")

    def import_defaults(self):
        if self.app.project is None or self.part_id is None:
            messagebox.showinfo("选择部件", "请先选择部件。", parent=self)
            return
        self.commit()
        new_entries, unresolved = self.app.project.default_entries(self.part_id)
        if new_entries:
            part = self.app.project.data["parts"].setdefault(self.part_id, {"entries": []})
            entries = part.setdefault("entries", [])
            first = len(entries)
            entries.extend(new_entries)
            self._refresh_entries(first)
            self._show_entry(entries[first], first)
        self.app.status.set(
            f"已导入 {len(new_entries)} 个默认条目" +
            (f"；{len(unresolved)} 个驱动引用无法从定义读取" if unresolved else ""))
        if not new_entries:
            messagebox.showinfo("导入默认条目", "没有可导入的新条目。", parent=self)

    def remove_entry(self):
        if self.entry is None or self.entry_index is None:
            return
        if not messagebox.askyesno("删除条目", "删除选中的条目？", parent=self):
            return
        entries = self._part_entries()
        index = self.entry_index
        entries.pop(index)
        self.entry = None
        next_index = min(index, len(entries) - 1) if entries else None
        self._refresh_entries(next_index)
        self._show_entry(entries[next_index] if next_index is not None else None, next_index)

    def move_entry(self, step):
        if self.entry is None or self.entry_index is None:
            return
        self.commit()
        entries = self._part_entries()
        index = self.entry_index
        new_index = index + step
        if 0 <= new_index < len(entries):
            entries[index], entries[new_index] = entries[new_index], entries[index]
            self.entry_index = new_index
            self._refresh_entries(new_index)


class DriveEditor(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=14)
        self.app = app
        self.drive_id = None
        self.drive = None
        self.initial_title = ""
        self.initial_description = ""
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        bar = ttk.Frame(self)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        bar.columnconfigure(1, weight=1)
        ttk.Label(bar, text="驱动").grid(row=0, column=0, padx=(0, 8))
        self.picker = Picker(bar, on_select=self.select_drive)
        self.picker.grid(row=0, column=1, sticky="ew")
        form = ttk.Frame(self)
        form.grid(row=1, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text="名称").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 6))
        self.title_var = tk.StringVar()
        self.title_entry = ttk.Entry(form, textvariable=self.title_var)
        self.title_entry.grid(row=0, column=1, sticky="ew", pady=(0, 6))
        ttk.Label(form, text="说明").grid(row=1, column=0, sticky="nw", padx=(0, 8))
        self.description = tk.Text(form, height=5, wrap="word", undo=True)
        self.description.grid(row=1, column=1, sticky="ew")
        self.attributes = AttributeEditor(self, lambda: self.drive, self._persist)
        self.attributes.grid(row=2, column=0, sticky="nsew", pady=(8, 0))
        self._show_drive(None)

    def load(self):
        self.drive_id = None
        self.drive = None
        self.picker.clear()
        self.picker.set_choices(self.app.project.drives.items())
        self._show_drive(None)

    def select_drive(self, definition_id):
        self.commit()
        self.drive_id = definition_id
        if definition_id is None:
            self._show_drive(None)
            return
        existing = self.app.project.data["drives"].get(definition_id)
        self._show_drive(existing if isinstance(existing, dict) else {})

    def _show_drive(self, drive):
        self.drive = drive
        self.initial_title = _description_text(drive.get("title", "")) if drive is not None else ""
        self.initial_description = _description_text(drive.get("description", "")) if drive is not None else ""
        self.title_var.set(self.initial_title)
        self.title_entry.configure(state="normal" if drive is not None else "disabled")
        _set_text(self.description, self.initial_description, enabled=drive is not None)
        self.attributes.refresh()

    def _persist(self):
        if self.drive_id is not None and self.drive is not None:
            all_drives = self.app.project.data["drives"]
            if self.drive or self.drive_id in all_drives:
                all_drives[self.drive_id] = self.drive

    def commit(self):
        if self.drive is None:
            return
        title = self.title_var.get()
        description = _read_text(self.description)
        if title != self.initial_title:
            if title:
                self.drive["title"] = title
            else:
                self.drive.pop("title", None)
            self.initial_title = title
        if description != self.initial_description:
            if description:
                self.drive["description"] = description
            else:
                self.drive.pop("description", None)
            self.initial_description = description
        self._persist()


class App(tk.Tk):
    def __init__(self, project_arg=None):
        theme.prepare_process()
        super().__init__()
        theme.apply(self)
        self.title("G-EX Mod Tool")
        width = max(1000, min(1380, self.winfo_screenwidth() - 80))
        height = max(700, min(880, self.winfo_screenheight() - 80))
        self.geometry(f"{width}x{height}")
        self.minsize(1000, 700)
        self.project = None
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        header = ttk.Frame(self, padding=(16, 16, 16, 12))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(2, weight=1)
        ttk.Label(header, text="G-EX MOD TOOL", style="Brand.TLabel").grid(row=0, column=0, padx=(0, 24))
        ttk.Label(header, text="游戏目录", style="Muted.TLabel").grid(row=0, column=1, padx=(0, 8))
        self.project_path = tk.StringVar()
        ttk.Entry(header, textvariable=self.project_path, state="readonly").grid(row=0, column=2, sticky="ew")
        ttk.Button(header, text="选择目录", command=self.choose_project).grid(row=0, column=3, padx=(8, 12))
        ttk.Button(header, text="保存", command=self.save, style="Accent.TButton").grid(row=0, column=4)
        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 8))
        self.parts = PartEditor(self.notebook, self)
        self.drives = DriveEditor(self.notebook, self)
        self.notebook.add(self.parts, text="部件条目")
        self.notebook.add(self.drives, text="驱动详情")
        self.notebook.bind("<<NotebookTabChanged>>", lambda _event: self.commit())
        ttk.Separator(self, orient="horizontal").grid(row=2, column=0, sticky="ew", padx=16)
        self.status = tk.StringVar(value="请选择游戏目录")
        ttk.Label(self, textvariable=self.status, anchor="w", padding=(16, 8), style="Muted.TLabel").grid(row=3, column=0, sticky="ew")
        self.bind("<Control-s>", self._save_shortcut)
        self.protocol("WM_DELETE_WINDOW", self.close)
        project = project_arg if project_arg is not None else nearby_game_directory() or last_project()
        if project:
            self.after_idle(lambda: self.open_project(project, notify=project_arg is not None))

    def commit(self):
        self.parts.commit()
        self.drives.commit()

    def _save_shortcut(self, _event):
        self.save()
        return "break"

    def open_drive(self, drive_id):
        self.commit()
        self.drives.picker.select(drive_id)
        self.drives.select_drive(drive_id)
        self.notebook.select(self.drives)

    def save(self):
        if self.project is None:
            messagebox.showinfo("保存", "请先选择游戏目录。", parent=self)
            return False
        self.commit()
        try:
            changed = self.project.save()
        except (OSError, TypeError, ValueError) as error:
            messagebox.showerror("保存失败", str(error), parent=self)
            return False
        self.status.set("已保存" if changed else "没有需要保存的更改")
        return True

    def _confirm_changes(self):
        if self.project is None:
            return True
        self.commit()
        if not self.project.changed():
            return True
        answer = messagebox.askyesnocancel("未保存的更改", "是否保存当前更改？", parent=self)
        if answer is None:
            return False
        return self.save() if answer else True

    def choose_project(self):
        if not self._confirm_changes():
            return
        path = theme.askdirectory(title="选择游戏目录", initialdir=self.project_path.get() or None, parent=self)
        if path:
            self.open_project(path)

    def open_project(self, path, notify=True):
        try:
            project = Project(path)
        except (OSError, UnicodeError, ValueError) as error:
            self.status.set("无法打开游戏目录")
            if notify:
                messagebox.showerror("无法打开游戏目录", str(error), parent=self)
            return False
        self.project = project
        self.project_path.set(str(project.root))
        self.parts.load()
        self.drives.load()
        try:
            remember_project(project.root)
        except OSError:
            pass
        self.status.set(f"已打开：{len(project.parts)} 个部件，{len(project.drives)} 个驱动" +
                        (f"；跳过 {project.skipped} 个无法读取的文件" if project.skipped else ""))
        return True

    def close(self):
        if self._confirm_changes():
            self.destroy()


def main():
    parser = argparse.ArgumentParser(description="G-EX Mod Tool")
    parser.add_argument("--project", help="游戏目录")
    args = parser.parse_args()
    App(args.project).mainloop()
