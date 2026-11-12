"""Visual theme and small application dialogs for the desktop editor."""

from __future__ import annotations

import os
from pathlib import Path
import string
import sys
import tkinter as tk
from tkinter import font as tkfont, ttk


BACKGROUND = "#121d2a"
SURFACE = "#182637"
FIELD = "#101a26"
FIELD_DISABLED = "#16212d"
BORDER = "#34485a"
TEXT = "#e5edf4"
MUTED = "#9badbc"
DISABLED = "#677b8d"
ACCENT = "#67c9d5"
ACCENT_BUTTON = "#287e90"
ACCENT_HOVER = "#3195a7"
SELECT = "#285e71"
ICON_RECTS = ((8, 7, 24, 10), (7, 9, 10, 23), (9, 22, 24, 25),
              (16, 15, 25, 18), (22, 16, 25, 23))


def prepare_process():
    """Enable DPI awareness for this process before creating any Tk window."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        user = ctypes.windll.user32
        if user.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except (AttributeError, OSError):
        pass
    try:
        import ctypes
        ctypes.windll.user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass


def apply_window(window):
    """Use the system's dark Windows title bar where it is available."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes
        window.update_idletasks()
        user = ctypes.WinDLL("user32", use_last_error=True)
        user.GetParent.argtypes = [wintypes.HWND]
        user.GetParent.restype = wintypes.HWND
        handle = user.GetParent(wintypes.HWND(window.winfo_id())) or window.winfo_id()
        dwm = ctypes.WinDLL("dwmapi", use_last_error=True)
        dwm.DwmSetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
        flag = ctypes.c_int(1)
        for attribute in (20, 19):
            if dwm.DwmSetWindowAttribute(handle, attribute, ctypes.byref(flag), ctypes.sizeof(flag)) == 0:
                break
    except (AttributeError, OSError, ValueError):
        pass


