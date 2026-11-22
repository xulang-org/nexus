"""Tk mapping of the pinned XUUI workspace tokens."""

import json
import math
from pathlib import Path
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk


TOKENS = json.loads((Path(__file__).resolve().parents[1] / "assets/design/xu-ui-tokens.json").read_text())
PAPER = TOKENS["themes"]["light"]


def pixels(token):
    return int(TOKENS["base"][token].removesuffix("px"))


class EntryField(ttk.Frame):
    """Outlined XUUI field decoration around a native Tk entry."""

    def __init__(self, parent, label, variable, width, unit="", max_bytes=None):
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.variable = variable
        self.max_bytes = max_bytes
        self.box = tk.Frame(self, background=PAPER["surface"])
        self.box.grid(row=0, column=0, sticky="ew", pady=(pixels("space-2"), 0))
        self.box.columnconfigure(0, weight=1)
        self.box.columnconfigure(2, minsize=pixels("control-sm"))
        self.entry = ttk.Entry(self.box, textvariable=variable, width=width, style="FieldValue.TEntry")
        self.entry.grid(row=0, column=0, sticky="ew", padx=(pixels("space-3"), 0))
        if unit:
            ttk.Label(self.box, text=unit, style="Muted.TLabel").grid(row=0, column=1, padx=pixels("space-2"))
        self.clear_button = ttk.Button(self.box, name="clear", text="×", style="FieldClear.TButton",
                                       command=self.clear)
        self.clear_button.grid(row=0, column=2, padx=(0, pixels("space-1")))
        self.caption = ttk.Label(self, text=label, padding=(pixels("space-1"), 0), style="Muted.TLabel")
        self.caption.place(in_=self.box, x=pixels("space-3"), y=0, anchor="w", bordermode="ignore")
        self.caption.bind("<Button-1>", lambda _: self.entry.focus_set())
        self.box.bind("<Button-1>", lambda _: self.entry.focus_set())
        for widget in (self.entry, self.clear_button):
            widget.bind("<FocusIn>", self.paint_outline)
            widget.bind("<FocusOut>", self.paint_outline)

        self.support = ttk.Frame(self)
        self.support.grid(row=1, column=0, sticky="ew", pady=(pixels("space-1"), 0))
        self.support.columnconfigure(0, weight=1)
        self.error = ttk.Label(self.support, style="FieldError.TLabel", wraplength=184)
        self.error.grid(row=0, column=0, sticky="nw")
        self.counter = None
        if max_bytes is not None:
            self.counter = ttk.Label(self.support, style="Muted.TLabel")
            self.counter.grid(row=0, column=1, sticky="ne", padx=(pixels("space-2"), 0))
        self.bind("<Configure>", lambda event: self.wrap_error(event.width))
        self.trace = variable.trace_add("write", self.value_changed)
        self.bind("<Destroy>", self.release_trace)
        self.value_changed()

    def wrap_error(self, width):
        if self.counter is not None:
            width -= self.counter.winfo_reqwidth() + pixels("space-2")
        self.error.configure(wraplength=max(40, width))

    def clear(self):
        self.variable.set("")
        self.entry.focus_set()

    def value_changed(self, *_):
        value = self.variable.get()
        if value:
            self.clear_button.grid()
        else:
            self.clear_button.grid_remove()
        if self.counter is not None:
            self.counter.configure(text=f"{len(value.encode())} / {self.max_bytes} bytes")
        self.set_error("")
        if self.winfo_width() > 1:
            self.wrap_error(self.winfo_width())

    def release_trace(self, event):
        if event.widget is self:
            self.variable.trace_remove("write", self.trace)

    def paint_outline(self, _=None):
        invalid = self.entry.instate(["invalid"])
        focused = self.focus_get() in (self.entry, self.clear_button)
        ink = PAPER["danger"] if invalid else PAPER["focus"] if focused else PAPER["control-border"]
        thickness = 2 if focused or invalid else 1
        self.box.configure(highlightthickness=thickness, highlightbackground=ink, highlightcolor=ink)
        self.box.rowconfigure(0, minsize=pixels("control-lg") - 2 * thickness)
        self.caption.configure(style="FieldError.TLabel" if invalid else "Muted.TLabel")

    def set_error(self, message):
        self.entry.state(["invalid" if message else "!invalid"])
        self.error.configure(text=message)
        if message:
            self.error.grid()
        else:
            self.error.grid_remove()
        if message or self.counter is not None:
            self.support.grid()
        else:
            self.support.grid_remove()
        self.paint_outline()