def apply(root):
    families = set(tkfont.families(root))
    family = next((name for name in ("Microsoft YaHei UI", "Microsoft YaHei", "Noto Sans CJK SC", "Segoe UI")
                   if name in families), "TkDefaultFont")
    if family != "TkDefaultFont":
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            tkfont.nametofont(name, root=root).configure(family=family, size=10)
    root.configure(background=BACKGROUND)
    icon = tk.PhotoImage(master=root, width=32, height=32)
    icon.put(BACKGROUND, to=(0, 0, 32, 32))
    icon.put("#284455", to=(1, 1, 31, 31))
    icon.put(SURFACE, to=(2, 2, 30, 30))
    for rectangle in ICON_RECTS:
        icon.put(ACCENT, to=rectangle)
    root.iconphoto(True, icon)
    root._gex_icon = icon
    root.option_add("*Font", (family, 10))
    for option, value in {
        "background": FIELD,
        "foreground": TEXT,
        "selectBackground": SELECT,
        "selectForeground": TEXT,
        "highlightBackground": BORDER,
        "highlightColor": ACCENT,
        "highlightThickness": 1,
        "borderWidth": 0,
    }.items():
        root.option_add(f"*Listbox.{option}", value)
        root.option_add(f"*Text.{option}", value)
    root.option_add("*Listbox.selectBorderWidth", 0)
    root.option_add("*Listbox.activestyle", "none")
    root.option_add("*Text.insertBackground", TEXT)
    root.option_add("*Text.padX", 8)
    root.option_add("*Text.padY", 6)

    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background=BACKGROUND, foreground=TEXT, font=(family, 10),
                    bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER)
    style.configure("TFrame", background=BACKGROUND)
    style.configure("TLabel", background=BACKGROUND, foreground=TEXT)
    style.configure("Muted.TLabel", background=BACKGROUND, foreground=MUTED)
    style.configure("Brand.TLabel", background=BACKGROUND, foreground=TEXT, font=(family, 12, "bold"))
    style.configure("DialogTitle.TLabel", background=BACKGROUND, foreground=TEXT, font=(family, 12, "bold"))
    style.configure("TButton", background="#243749", foreground=TEXT, bordercolor=BORDER,
                    focuscolor=ACCENT, padding=(10, 6), relief="flat")
    style.map("TButton", background=[("disabled", FIELD_DISABLED), ("pressed", "#304d60"),
                                     ("active", "#30485a")],
              foreground=[("disabled", DISABLED)], bordercolor=[("focus", ACCENT)])
    style.configure("Accent.TButton", background=ACCENT_BUTTON, foreground="#ffffff", bordercolor=ACCENT_BUTTON,
                    focuscolor="#d7f9fc", padding=(16, 7), font=(family, 10, "bold"))
    style.map("Accent.TButton", background=[("disabled", FIELD_DISABLED), ("pressed", "#226c7a"),
                                            ("active", ACCENT_HOVER)],
              foreground=[("disabled", DISABLED)], bordercolor=[("focus", ACCENT)])
    style.configure("TEntry", fieldbackground=FIELD, foreground=TEXT, insertcolor=TEXT,
                    bordercolor=BORDER, padding=(8, 6))
    style.map("TEntry", fieldbackground=[("disabled", FIELD_DISABLED), ("readonly", FIELD)],
              foreground=[("disabled", DISABLED), ("readonly", MUTED)],
              bordercolor=[("focus", ACCENT)])
    style.configure("TCombobox", fieldbackground=FIELD, background=SURFACE, foreground=TEXT,
                    arrowcolor=MUTED, bordercolor=BORDER, padding=(7, 5))
    style.map("TCombobox", fieldbackground=[("disabled", FIELD_DISABLED), ("readonly", FIELD)],
              foreground=[("disabled", DISABLED), ("readonly", TEXT)],
              selectbackground=[("readonly", FIELD)], selectforeground=[("readonly", TEXT)],
              bordercolor=[("focus", ACCENT)], arrowcolor=[("active", ACCENT)])
    style.configure("TCheckbutton", background=BACKGROUND, foreground=TEXT, padding=(0, 3),
                    indicatorbackground=FIELD, indicatorcolor=ACCENT)
    style.map("TCheckbutton", background=[("active", BACKGROUND)], foreground=[("disabled", DISABLED)],
              indicatorbackground=[("selected", ACCENT_BUTTON), ("disabled", FIELD_DISABLED)])
    style.configure("TLabelframe", background=BACKGROUND, bordercolor=BORDER, relief="solid")
    style.configure("TLabelframe.Label", background=BACKGROUND, foreground=MUTED, font=(family, 10, "bold"))
    style.configure("TNotebook", background=BACKGROUND, borderwidth=0, tabmargins=(0, 0, 0, 0))
    style.configure("TNotebook.Tab", background=FIELD, foreground=MUTED, bordercolor=BORDER,
                    padding=(18, 9), font=(family, 10))
    style.map("TNotebook.Tab", background=[("selected", SURFACE), ("active", "#203447")],
              foreground=[("selected", TEXT), ("active", TEXT)])
    rowheight = max(30, round(30 * root.winfo_fpixels("1i") / 96.0))
    style.configure("Treeview", background=FIELD, fieldbackground=FIELD, foreground=TEXT,
                    bordercolor=BORDER, rowheight=rowheight, relief="flat")
    style.map("Treeview", background=[("selected", SELECT)], foreground=[("selected", "#ffffff")])
    style.configure("Treeview.Heading", background=SURFACE, foreground=MUTED, bordercolor=BORDER,
                    padding=(8, 6), font=(family, 10, "bold"), relief="flat")
    style.map("Treeview.Heading", background=[("active", "#22394b")], foreground=[("active", TEXT)])
    style.configure("Vertical.TScrollbar", background="#31485b", troughcolor=FIELD, bordercolor=FIELD,
                    arrowcolor=MUTED, relief="flat", width=12)
    style.map("Vertical.TScrollbar", background=[("active", "#466579")])
    style.configure("TSeparator", background=BORDER)
    apply_window(root)
    return style


class _Prompt(tk.Toplevel):
    def __init__(self, parent, title, message, buttons, closed):
        super().__init__(parent)
        self.result = closed
        self.title(title)
        self.configure(background=BACKGROUND)
        self.transient(parent.winfo_toplevel())
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._close)
        body = ttk.Frame(self, padding=(22, 20, 22, 18))
        body.grid(sticky="nsew")
        ttk.Label(body, text=title, style="DialogTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(body, text=message, wraplength=480, justify="left").grid(row=1, column=0, sticky="w", pady=(12, 20))
        actions = ttk.Frame(body)
        actions.grid(row=2, column=0, sticky="e")
        primary = None
        for text, result, is_primary in buttons:
            button = ttk.Button(actions, text=text, command=lambda value=result: self._finish(value),
                                style="Accent.TButton" if is_primary else "TButton")
            button.pack(side="left", padx=(8, 0))
            if is_primary:
                primary = button
        self.bind("<Escape>", lambda _event: self._close())
        apply_window(self)
        self.update_idletasks()
        owner = parent.winfo_toplevel()
        x = owner.winfo_rootx() + max(0, (owner.winfo_width() - self.winfo_reqwidth()) // 2)
        y = owner.winfo_rooty() + max(0, (owner.winfo_height() - self.winfo_reqheight()) // 3)
        self.geometry(f"{x:+d}{y:+d}")
        self.wait_visibility()
        self.grab_set()
        if primary is not None:
            primary.focus_set()

    def _finish(self, result):
        self.result = result
        self.destroy()

    def _close(self):
        self.destroy()


def _prompt(title, message, parent, buttons, closed=None):
    previous = parent.grab_current()
    dialog = _Prompt(parent, title, message, buttons, closed)
    parent.wait_window(dialog)
    if previous is not None and previous.winfo_exists():
        previous.grab_set()
    return dialog.result


def showinfo(title, message, parent):
    _prompt(title, message, parent, [("确定", True, True)])


def showerror(title, message, parent):
    _prompt(title, message, parent, [("确定", True, True)])


def askyesno(title, message, parent):
    return _prompt(title, message, parent, [("取消", False, False), ("确定", True, True)], closed=False)


def askyesnocancel(title, message, parent):
    return _prompt(title, message, parent,
                   [("取消", None, False), ("不保存", False, False), ("保存", True, True)])


def _volume_roots():
    if os.name != "nt":
        return [str(Path.cwd().anchor or "/")]
    try:
        import ctypes
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        return [letter + ":\\" for index, letter in enumerate(string.ascii_uppercase) if mask & (1 << index)]
    except (AttributeError, OSError):
        return [str(Path.cwd().anchor)]


class _DirectoryPicker(tk.Toplevel):
    def __init__(self, parent, title, initialdir):
        super().__init__(parent)
        self.result = None
        self.current = None
        self.title(title)
        self.configure(background=BACKGROUND)
        self.transient(parent.winfo_toplevel())
        self.geometry("760x540")
        self.minsize(560, 400)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        bar = ttk.Frame(self, padding=(18, 18, 18, 10))
        bar.grid(row=0, column=0, sticky="ew")
        bar.columnconfigure(1, weight=1)
        self.volume = tk.StringVar()
        self.volumes = ttk.Combobox(bar, textvariable=self.volume, values=_volume_roots(), state="readonly", width=8)
        self.volumes.grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.volumes.bind("<<ComboboxSelected>>", lambda _event: self._navigate(self.volume.get()))
        self.path = tk.StringVar()
        path_entry = ttk.Entry(bar, textvariable=self.path)
        path_entry.grid(row=0, column=1, sticky="ew")
        path_entry.bind("<Return>", lambda _event: self._navigate(self.path.get()))
        ttk.Button(bar, text="上一级", command=self._up).grid(row=0, column=2, padx=(8, 0))
        listing = ttk.Frame(self, padding=(18, 0, 18, 0))
        listing.grid(row=1, column=0, sticky="nsew")
        listing.columnconfigure(0, weight=1)
        listing.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(listing, columns=(), selectmode="browse", show="tree headings")
        self.tree.heading("#0", text="文件夹", anchor="w")
        self.tree.column("#0", anchor="w", stretch=True)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(listing, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<Double-1>", lambda _event: self._open_selected())
        self.tree.bind("<Return>", lambda _event: self._open_selected())
        actions = ttk.Frame(self, padding=(18, 14, 18, 18))
        actions.grid(row=2, column=0, sticky="e")
        ttk.Button(actions, text="取消", command=self.destroy).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="打开", command=self._open_selected).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="选择", command=self._choose, style="Accent.TButton").pack(side="left")
        self.bind("<Escape>", lambda _event: self.destroy())
        start = Path(initialdir).expanduser() if initialdir else Path.home()
        if not start.is_dir():
            start = Path.home()
        self._navigate(start)
        apply_window(self)
        self.wait_visibility()
        self.grab_set()
        self.tree.focus_set()

    def _navigate(self, directory):
        try:
            directory = Path(directory).expanduser().resolve()
            with os.scandir(directory) as contents:
                folders = []
                for item in contents:
                    try:
                        if item.is_dir():
                            folders.append(item.name)
                    except OSError:
                        continue
        except (OSError, ValueError, RuntimeError) as error:
            showerror("无法打开目录", str(error), parent=self)
            return
        self.current = directory
        self.path.set(str(directory))
        self.volume.set(directory.anchor)
        self.tree.delete(*self.tree.get_children())
        for name in sorted(folders, key=str.casefold):
            self.tree.insert("", "end", text=name)

    def _up(self):
        if self.current is not None:
            self._navigate(self.current.parent)

    def _open_selected(self):
        selection = self.tree.selection()
        if self.current is not None and selection:
            self._navigate(self.current / self.tree.item(selection[0], "text"))

    def _choose(self):
        try:
            typed = Path(self.path.get()).expanduser().resolve()
            selection = self.tree.selection()
            chosen = (self.current / self.tree.item(selection[0], "text")) if typed == self.current and selection else typed
            if not chosen.is_dir():
                raise ValueError("请选择有效的文件夹。")
        except (OSError, ValueError, RuntimeError) as error:
            showerror("无法选择目录", str(error), parent=self)
            return
        self.result = str(chosen)
        self.destroy()


def askdirectory(title, initialdir, parent):
    previous = parent.grab_current()
    dialog = _DirectoryPicker(parent, title, initialdir)
    parent.wait_window(dialog)
    if previous is not None and previous.winfo_exists():
        previous.grab_set()
    return dialog.result or ""