def rounded_image(root, fill, border, radius, stroke=1, size=None, margin=0):
    size = size or radius * 2 + 6
    image = tk.PhotoImage(master=root, width=size + margin, height=size)
    image.put(PAPER["surface"], to=(0, 0, size + margin, size))
    for inset, color in ((0, border), (stroke, fill)):
        inner_radius = max(0, radius - inset)
        for y in range(inset, size - inset):
            distance = min(y, size - 1 - y) - inset
            corner = max(0.0, inner_radius - distance - 0.5)
            edge = inset + round(inner_radius - math.sqrt(inner_radius**2 - corner**2))
            image.put(color, to=(edge, y, size - edge, y + 1))
    return image


def install_theme(root):
    style = ttk.Style(root)
    style.theme_use("clam")
    families = {name.casefold(): name for name in tkfont.families(root)}

    def font(token, fallback, size, weight="normal"):
        stack = TOKENS["base"][token].split(",")
        family = next((families[name] for item in stack
                       if (name := item.strip().strip('"').casefold()) in families),
                      tkfont.nametofont(fallback, root).actual("family"))
        return family, -size, weight

    body = font("font-sans", "TkDefaultFont", 14)
    strong = font("font-sans", "TkDefaultFont", 14, "bold")
    title = font("font-sans", "TkDefaultFont", 16, "bold")
    small = font("font-sans", "TkDefaultFont", 12)
    mono = font("font-mono", "TkFixedFont", 13)
    color = PAPER
    style.configure(".", font=body, foreground=color["text"], background=color["surface"],
                    bordercolor=color["border"], lightcolor=color["surface"], darkcolor=color["surface"],
                    focuscolor=color["focus"], selectbackground=color["brand-soft"],
                    selectforeground=color["text"], insertcolor=color["text"])
    style.configure("Panel.TLabel", font=title)
    style.configure("Brand.TLabel", font=title, foreground=color["brand"])
    style.configure("Field.TLabel", font=strong)
    style.configure("Muted.TLabel", font=small, foreground=color["muted"])
    style.configure("FieldError.TLabel", font=small, foreground=color["danger"])
    for name, tone in (("Warning", "warning"), ("Success", "success"), ("Error", "danger")):
        style.configure(f"{name}.TLabel", foreground=color[tone])
    style.configure("TSeparator", background=color["border"], bordercolor=color["border"],
                    lightcolor=color["border"], darkcolor=color["border"])

    owner = root.nametowidget(".")
    if not hasattr(owner, "_nexus_button_images"):
        owner._nexus_button_images = []
    radius = pixels("radius-md")
    line_height = tkfont.Font(root=root, font=strong).metrics("linespace")
    button_padding = (pixels("space-3"), max(1, math.ceil((pixels("control-md") - line_height) / 2)))
    for name, background, hovered, pressed, foreground, border in [
        ("TButton", "elevated", "subtle", "control-pressed", "text", "control-border"),
        ("Primary.TButton", "brand", "brand-hover", "brand-pressed", "on-brand", "brand"),
        ("Quiet.TButton", "surface", "elevated", "control-pressed", "muted", "surface"),
        ("FieldClear.TButton", "surface", "elevated", "control-pressed", "muted", "surface"),
    ]:
        style.configure(name, font=strong, padding=button_padding, width=0, anchor="center",
                        foreground=color[foreground])
        style.map(name, foreground=[("disabled", color["control-border"]), ("active", color[foreground])])
        element = f"Nexus.{name}.surface"
        if element not in style.element_names():
            normal = rounded_image(owner, color[background], color[border], radius)
            disabled = rounded_image(owner, color["surface"], color["surface"], radius)
            down = rounded_image(owner, color[pressed], color[border], radius)
            focus = rounded_image(owner, color[background], color["focus"], radius, stroke=2)
            hover = rounded_image(owner, color[hovered], color[border], radius)
            owner._nexus_button_images.extend((normal, disabled, down, focus, hover))
            style.element_create(element, "image", normal, ("disabled", disabled), ("pressed", down),
                                 ("focus", focus), ("active", hover), padding=0, border=radius + 2, sticky="nswe")
        style.layout(name, [(element, {"sticky": "nswe", "children": [
            ("Button.padding", {"sticky": "nswe", "children": [("Button.label", {"sticky": "nswe"})]})
        ]})])
    style.configure("FieldClear.TButton", font=(body[0], -20, "normal"), padding=(4, 2))

    for name in ("TEntry", "TCombobox"):
        style.configure(name, padding=(10, 9), fieldbackground=color["canvas"],
                        background=color["elevated"], bordercolor=color["control-border"],
                        arrowcolor=color["text"], arrowsize=14)
        style.map(name, fieldbackground=[("disabled", color["surface"]), ("readonly", color["canvas"])],
                  bordercolor=[("disabled", color["border"]), ("invalid", color["danger"]),
                               ("focus", color["focus"])],
                  foreground=[("disabled", color["muted"])])
    style.configure("Coordinate.TEntry", font=mono, padding=(10, 9))
    style.configure("FieldValue.TEntry", background=color["surface"], fieldbackground=color["surface"], padding=0)
    style.layout("FieldValue.TEntry", [("Entry.textarea", {"sticky": "nswe"})])
    style.configure("TCheckbutton", padding=(0, 5))
    indicator = "Nexus.check.indicator"
    if indicator not in style.element_names():
        checkbox_size = pixels("icon-sm")
        gap = pixels("space-2")

        def checkbox(selected, focused):
            fill = color["brand" if selected else "canvas"]
            border = color["focus" if focused else "brand" if selected else "control-border"]
            image = rounded_image(owner, fill, border, pixels("radius-sm"),
                                  size=checkbox_size, margin=gap)
            if selected:
                for i in range(3):
                    image.put(color["on-brand"], to=(4+i, 7+i, 6+i, 9+i))
                for i in range(6):
                    image.put(color["on-brand"], to=(6+i, 9-i, 8+i, 11-i))
            return image

        empty, checked, focus_empty, focus_checked = (checkbox(*state) for state in
                                                     [(False, False), (True, False), (False, True), (True, True)])
        owner._nexus_button_images.extend((empty, checked, focus_empty, focus_checked))
        style.element_create(indicator, "image", empty, ("selected", "focus", focus_checked),
                             ("focus", focus_empty), ("selected", checked), sticky="w")
    style.layout("TCheckbutton", [("Checkbutton.padding", {"sticky": "nswe", "children": [
        (indicator, {"side": "left", "sticky": "w"}), ("Checkbutton.label", {"side": "left", "sticky": "nswe"})
    ]})])
    style.configure("Treeview", rowheight=pixels("control-sm"), background=color["surface"],
                    fieldbackground=color["surface"], relief="flat", borderwidth=0, padding=(4, 0))
    style.map("Treeview", background=[("selected", color["brand-soft"])],
              foreground=[("selected", color["text"])])
    style.configure("Vertical.TScrollbar", background=color["elevated"], troughcolor=color["surface"],
                    arrowcolor=color["muted"], arrowsize=10)
    style.map("Vertical.TScrollbar", background=[("active", color["subtle"])])
    for option, key in (("background", "canvas"), ("foreground", "text"),
                        ("selectBackground", "brand-soft"), ("selectForeground", "text")):
        root.option_add(f"*TCombobox*Listbox.{option}", color[key])
    return small, mono
