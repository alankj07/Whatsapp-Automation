"""
WhatsApp Message Sender — desktop GUI (Windows).
"""

from __future__ import annotations

import json
import os
import time
import threading
import tkinter as tk
import webbrowser
from datetime import datetime, timedelta
from tkinter import messagebox, ttk

from whatsapp_sender import (
    _parse_date,
    _parse_time,
    normalize_phone,
    send_whatsapp_message,
    wait_until,
    prepare_whatsapp_chat,
    send_whatsapp_prepared,
    force_foreground,
)

# Brand palette (Premium WhatsApp Dark Theme)
COLOR_BG = "#0b141a"         # Deep WhatsApp dark background
COLOR_SURFACE = "#111b21"    # Main container surface background
COLOR_HEADER_TOP = "#202c33" # Header top panel background
COLOR_HEADER_BOTTOM = "#222e35" # Sub-header/accent panel
COLOR_ACCENT = "#00e676"     # Neon WhatsApp Green
COLOR_ACCENT_DARK = "#00b248" # Darker Green for pressed state
COLOR_ACCENT_LIGHT = "#182229" # Subtle panel selection highlight
COLOR_TEXT = "#e9edef"       # WhatsApp High-contrast light text
COLOR_MUTED = "#8696a0"      # WhatsApp Muted text grey
COLOR_BORDER = "#222e35"     # Container border divider
COLOR_SECTION = "#1f2c34"    # Card group background
COLOR_INPUT_BG = "#2a3942"   # Deep grey for inputs/fields
COLOR_INPUT_FOCUS = "#00e676" # Focus outline green
COLOR_DISABLED = "#1f2c34"   # Disabled button background
COLOR_STATUS_OK = "#00e676"  # Success status green
COLOR_STATUS_BUSY = "#f7b928" # Busy/Scheduled status amber
COLOR_STATUS_IDLE = "#8696a0" # Idle status grey


def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    try:
        hex_str = hex_str.lstrip('#')
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
    except Exception:
        return (255, 255, 255)

def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return '#{:02x}{:02x}{:02x}'.format(*rgb)

def interpolate_color(color1: str, color2: str, factor: float) -> str:
    r1, g1, b1 = hex_to_rgb(color1)
    r2, g2, b2 = hex_to_rgb(color2)
    r = int(r1 + (r2 - r1) * factor)
    g = int(g1 + (g2 - g1) * factor)
    b = int(b1 + (b2 - b1) * factor)
    return rgb_to_hex((r, g, b))


class HoverButton(tk.Button):
    """Flat button with smooth hover fade transition."""

    def __init__(
        self,
        master,
        *,
        bg: str,
        hover: str,
        active: str | None = None,
        **kwargs,
    ) -> None:
        self._bg = bg
        self._hover = hover
        self._active = active or hover
        super().__init__(
            master,
            bg=bg,
            activebackground=self._active,
            relief=tk.FLAT,
            cursor="hand2",
            borderwidth=0,
            highlightthickness=0,
            **kwargs,
        )
        self._anim_task = None
        self.bind("<Enter>", lambda _e: self._fade_to(self._hover))
        self.bind("<Leave>", lambda _e: self._fade_to(self._bg))

    def _fade_to(self, target_color: str, step: int = 0, total_steps: int = 8) -> None:
        if self._anim_task:
            self.after_cancel(self._anim_task)
            self._anim_task = None
            
        current_color = self.cget("bg")
        if self.cget("state") == tk.DISABLED:
            return
            
        if step >= total_steps or current_color == target_color:
            self.configure(bg=target_color)
            return

        next_color = interpolate_color(current_color, target_color, 0.35)
        self.configure(bg=next_color)
        
        self._anim_task = self.after(20, lambda: self._fade_to(target_color, step + 1, total_steps))

    def set_enabled(self, enabled: bool) -> None:
        if self._anim_task:
            self.after_cancel(self._anim_task)
            self._anim_task = None
        if enabled:
            self.configure(state=tk.NORMAL, bg=self._bg)
        else:
            self.configure(state=tk.DISABLED, bg=COLOR_DISABLED)


class FloatingProgressWindow(tk.Toplevel):
    def __init__(self, app: WhatsAppSenderApp) -> None:
        super().__init__(app.root)
        self.app = app
        self.title("Automation Progress")
        
        # Borderless window
        self.overrideredirect(True)
        # Always on top
        self.wm_attributes("-topmost", True)
        
        # Set dimensions and position (bottom right corner of screen)
        width = 320
        height = 165
        
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        # 30px padding from right and bottom
        x = screen_width - width - 30
        y = screen_height - height - 50
        self.geometry(f"{width}x{height}+{x}+{y}")
        
        # Windows Native drop shadow for borderless window
        import ctypes
        try:
            hwnd = self.winfo_id()
            user32 = ctypes.windll.user32
            style = user32.GetClassLongW(hwnd, -26)  # GCL_STYLE = -26
            user32.SetClassLongW(hwnd, -26, style | 0x00020000)  # CS_DROPSHADOW = 0x00020000
        except Exception:
            pass
            
        # Background transparency trick for rounded corners
        self.wm_attributes("-transparentcolor", "#000001")
        self.configure(bg="#000001")
        
        # Canvas to draw rounded card
        self.canvas = tk.Canvas(self, width=width, height=height, bg="#000001", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Draw premium rounded card with a double neon border (teal outline + neon glow cyan-green outline)
        self.draw_rounded_rect(2, 2, 318, 163, radius=16, fill="#111b21", outline="#003d33", width=3)
        self.draw_rounded_rect(4, 4, 316, 161, radius=14, fill="", outline="#00e6b8", width=1)
        
        # Dragging data
        self.drag_data = {"x": 0, "y": 0}
        
        # Inner main frame placed on top of the Canvas
        # Center of frame is (160, 82)
        self.main_frame = tk.Frame(self.canvas, bg="#111b21")
        # Placing frame slightly smaller to fit within rounded outline
        self.canvas.create_window(160, 82, window=self.main_frame, width=308, height=153)
        
        # Custom Title Bar (Minimalist header in parent background)
        self.title_bar = tk.Frame(self.main_frame, bg="#111b21", height=28)
        self.title_bar.pack(fill=tk.X, pady=(2, 0))
        self.title_bar.pack_propagate(False)
        
        # Indicator Dot for Pulse Animation
        self.indicator_dot = tk.Label(
            self.title_bar,
            text="●",
            font=("Segoe UI", 12),
            fg="#00e676",
            bg="#111b21",
            anchor="w",
        )
        self.indicator_dot.pack(side=tk.LEFT, padx=(12, 4))
        
        self.title_label = tk.Label(
            self.title_bar,
            text="WhatsApp Sender Progress",
            font=("Segoe UI", 9, "bold"),
            fg="white",
            bg="#111b21",
            anchor="w",
        )
        self.title_label.pack(side=tk.LEFT)
        
        # Bind dragging to title bar, title label, and canvas
        for widget in (self.title_bar, self.title_label, self.canvas):
            widget.bind("<Button-1>", self.start_drag)
            widget.bind("<B1-Motion>", self.drag)
            
        # Status Label
        self.status_label = tk.Label(
            self.main_frame,
            text="Initializing...",
            font=("Segoe UI", 10, "bold"),
            fg="#e9edef",
            bg="#111b21",
            anchor="w",
            padx=12,
        )
        self.status_label.pack(fill=tk.X, pady=(4, 6))
        
        # Progress and ETC Info Label
        self.info_label = tk.Label(
            self.main_frame,
            text="Progress: 0/0  •  ETC: --:--",
            font=("Segoe UI", 9),
            fg="#8696a0",
            bg="#111b21",
            anchor="w",
            padx=12,
        )
        self.info_label.pack(fill=tk.X)
        
        # Progress Bar Canvas
        self.progress_canvas = tk.Canvas(
            self.main_frame,
            height=6,
            bg="#222e35",
            highlightthickness=0,
            bd=0,
        )
        self.progress_canvas.pack(fill=tk.X, padx=12, pady=(6, 10))
        self.progress_rect = self.progress_canvas.create_rectangle(0, 0, 0, 6, fill="#00e676", width=0)
        
        # Action Buttons Frame
        self.btn_frame = tk.Frame(self.main_frame, bg="#111b21")
        self.btn_frame.pack(fill=tk.X, padx=12, pady=(0, 8))
        
        # Restore button
        self.restore_btn = tk.Button(
            self.btn_frame,
            text="Show Main App",
            font=("Segoe UI", 8, "bold"),
            fg="#00e676",
            bg="#202c33",
            activebackground="#2a3942",
            activeforeground="#00e676",
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
            padx=10,
            pady=4,
            command=self.restore_main_app
        )
        self.restore_btn.pack(side=tk.LEFT)
        
        # Cancel / Close Button
        self.action_btn = tk.Button(
            self.btn_frame,
            text="Cancel",
            font=("Segoe UI", 8, "bold"),
            fg="white",
            bg="#ea0038",
            activebackground="#c0002e",
            activeforeground="white",
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
            padx=12,
            pady=4,
            command=self.cancel_or_close
        )
        self.action_btn.pack(side=tk.RIGHT)
        
        self.completed = False
        
        # Bind dragging on widgets that might eat drag events
        for widget in (self.status_label, self.info_label):
            widget.bind("<Button-1>", self.start_drag)
            widget.bind("<B1-Motion>", self.drag)
            
        # Start micro-animations
        self.pulse_indicator()

    def draw_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1
        ]
        return self.canvas.create_polygon(points, **kwargs, smooth=True)

    def pulse_indicator(self) -> None:
        """Micro-animation: pulse the indicator dot to show activity."""
        if self.completed:
            return
        try:
            current_color = self.indicator_dot.cget("fg")
            next_color = "#00e676" if current_color == "#003d33" else "#003d33"
            self.indicator_dot.configure(fg=next_color)
        except Exception:
            pass
        self.after(600, self.pulse_indicator)

    def start_drag(self, event: tk.Event) -> None:
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y

    def drag(self, event: tk.Event) -> None:
        x = self.winfo_x() - self.drag_data["x"] + event.x
        y = self.winfo_y() - self.drag_data["y"] + event.y
        self.geometry(f"+{x}+{y}")

    def update_status(self, text: str) -> None:
        if len(text) > 35:
            text = text[:32] + "..."
        self.status_label.configure(text=text)

    def update_progress_info(self, current: int, total: int, pct: float, etc_text: str) -> None:
        percent_str = f"{int(pct * 100)}%"
        self.info_label.configure(text=f"Progress: {current}/{total} ({percent_str})  •  ETC: {etc_text}")
        
        # Update progress bar
        canvas_width = 308 - 24
        new_width = int(canvas_width * pct)
        self.progress_canvas.coords(self.progress_rect, 0, 0, new_width, 6)

    def set_completed_state(self, status_text: str) -> None:
        self.completed = True
        self.update_status(status_text)
        self.action_btn.configure(text="Close", bg="#00a884", activebackground="#008f72")
        self.restore_btn.pack_forget()
        
        # Change indicator dot on completion (Checkmark for success, Cross for failure/cancel)
        if "success" in status_text.lower() or "completed" in status_text.lower():
            self.indicator_dot.configure(text="✔", fg="#00e676")
            total = self.app.total_contacts if self.app.total_contacts > 0 else 1
            self.update_progress_info(total, total, 1.0, "0s")
        else:
            self.indicator_dot.configure(text="✖", fg="#ea0038")

    def restore_main_app(self) -> None:
        self.app.root.deiconify()
        self.app.root.lift()
        self.app.root.focus_force()

    def cancel_or_close(self) -> None:
        if not self.completed:
            self.app._on_cancel()
        else:
            self.restore_main_app()
            self.destroy()
            self.app.floating_window = None


class WhatsAppSenderApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("WhatsApp Message Sender")
        self.root.minsize(640, 720)
        self.root.configure(bg=COLOR_BG)
        self._center_window(820, 840)

        self._stop_event = threading.Event()
        self._worker: threading.Thread | None = None
        self._busy = False
        self.files_list: list[str] = []
        self.floating_window: FloatingProgressWindow | None = None

        # Progress & ETC States
        self.total_contacts = 0
        self.current_idx = 0
        self.t_per_contact = 0.0
        self.total_est_time = 0.0
        self.send_start_time = 0.0

        self._build_styles()
        self._build_ui()
        self._toggle_schedule_fields()
        self._update_when_toggle()
        self.root.after(50, self._sync_canvas_width)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_canvas_resize(self, event: tk.Event) -> None:
        """Stretch scrollable content to full canvas width."""
        if event.width > 1:
            self._canvas.itemconfigure(self._canvas_window, width=event.width)

    def _sync_canvas_width(self) -> None:
        w = self._canvas.winfo_width()
        if w > 1:
            self._canvas.itemconfigure(self._canvas_window, width=w)

    def _center_window(self, w: int, h: int) -> None:
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = max(0, (sh - h) // 2 - 24)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _on_mousewheel(self, event: tk.Event) -> None:
        if not hasattr(self, "scroll_target"):
            self.scroll_target = self._canvas.yview()[0]
        
        direction = -1 if event.delta > 0 else 1
        self.scroll_target = max(0.0, min(1.0, self.scroll_target + direction * 0.08))
        
        if not getattr(self, "scroll_animating", False):
            self.scroll_animating = True
            self._animate_scroll()

    def _animate_scroll(self) -> None:
        if not hasattr(self, "_canvas") or not self._canvas.winfo_exists():
            self.scroll_animating = False
            return
        curr = self._canvas.yview()[0]
        diff = self.scroll_target - curr
        if abs(diff) < 0.001:
            self._canvas.yview_moveto(self.scroll_target)
            self.scroll_animating = False
            return
        next_y = curr + diff * 0.25
        self._canvas.yview_moveto(next_y)
        self.root.after(15, self._animate_scroll)

    def _build_styles(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")

        # Scrollbar styling
        style.configure(
            "Custom.Vertical.TScrollbar",
            gripcount=0,
            background=COLOR_INPUT_BG,
            troughcolor=COLOR_BG,
            bordercolor=COLOR_BORDER,
            darkcolor=COLOR_INPUT_BG,
            lightcolor=COLOR_INPUT_BG,
            arrowcolor=COLOR_TEXT,
            borderwidth=0,
            arrowsize=12,
        )

        # Treeview styling (Sent History table)
        style.configure(
            "Custom.Treeview",
            background=COLOR_SURFACE,
            foreground=COLOR_TEXT,
            rowheight=28,
            fieldbackground=COLOR_SURFACE,
            bordercolor=COLOR_BORDER,
            borderwidth=1,
            font=("Segoe UI", 9)
        )
        style.configure(
            "Custom.Treeview.Heading",
            background=COLOR_HEADER_TOP,
            foreground=COLOR_TEXT,
            bordercolor=COLOR_BORDER,
            borderwidth=1,
            font=("Segoe UI", 9, "bold")
        )
        style.map(
            "Custom.Treeview",
            background=[("selected", COLOR_ACCENT)],
            foreground=[("selected", "#0b141a")]
        )
        style.map(
            "Custom.Treeview.Heading",
            background=[("active", COLOR_HEADER_BOTTOM)],
            foreground=[("active", COLOR_TEXT)]
        )

    def _build_ui(self) -> None:
        self._build_header()

        # Scrollable main area
        container = tk.Frame(self.root, bg=COLOR_BG)
        container.pack(fill=tk.BOTH, expand=True)

        self._canvas = tk.Canvas(container, bg=COLOR_BG, highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(
            container, orient=tk.VERTICAL, command=self._canvas.yview, style="Custom.Vertical.TScrollbar"
        )
        self._scroll_frame = tk.Frame(self._canvas, bg=COLOR_BG)
        self._scroll_frame.bind(
            "<Configure>",
            lambda _e: self._canvas.configure(scrollregion=self._canvas.bbox("all")),
        )
        self._canvas_window = self._canvas.create_window(
            (0, 0), window=self._scroll_frame, anchor="nw"
        )
        self._canvas.bind("<Configure>", self._on_canvas_resize)
        self._canvas.configure(yscrollcommand=scrollbar.set)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(16, 0), pady=16)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(4, 16), pady=16)

        self._canvas.bind("<Enter>", lambda _e: self._canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self._canvas.bind("<Leave>", lambda _e: self._canvas.unbind_all("<MouseWheel>"))

        pad = tk.Frame(self._scroll_frame, bg=COLOR_BG)
        pad.pack(fill=tk.BOTH, expand=True)
        pad.columnconfigure(0, weight=1)

        self._build_disclaimer_section(pad)
        self._build_recipient_section(pad)
        self._build_message_section(pad)
        self._build_file_section(pad)
        self._build_schedule_section(pad)
        self._build_options_section(pad)
        self._build_history_section(pad)

        self._build_action_bar()
        self._build_footer()
        self._build_developer_footer(pad)

    def _build_header(self) -> None:
        header = tk.Frame(self.root, bg=COLOR_HEADER_TOP, height=120)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        # Gradient effect (two bands)
        band = tk.Frame(header, bg=COLOR_HEADER_BOTTOM, height=40)
        band.place(relx=0, rely=1, relwidth=1, anchor="sw")

        inner = tk.Frame(header, bg=COLOR_HEADER_TOP)
        inner.place(relx=0, rely=0, relwidth=1, relheight=1)

        row = tk.Frame(inner, bg=COLOR_HEADER_TOP)
        row.pack(fill=tk.BOTH, expand=True, padx=24, pady=20)

        logo = tk.Label(
            row,
            text="💬",
            font=("Segoe UI Emoji", 28),
            bg=COLOR_ACCENT,
            fg="#0b141a",
            width=2,
            padx=6,
            pady=4,
        )
        logo.pack(side=tk.LEFT)

        titles = tk.Frame(row, bg=COLOR_HEADER_TOP)
        titles.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(16, 0))

        tk.Label(
            titles,
            text="WhatsApp Message Sender",
            font=("Segoe UI", 20, "bold"),
            fg=COLOR_TEXT,
            bg=COLOR_HEADER_TOP,
        ).pack(anchor="w")

        tk.Label(
            titles,
            text="Compose, schedule, and send via WhatsApp Desktop",
            font=("Segoe UI", 10),
            fg=COLOR_MUTED,
            bg=COLOR_HEADER_TOP,
        ).pack(anchor="w", pady=(4, 0))

    def _card(self, parent: tk.Frame, icon: str, title: str) -> tk.Frame:
        outer = tk.Frame(parent, bg=COLOR_BG)
        outer.pack(fill=tk.BOTH, expand=True, pady=(0, 14))
        outer.columnconfigure(0, weight=1)

        card = tk.Frame(outer, bg=COLOR_SURFACE, highlightbackground=COLOR_BORDER, highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True)
        card.columnconfigure(1, weight=1)

        accent = tk.Frame(card, bg=COLOR_ACCENT, width=4)
        accent.grid(row=0, column=0, sticky="ns")

        body = tk.Frame(card, bg=COLOR_SURFACE, padx=20, pady=16)
        body.grid(row=0, column=1, sticky="nsew")
        body.columnconfigure(0, weight=1)

        head = tk.Frame(body, bg=COLOR_SURFACE)
        head.pack(fill=tk.X, pady=(0, 12))

        tk.Label(
            head,
            text=icon,
            font=("Segoe UI Emoji", 14),
            bg=COLOR_SURFACE,
            fg=COLOR_ACCENT,
        ).pack(side=tk.LEFT)

        tk.Label(
            head,
            text=title,
            font=("Segoe UI", 12, "bold"),
            fg=COLOR_TEXT,
            bg=COLOR_SURFACE,
        ).pack(side=tk.LEFT, padx=(8, 0))

        return body

    def _labeled_input(
        self,
        parent: tk.Frame,
        label: str,
        hint: str = "",
        width: int | None = None,
        var: tk.StringVar | None = None,
    ) -> tk.Entry:
        tk.Label(
            parent,
            text=label,
            font=("Segoe UI", 9, "bold"),
            fg=COLOR_TEXT,
            bg=COLOR_SURFACE,
        ).pack(anchor="w")
        if hint:
            tk.Label(
                parent,
                text=hint,
                font=("Segoe UI", 8),
                fg=COLOR_MUTED,
                bg=COLOR_SURFACE,
            ).pack(anchor="w", pady=(2, 6))
        else:
            tk.Frame(parent, height=6, bg=COLOR_SURFACE).pack()

        wrap = tk.Frame(parent, bg=COLOR_BORDER, padx=1, pady=1)
        wrap.pack(fill=tk.X, pady=(0, 10))
        wrap.columnconfigure(0, weight=1)

        entry = tk.Entry(
            wrap,
            textvariable=var,
            font=("Segoe UI", 11),
            fg=COLOR_TEXT,
            bg=COLOR_INPUT_BG,
            relief=tk.FLAT,
            insertbackground=COLOR_ACCENT,
        )
        if width is not None:
            entry.configure(width=width)
        entry.grid(row=0, column=0, sticky="ew", ipady=8, ipadx=10)

        def on_focus_in(_e: tk.Event) -> None:
            wrap.configure(bg=COLOR_INPUT_FOCUS)

        def on_focus_out(_e: tk.Event) -> None:
            wrap.configure(bg=COLOR_BORDER)

        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)
        return entry

    def _styled_entry_box(self, parent: tk.Frame, var: tk.StringVar) -> tk.Frame:
        """Bordered entry container (same height as other fields)."""
        wrap = tk.Frame(parent, bg=COLOR_BORDER, padx=1, pady=1)
        wrap.columnconfigure(0, weight=1)
        entry = tk.Entry(
            wrap,
            textvariable=var,
            font=("Segoe UI", 11),
            fg=COLOR_TEXT,
            bg=COLOR_INPUT_BG,
            relief=tk.FLAT,
            insertbackground=COLOR_ACCENT,
        )
        entry.grid(row=0, column=0, sticky="ew", ipady=6, ipadx=10)

        def on_focus_in(_e: tk.Event) -> None:
            wrap.configure(bg=COLOR_INPUT_FOCUS)

        def on_focus_out(_e: tk.Event) -> None:
            wrap.configure(bg=COLOR_BORDER)

        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)
        return wrap

    def _build_disclaimer_section(self, parent: tk.Frame) -> None:
        outer = tk.Frame(parent, bg=COLOR_BG)
        outer.pack(fill=tk.BOTH, expand=True, pady=(0, 14))
        outer.columnconfigure(0, weight=1)

        card = tk.Frame(outer, bg="#2c220c", highlightbackground="#ffd666", highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True)

        accent = tk.Frame(card, bg="#f7b928", width=4)
        accent.pack(side=tk.LEFT, fill=tk.Y)

        body = tk.Frame(card, bg="#2c220c", padx=20, pady=12)
        body.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(
            body,
            text="⚠️ Disclaimer / Important",
            font=("Segoe UI", 10, "bold"),
            fg="#ffd666",
            bg="#2c220c",
        ).pack(anchor="w")

        lbl = tk.Label(
            body,
            text="Please ensure that the WhatsApp Desktop application is open and active on your screen. Closed window may cause the automation process to fail.",
            font=("Segoe UI", 9),
            fg="#f5e3b5",
            bg="#2c220c",
            justify=tk.LEFT,
        )
        lbl.pack(anchor="w", pady=(4, 0))

        def _adjust_wrap(event: tk.Event) -> None:
            lbl.configure(wraplength=event.width - 20)

        body.bind("<Configure>", _adjust_wrap)

    def _build_recipient_section(self, parent: tk.Frame) -> None:
        body = self._card(parent, "📱", "Recipient")

        grid = tk.Frame(body, bg=COLOR_SURFACE)
        grid.pack(fill=tk.X)
        grid.columnconfigure(0, weight=3)
        grid.columnconfigure(1, weight=1)

        label_font = ("Segoe UI", 9, "bold")
        hint_font = ("Segoe UI", 8)

        tk.Label(
            grid, text="Phone numbers", font=label_font, fg=COLOR_TEXT, bg=COLOR_SURFACE
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            grid, text="Country code", font=label_font, fg=COLOR_TEXT, bg=COLOR_SURFACE
        ).grid(row=0, column=1, sticky="w", padx=(16, 0))

        hint_row = tk.Frame(grid, bg=COLOR_SURFACE, height=34)
        hint_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 8))
        hint_row.grid_propagate(False)
        hint_row.columnconfigure(0, weight=3)
        hint_row.columnconfigure(1, weight=1)

        tk.Label(
            hint_row,
            text="Enter one number per line or separated by commas",
            font=hint_font,
            fg=COLOR_MUTED,
            bg=COLOR_SURFACE,
            anchor="nw",
            justify=tk.LEFT,
        ).grid(row=0, column=0, sticky="nw")

        tk.Label(
            hint_row,
            text="e.g. 91 for India",
            font=hint_font,
            fg=COLOR_MUTED,
            bg=COLOR_SURFACE,
            anchor="nw",
        ).grid(row=0, column=1, sticky="nw", padx=(16, 0))

        wrap = tk.Frame(grid, bg=COLOR_BORDER, padx=1, pady=1)
        wrap.grid(row=2, column=0, sticky="ew", padx=(0, 16))
        wrap.columnconfigure(0, weight=1)

        self.phone_text = tk.Text(
            wrap,
            height=1,
            font=("Segoe UI", 11),
            fg=COLOR_TEXT,
            bg=COLOR_INPUT_BG,
            relief=tk.FLAT,
            wrap=tk.WORD,
            padx=10,
            pady=6,
            insertbackground=COLOR_ACCENT,
            highlightthickness=0,
        )
        self.phone_text.grid(row=0, column=0, sticky="nsew")
        self.phone_scroll = ttk.Scrollbar(wrap, orient=tk.VERTICAL, command=self.phone_text.yview)
        self.phone_text.configure(yscrollcommand=self.phone_scroll.set)
        
        # Monitor changes to resize text box dynamically
        self.phone_text.bind("<KeyRelease>", self._adjust_phone_height)

        self.country_var = tk.StringVar(value="91")
        cc_box = self._styled_entry_box(grid, self.country_var)
        cc_box.grid(row=2, column=1, sticky="ew")

        csv_row = tk.Frame(body, bg=COLOR_SURFACE)
        csv_row.pack(fill=tk.X, pady=(10, 0))

        self.import_csv_btn = HoverButton(
            csv_row,
            text="📥  Import CSV",
            font=("Segoe UI", 9, "bold"),
            fg="white",
            bg=COLOR_ACCENT,
            hover=COLOR_ACCENT_DARK,
            padx=12,
            pady=6,
            command=self._on_import_csv,
        )
        self.import_csv_btn.pack(side=tk.LEFT)

    def _adjust_phone_height(self, _event: tk.Event | None = None) -> None:
        content = self.phone_text.get("1.0", "end-1c").strip()
        if not content:
            self.phone_text.configure(height=1)
            try:
                self.phone_scroll.grid_remove()
            except Exception:
                pass
            return

        line_count = len(content.splitlines())
        new_height = max(1, min(line_count, 8))
        self.phone_text.configure(height=new_height)

        try:
            if line_count > 8:
                self.phone_scroll.grid(row=0, column=1, sticky="ns")
            else:
                self.phone_scroll.grid_remove()
        except Exception:
            pass

    def _build_message_section(self, parent: tk.Frame) -> None:
        body = self._card(parent, "✉️", "Message")

        tk.Label(
            body,
            text="Write your message",
            font=("Segoe UI", 9, "bold"),
            fg=COLOR_TEXT,
            bg=COLOR_SURFACE,
        ).pack(anchor="w")

        wrap = tk.Frame(body, bg=COLOR_BORDER, padx=1, pady=1)
        wrap.pack(fill=tk.X, pady=(6, 8))
        wrap.columnconfigure(0, weight=1)

        self.message_text = tk.Text(
            wrap,
            height=6,
            font=("Segoe UI", 11),
            fg=COLOR_TEXT,
            bg=COLOR_INPUT_BG,
            relief=tk.FLAT,
            wrap=tk.WORD,
            padx=12,
            pady=10,
            insertbackground=COLOR_ACCENT,
            highlightthickness=0,
        )
        self.message_text.grid(row=0, column=0, sticky="nsew")
        msg_scroll = ttk.Scrollbar(wrap, orient=tk.VERTICAL, command=self.message_text.yview)
        msg_scroll.grid(row=0, column=1, sticky="ns")
        self.message_text.configure(yscrollcommand=msg_scroll.set)
        self.message_text.bind("<KeyRelease>", self._update_char_count)

        meta = tk.Frame(body, bg=COLOR_SURFACE)
        meta.pack(fill=tk.X)
        self.char_count_var = tk.StringVar(value="0 characters")
        tk.Label(
            meta,
            textvariable=self.char_count_var,
            font=("Segoe UI", 8),
            fg=COLOR_MUTED,
            bg=COLOR_SURFACE,
        ).pack(side=tk.RIGHT)

        self.timestamp_var = tk.BooleanVar(value=False)
        self._styled_check(
            body,
            "Add date & time stamp to message",
            self.timestamp_var,
        )

    def _styled_check(self, parent: tk.Frame, text: str, variable: tk.BooleanVar) -> None:
        row = tk.Frame(parent, bg=COLOR_SECTION, padx=10, pady=8)
        row.pack(fill=tk.X, pady=(4, 0))
        cb = tk.Checkbutton(
            row,
            text=text,
            variable=variable,
            font=("Segoe UI", 10),
            fg=COLOR_TEXT,
            bg=COLOR_SECTION,
            activebackground=COLOR_SECTION,
            activeforeground=COLOR_TEXT,
            selectcolor=COLOR_INPUT_BG,
            relief=tk.FLAT,
            cursor="hand2",
        )
        cb.pack(fill=tk.X, anchor="w")

    def _build_file_section(self, parent: tk.Frame) -> None:
        body = self._card(parent, "📁", "Attachments (Optional)")

        self.files_frame = tk.Frame(body, bg=COLOR_SURFACE)
        self.files_frame.pack(fill=tk.X, pady=(0, 10))

        self.files_label = tk.Label(
            self.files_frame,
            text="No files selected",
            font=("Segoe UI", 9, "italic"),
            fg=COLOR_MUTED,
            bg=COLOR_SURFACE,
            anchor="w",
            justify=tk.LEFT,
        )
        self.files_label.pack(fill=tk.X, anchor="w")

        btn_row = tk.Frame(body, bg=COLOR_SURFACE)
        btn_row.pack(fill=tk.X)

        self.add_files_btn = HoverButton(
            btn_row,
            text="📎  Add Files",
            font=("Segoe UI", 9, "bold"),
            fg="white",
            bg=COLOR_ACCENT,
            hover=COLOR_ACCENT_DARK,
            padx=12,
            pady=6,
            command=self._on_add_files,
        )
        self.add_files_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.clear_files_btn = HoverButton(
            btn_row,
            text="🗑️  Clear",
            font=("Segoe UI", 9),
            fg=COLOR_MUTED,
            bg=COLOR_SECTION,
            hover=COLOR_BORDER,
            padx=12,
            pady=6,
            command=self._on_clear_files,
        )
        self.clear_files_btn.pack(side=tk.LEFT)

    def _on_add_files(self) -> None:
        import subprocess
        ps_script = (
            '[Console]::OutputEncoding = [System.Text.Encoding]::UTF8;'
            'Add-Type -AssemblyName System.Windows.Forms;'
            '$d = New-Object System.Windows.Forms.OpenFileDialog;'
            '$d.Multiselect = $true;'
            '$d.Title = "Select Files to Attach";'
            '$d.Filter = "All Files (*.*)|*.*";'
            'if ($d.ShowDialog() -eq "OK") {'
            '  $d.FileNames -join "|"'
            '}'
        )
        result = subprocess.run(
            ['powershell', '-WindowStyle', 'Hidden', '-Command', ps_script],
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        output = result.stdout.decode('utf-8', errors='replace').strip()
        if output:
            for p in output.split('|'):
                p_str = p.strip()
                if p_str and p_str not in self.files_list:
                    self.files_list.append(p_str)
            self._update_files_display()

    def _on_clear_files(self) -> None:
        self.files_list.clear()
        self._update_files_display()

    def _on_import_csv(self) -> None:
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Select CSV File Containing Numbers",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        if not path:
            return
            
        import csv
        numbers = []
        try:
            with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
                # Use Sniffer to detect delimiter, default to comma
                sample = f.read(2048)
                f.seek(0)
                dialect = csv.excel
                if sample:
                    try:
                        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
                    except Exception:
                        pass
                
                reader = csv.reader(f, dialect)
                rows = list(reader)
                
            if not rows:
                messagebox.showerror("Error", "The CSV file is empty.")
                return
                
            # Heuristics to find the column containing phone numbers
            header = rows[0]
            phone_col_idx = -1
            
            # Common headers for phone numbers (lowercase)
            keywords = ["phone", "mobile", "number", "contact", "recipient", "tel", "cell"]
            for idx, col in enumerate(header):
                col_clean = col.strip().lower()
                if any(kw in col_clean for kw in keywords):
                    phone_col_idx = idx
                    break
            
            start_row = 1 if phone_col_idx != -1 else 0
            if phone_col_idx == -1:
                # Default to first column if no keywords match
                phone_col_idx = 0
                
            for r in rows[start_row:]:
                if len(r) > phone_col_idx:
                    val = r[phone_col_idx].strip()
                    if val:
                        # strip spaces, dashes, parentheses, keep digits and plus sign
                        cleaned = "".join(c for c in val if c.isdigit() or c == "+")
                        if cleaned:
                            numbers.append(cleaned)
                            
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to parse CSV: {exc}")
            return
            
        if not numbers:
            messagebox.showinfo("No Numbers Found", "Could not find any phone numbers in the selected CSV column.")
            return
            
        existing = self.phone_text.get("1.0", tk.END).strip()
        choice = messagebox.askyesnocancel(
            "Import CSV",
            f"Found {len(numbers)} numbers.\n\n"
            "Do you want to OVERWRITE the existing numbers?\n"
            "- Yes: Overwrite existing numbers\n"
            "- No: Append to existing numbers\n"
            "- Cancel: Abort import"
        )
        if choice is None: # Cancel
            return
        elif choice is True: # Yes (Overwrite)
            self.phone_text.delete("1.0", tk.END)
            self.phone_text.insert("1.0", "\n".join(numbers))
        else: # No (Append)
            if existing:
                self.phone_text.insert(tk.END, "\n" + "\n".join(numbers))
            else:
                self.phone_text.insert("1.0", "\n".join(numbers))
                
        self._adjust_phone_height()
        messagebox.showinfo("Success", f"Successfully imported {len(numbers)} number(s).")

    def _update_files_display(self) -> None:
        # Clear all existing widgets in files_frame
        for widget in self.files_frame.winfo_children():
            widget.destroy()

        if not self.files_list:
            lbl = tk.Label(
                self.files_frame,
                text="No files selected",
                font=("Segoe UI", 9, "italic"),
                fg=COLOR_MUTED,
                bg=COLOR_SURFACE,
                anchor="w",
            )
            lbl.pack(fill=tk.X, anchor="w")
        else:
            for idx, p in enumerate(self.files_list):
                # Extract filename from path
                name = str(p).replace("\\", "/").rstrip("/").split("/")[-1]
                if not name:
                    name = str(p)
                row = tk.Frame(self.files_frame, bg=COLOR_SECTION, pady=4)
                row.pack(fill=tk.X, pady=(0, 3))
                row.columnconfigure(0, weight=1)
                # Use grid for reliable side-by-side layout
                name_lbl = tk.Label(
                    row,
                    text=name,
                    font=("Segoe UI", 9),
                    fg=COLOR_TEXT,
                    bg=COLOR_SECTION,
                    anchor="w",
                    padx=8,
                )
                name_lbl.grid(row=0, column=0, sticky="ew")
                del_btn = HoverButton(
                    row,
                    text="x",
                    font=("Segoe UI", 8, "bold"),
                    fg="white",
                    bg="#e74c3c",
                    hover="#c0392b",
                    padx=6,
                    pady=1,
                    command=lambda i=idx: self._remove_file(i),
                )
                del_btn.grid(row=0, column=1, padx=(4, 8))

    def _remove_file(self, index: int) -> None:
        """Remove a single file from the attachments list by index."""
        if 0 <= index < len(self.files_list):
            self.files_list.pop(index)
            self._update_files_display()

    def _build_history_section(self, parent: tk.Frame) -> None:
        body = self._card(parent, "📜", "Sent History")

        table_frame = tk.Frame(body, bg=COLOR_SURFACE)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        tree_scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.history_tree = ttk.Treeview(
            table_frame,
            columns=("time", "recipient", "preview", "status"),
            show="headings",
            yscrollcommand=tree_scroll.set,
            style="Custom.Treeview",
            height=6,
        )
        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.config(command=self.history_tree.yview)

        self.history_tree.tag_configure("batch_even", background=COLOR_SURFACE)
        self.history_tree.tag_configure("batch_odd", background="#1a242a")

        self.history_tree.heading("time", text="Time")
        self.history_tree.heading("recipient", text="Recipient")
        self.history_tree.heading("preview", text="Message/Files")
        self.history_tree.heading("status", text="Status")

        self.history_tree.column("time", width=145, anchor="w", stretch=False)
        self.history_tree.column("recipient", width=135, anchor="w", stretch=False)
        self.history_tree.column("preview", width=250, anchor="w")
        self.history_tree.column("status", width=80, anchor="center", stretch=False)

        btn_row = tk.Frame(body, bg=COLOR_SURFACE)
        btn_row.pack(fill=tk.X)

        self.load_history_btn = HoverButton(
            btn_row,
            text="📥  Load Selected",
            font=("Segoe UI", 9, "bold"),
            fg="white",
            bg=COLOR_ACCENT,
            hover=COLOR_ACCENT_DARK,
            padx=12,
            pady=6,
            command=self._on_load_history_entry,
        )
        self.load_history_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.clear_history_btn = HoverButton(
            btn_row,
            text="🗑️  Clear History",
            font=("Segoe UI", 9),
            fg=COLOR_MUTED,
            bg=COLOR_SECTION,
            hover=COLOR_BORDER,
            padx=12,
            pady=6,
            command=self._on_clear_history,
        )
        self.clear_history_btn.pack(side=tk.LEFT)

        self._refresh_history_tree()

    def _load_history(self) -> list[dict]:
        if not os.path.exists("sent_history.json"):
            return []
        try:
            with open("sent_history.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save_history(self, history: list[dict]) -> None:
        try:
            with open("sent_history.json", "w", encoding="utf-8") as f:
                json.dump(history, f, indent=4, ensure_ascii=False)
        except Exception:
            pass

    def _add_history_entry(self, phone: str, message: str, files: list[str], status: str, time_str: str | None = None, batch_index: int = 0) -> None:
        history = self._load_history()
        preview = ""
        if message:
            preview = message.replace("\n", " ")
            if len(preview) > 40:
                preview = preview[:37] + "..."
        if files:
            files_prev = f"[{len(files)} file(s): " + ", ".join(os.path.basename(f) for f in files) + "]"
            if preview:
                preview = f"{preview} {files_prev}"
            else:
                preview = files_prev

        entry = {
            "time": time_str or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "index": batch_index,
            "recipient": phone,
            "message": message,
            "files": files,
            "preview": preview,
            "status": status
        }
        history.insert(0, entry)
        self._save_history(history[:100])
        self._ui(self._refresh_history_tree)

    def _refresh_history_tree(self) -> None:
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        history = self._load_history()
        
        display_rows = []
        for entry in history:
            rec = entry.get("recipient", "")
            if isinstance(rec, list):
                for sub_idx, sub_rec in enumerate(rec):
                    display_rows.append({
                        "time": entry.get("time", ""),
                        "index": entry.get("index", sub_idx),
                        "recipient": sub_rec,
                        "preview": entry.get("preview", ""),
                        "status": entry.get("status", "")
                    })
            else:
                display_rows.append({
                    "time": entry.get("time", ""),
                    "index": entry.get("index", 0),
                    "recipient": rec,
                    "preview": entry.get("preview", ""),
                    "status": entry.get("status", "")
                })
        
        # Sort display rows by index ascending, then by time descending
        display_rows.sort(key=lambda e: e.get("index", 0))
        display_rows.sort(key=lambda e: e.get("time", ""), reverse=True)
        
        from collections import Counter
        time_counts = Counter(row.get("time", "") for row in display_rows)
        time_seen = {}
        
        current_time = None
        batch_toggle = True
        
        for idx, row in enumerate(display_rows):
            row_time = row.get("time", "")
            total_in_batch = time_counts.get(row_time, 1)
            seen_count = time_seen.get(row_time, 0) + 1
            time_seen[row_time] = seen_count
            
            is_first_in_batch = (seen_count == 1)
            is_last_in_batch = (seen_count == total_in_batch)
            
            if is_first_in_batch:
                batch_toggle = not batch_toggle
                
            tag = "batch_even" if batch_toggle else "batch_odd"
            
            # Format display values: only first row shows time and preview
            disp_time = row_time if is_first_in_batch else ""
            disp_preview = row.get("preview", "") if is_first_in_batch else ""
            disp_status = row.get("status", "")
            
            raw_rec = row.get("recipient", "")
            if total_in_batch > 1:
                if is_first_in_batch:
                    disp_rec = f"┌ {raw_rec}"
                elif is_last_in_batch:
                    disp_rec = f"└ {raw_rec}"
                else:
                    disp_rec = f"├ {raw_rec}"
            else:
                disp_rec = raw_rec
            
            self.history_tree.insert(
                "",
                "end",
                iid=str(idx),
                values=(disp_time, disp_rec, disp_preview, disp_status),
                tags=(tag,)
            )

    def _on_clear_history(self) -> None:
        if messagebox.askyesno("Confirm Clear", "Are you sure you want to clear all sent history?"):
            self._save_history([])
            self._refresh_history_tree()

    def _on_load_history_entry(self) -> None:
        selected = self.history_tree.selection()
        if not selected:
            messagebox.showwarning("Notice", "Please select a history entry to load.")
            return
        idx = int(selected[0])
        history = self._load_history()
        
        display_rows = []
        for entry in history:
            rec = entry.get("recipient", "")
            if isinstance(rec, list):
                for sub_idx, sub_rec in enumerate(rec):
                    display_rows.append({
                        "time": entry.get("time", ""),
                        "index": entry.get("index", sub_idx),
                        "recipient": sub_rec,
                        "message": entry.get("message", ""),
                        "files": entry.get("files", []),
                        "preview": entry.get("preview", ""),
                        "status": entry.get("status", "")
                    })
            else:
                display_rows.append({
                    "time": entry.get("time", ""),
                    "index": entry.get("index", 0),
                    "recipient": rec,
                    "message": entry.get("message", ""),
                    "files": entry.get("files", []),
                    "preview": entry.get("preview", ""),
                    "status": entry.get("status", "")
                })
        
        display_rows.sort(key=lambda e: e.get("index", 0))
        display_rows.sort(key=lambda e: e.get("time", ""), reverse=True)
        
        if idx < len(display_rows):
            target_entry = display_rows[idx]
            target_time = target_entry.get("time", "")
            
            matching_phones = []
            message = target_entry.get("message", "")
            files = list(target_entry.get("files", []))
            
            for row in display_rows:
                if row.get("time") == target_time:
                    p = row.get("recipient", "")
                    if p:
                        matching_phones.append(p)
            
            unique_phones = []
            for p in matching_phones:
                if p not in unique_phones:
                    unique_phones.append(p)
                    
            self.phone_text.delete("1.0", tk.END)
            self.phone_text.insert("1.0", "\n".join(unique_phones))
            self.message_text.delete("1.0", tk.END)
            self.message_text.insert("1.0", message)
            self.files_list = files
            self._update_files_display()
            self._update_char_count()
            self._adjust_phone_height()
            messagebox.showinfo("Success", f"Loaded {len(unique_phones)} contact(s) from history batch.")

    def _build_schedule_section(self, parent: tk.Frame) -> None:
        body = self._card(parent, "🕐", "When to send")

        toggle_row = tk.Frame(body, bg=COLOR_SURFACE)
        toggle_row.pack(fill=tk.X, pady=(0, 12))
        toggle_row.columnconfigure(0, weight=1)
        toggle_row.columnconfigure(1, weight=1)

        self.when_var = tk.StringVar(value="now")
        self._pill_now = tk.Label(
            toggle_row,
            text="⚡  Send now",
            font=("Segoe UI", 10, "bold"),
            bg=COLOR_ACCENT,
            fg="white",
            padx=16,
            pady=10,
            cursor="hand2",
        )
        self._pill_now.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self._pill_now.bind("<Button-1>", lambda _e: self._set_when("now"))

        self._pill_schedule = tk.Label(
            toggle_row,
            text="📅  Schedule",
            font=("Segoe UI", 10),
            bg=COLOR_SECTION,
            fg=COLOR_MUTED,
            padx=16,
            pady=10,
            cursor="hand2",
        )
        self._pill_schedule.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        self._pill_schedule.bind("<Button-1>", lambda _e: self._set_when("schedule"))

        self.schedule_panel = tk.Frame(body, bg=COLOR_ACCENT_LIGHT, padx=14, pady=12)
        self.schedule_panel.pack(fill=tk.X)

        tk.Label(
            self.schedule_panel,
            text="Pick date and time",
            font=("Segoe UI", 9, "bold"),
            fg=COLOR_HEADER_TOP,
            bg=COLOR_ACCENT_LIGHT,
        ).pack(anchor="w", pady=(0, 8))

        fields = tk.Frame(self.schedule_panel, bg=COLOR_ACCENT_LIGHT)
        fields.pack(fill=tk.X)
        fields.columnconfigure(0, weight=1)
        fields.columnconfigure(1, weight=1)

        col1 = tk.Frame(fields, bg=COLOR_ACCENT_LIGHT)
        col1.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        col1.columnconfigure(0, weight=1)
        tk.Label(col1, text="Date", font=("Segoe UI", 8), fg=COLOR_MUTED, bg=COLOR_ACCENT_LIGHT).pack(
            anchor="w"
        )
        self.date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        self.date_entry = tk.Entry(
            col1,
            textvariable=self.date_var,
            font=("Segoe UI", 11),
            relief=tk.FLAT,
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT,
            insertbackground=COLOR_ACCENT,
        )
        self.date_entry.pack(fill=tk.X, ipady=8, ipadx=10, pady=(4, 0))

        col2 = tk.Frame(fields, bg=COLOR_ACCENT_LIGHT)
        col2.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        col2.columnconfigure(0, weight=1)
        tk.Label(col2, text="Time (24h)", font=("Segoe UI", 8), fg=COLOR_MUTED, bg=COLOR_ACCENT_LIGHT).pack(
            anchor="w"
        )
        self.time_var = tk.StringVar(value=datetime.now().strftime("%H:%M"))
        self.time_entry = tk.Entry(
            col2,
            textvariable=self.time_var,
            font=("Segoe UI", 11),
            relief=tk.FLAT,
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT,
            insertbackground=COLOR_ACCENT,
        )
        self.time_entry.pack(fill=tk.X, ipady=8, ipadx=10, pady=(4, 0))

    def _set_when(self, mode: str) -> None:
        self.when_var.set(mode)
        self._update_when_toggle()
        self._toggle_schedule_fields()

    def _update_when_toggle(self) -> None:
        if self.when_var.get() == "now":
            self._pill_now.configure(bg=COLOR_ACCENT, fg="white", font=("Segoe UI", 10, "bold"))
            self._pill_schedule.configure(bg=COLOR_SECTION, fg=COLOR_MUTED, font=("Segoe UI", 10))
            self.schedule_panel.pack_forget()
        else:
            self._pill_schedule.configure(bg=COLOR_ACCENT, fg="white", font=("Segoe UI", 10, "bold"))
            self._pill_now.configure(bg=COLOR_SECTION, fg=COLOR_MUTED, font=("Segoe UI", 10))
            self.schedule_panel.pack(fill=tk.X)

    def _build_options_section(self, parent: tk.Frame) -> None:
        body = self._card(parent, "⚙️", "Options")
        self.open_only_var = tk.BooleanVar(value=False)
        self.delay_var = tk.DoubleVar(value=5.0)
        self._styled_check(
            body,
            "Open chat only — fill message but don't auto-send",
            self.open_only_var,
        )

        # Anti-Spam Delay Information
        bulk_delay_row = tk.Frame(body, bg=COLOR_SECTION, padx=12, pady=10)
        bulk_delay_row.pack(fill=tk.X, pady=(8, 0))

        tk.Label(
            bulk_delay_row,
            text="🛡️ Anti-Spam Protection active",
            font=("Segoe UI", 9, "bold"),
            fg=COLOR_ACCENT,
            bg=COLOR_SECTION,
        ).pack(anchor="w")

        tk.Label(
            bulk_delay_row,
            text="A randomized delay of 4 to 8 seconds is automatically applied\nbetween contacts to mimic human typing and prevent account bans.",
            font=("Segoe UI", 8),
            fg=COLOR_MUTED,
            bg=COLOR_SECTION,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(2, 0))
        
        self.bulk_delay_var = tk.DoubleVar(value=6.0)

    def _build_action_bar(self) -> None:
        bar = tk.Frame(self.root, bg=COLOR_SURFACE, highlightbackground=COLOR_BORDER, highlightthickness=1)
        bar.pack(fill=tk.X, side=tk.BOTTOM)

        inner = tk.Frame(bar, bg=COLOR_SURFACE, padx=24, pady=14)
        inner.pack(fill=tk.BOTH, expand=True)
        inner.columnconfigure(0, weight=1)

        self.send_btn = HoverButton(
            inner,
            text="  ✓  Send message  ",
            font=("Segoe UI", 12, "bold"),
            fg="white",
            bg=COLOR_ACCENT,
            hover=COLOR_ACCENT_DARK,
            padx=8,
            pady=12,
            command=self._on_send,
        )
        self.send_btn.pack(fill=tk.X)

        # Progress panel (initially hidden)
        self.progress_frame = tk.Frame(inner, bg=COLOR_SURFACE)
        
        self.progress_label = tk.Label(
            self.progress_frame,
            text="Progress: 0/0 (0%)  |  ETC: --:--",
            font=("Segoe UI", 9, "bold"),
            fg=COLOR_TEXT,
            bg=COLOR_SURFACE,
        )
        self.progress_label.pack(fill=tk.X, pady=(0, 6))

        # Modern flat progress bar on Canvas
        self.progress_canvas = tk.Canvas(
            self.progress_frame,
            height=6,
            bg=COLOR_SECTION,
            highlightthickness=0,
            bd=0,
        )
        self.progress_canvas.pack(fill=tk.X, pady=(0, 6))
        self.progress_rect = self.progress_canvas.create_rectangle(0, 0, 0, 6, fill=COLOR_ACCENT, width=0)

        self.cancel_btn = HoverButton(
            inner,
            text="Cancel",
            font=("Segoe UI", 10),
            fg=COLOR_MUTED,
            bg=COLOR_SECTION,
            hover=COLOR_BORDER,
            pady=8,
            command=self._on_cancel,
        )
        self.cancel_btn.pack(fill=tk.X, pady=(8, 0))
        self.cancel_btn.set_enabled(False)

    def _build_footer(self) -> None:
        foot = tk.Frame(self.root, bg=COLOR_HEADER_TOP, height=36)
        foot.pack(fill=tk.X, side=tk.BOTTOM)

        inner = tk.Frame(foot, bg=COLOR_HEADER_TOP)
        inner.pack(fill=tk.BOTH, expand=True, padx=24, pady=8)

        self._status_dot = tk.Label(inner, text="●", font=("Segoe UI", 10), fg=COLOR_STATUS_IDLE, bg=COLOR_HEADER_TOP)
        self._status_dot.pack(side=tk.LEFT)

        self.status_var = tk.StringVar(value="Ready to send")
        tk.Label(
            inner,
            textvariable=self.status_var,
            font=("Segoe UI", 9),
            fg=COLOR_MUTED,
            bg=COLOR_HEADER_TOP,
        ).pack(side=tk.LEFT, padx=(8, 0))

    def _build_developer_footer(self, parent: tk.Frame) -> None:
        """Developer credits — placed at the end of scrollable content."""
        dev_bg = COLOR_BG
        dev = tk.Frame(parent, bg=dev_bg)
        dev.pack(fill=tk.X, pady=(10, 0))

        inner = tk.Frame(dev, bg=dev_bg, padx=20, pady=10)
        inner.pack(fill=tk.X)
        inner.columnconfigure(0, weight=1)

        tk.Label(
            inner,
            text="Developed by ALAN KJ",
            font=("Segoe UI", 9, "bold"),
            fg=COLOR_TEXT,
            bg=dev_bg,
        ).grid(row=0, column=0, sticky="w")

        links = tk.Frame(inner, bg=dev_bg)
        links.grid(row=1, column=0, sticky="w", pady=(4, 0))

        ig = tk.Label(
            links,
            text="Instagram: @_storiesof.kj_",
            font=("Segoe UI", 8),
            fg=COLOR_ACCENT,
            bg=dev_bg,
            cursor="hand2",
        )
        ig.pack(side=tk.LEFT)
        ig.bind(
            "<Button-1>",
            lambda _e: webbrowser.open("https://www.instagram.com/_storiesof.kj_"),
        )
        ig.bind("<Enter>", lambda _e: ig.configure(font=("Segoe UI", 8, "underline")))
        ig.bind("<Leave>", lambda _e: ig.configure(font=("Segoe UI", 8)))

        sep = lambda: tk.Label(
            links, text="   ·   ", font=("Segoe UI", 8), fg=COLOR_MUTED, bg=dev_bg
        ).pack(side=tk.LEFT)

        sep()
        gh = tk.Label(
            links,
            text="GitHub: alankj07",
            font=("Segoe UI", 8),
            fg=COLOR_ACCENT,
            bg=dev_bg,
            cursor="hand2",
        )
        gh.pack(side=tk.LEFT)
        gh.bind("<Button-1>", lambda _e: webbrowser.open("https://github.com/alankj07"))
        gh.bind("<Enter>", lambda _e: gh.configure(font=("Segoe UI", 8, "underline")))
        gh.bind("<Leave>", lambda _e: gh.configure(font=("Segoe UI", 8)))

        sep()
        wa = tk.Label(
            links,
            text="WhatsApp: +91 8921084834",
            font=("Segoe UI", 8),
            fg=COLOR_ACCENT,
            bg=dev_bg,
            cursor="hand2",
        )
        wa.pack(side=tk.LEFT)
        wa.bind(
            "<Button-1>",
            lambda _e: webbrowser.open("https://wa.me/918921084834"),
        )
        wa.bind("<Enter>", lambda _e: wa.configure(font=("Segoe UI", 8, "underline")))
        wa.bind("<Leave>", lambda _e: wa.configure(font=("Segoe UI", 8)))

    def _update_char_count(self, _event: tk.Event | None = None) -> None:
        n = len(self.message_text.get("1.0", "end-1c"))
        self.char_count_var.set(f"{n} character{'s' if n != 1 else ''}")

    def _toggle_schedule_fields(self) -> None:
        scheduled = self.when_var.get() == "schedule"
        state = tk.NORMAL if scheduled else tk.DISABLED
        bg = COLOR_SURFACE if scheduled else COLOR_DISABLED
        for entry in (self.date_entry, self.time_entry):
            entry.configure(state=state, bg=bg)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.send_btn.set_enabled(not busy)
        self.cancel_btn.set_enabled(busy)
        self._status_dot.configure(fg=COLOR_STATUS_BUSY if busy else COLOR_STATUS_IDLE)

        # Show/hide progress bar
        if busy:
            try:
                self.cancel_btn.pack_forget()
                self.progress_frame.pack(fill=tk.X, pady=(8, 0))
                self.cancel_btn.pack(fill=tk.X, pady=(8, 0))
                self._update_progress(0, 1)  # Reset visual
            except Exception:
                pass
            
            # Show floating progress window and minimize main window
            if not self.floating_window:
                self.floating_window = FloatingProgressWindow(self)
                self.root.iconify()
        else:
            try:
                self.progress_frame.pack_forget()
            except Exception:
                pass
                
            # Transition floating window to completed/cancelled state
            if self.floating_window:
                status_txt = self.status_var.get()
                if "cancelled" in status_txt.lower():
                    self.floating_window.set_completed_state("Sending cancelled.")
                elif "completed with" in status_txt.lower() or "error" in status_txt.lower():
                    self.floating_window.set_completed_state("Completed with errors.")
                else:
                    self.floating_window.set_completed_state("Completed successfully.")

    def _tick_etc(self) -> None:
        if not self._busy:
            return
        elapsed = time.time() - self.send_start_time
        remaining = self.total_est_time - elapsed
        if remaining < 0:
            remaining = 0
        self._ui(lambda: self._update_progress(self.current_idx, self.total_contacts, remaining))
        self.root.after(1000, self._tick_etc)

    def _update_progress(self, current: int, total: int, est_seconds_left: float | None = None) -> None:
        if total <= 0:
            total = 1
        pct = current / total
        
        # Update progress bar canvas width
        try:
            self.progress_canvas.update_idletasks()
            canvas_width = self.progress_canvas.winfo_width()
            if canvas_width <= 1:
                canvas_width = 300
            new_width = int(canvas_width * pct)
            self.progress_canvas.coords(self.progress_rect, 0, 0, new_width, 6)
        except Exception:
            pass
            
        # Formulate Estimated Time of Completion (ETC) text
        etc_text = "--:--"
        if est_seconds_left is not None:
            if est_seconds_left <= 0:
                etc_text = "0s"
            elif est_seconds_left < 60:
                etc_text = f"{int(est_seconds_left)}s"
            else:
                mins = int(est_seconds_left // 60)
                secs = int(est_seconds_left % 60)
                etc_text = f"{mins}m {secs}s"
                
        percent_str = f"{int(pct * 100)}%"
        try:
            self.progress_label.configure(text=f"Progress: {current}/{total} ({percent_str})  |  ETC: {etc_text}")
        except Exception:
            pass

        # Update floating window progress info
        if self.floating_window:
            self.floating_window.update_progress_info(current, total, pct, etc_text)

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)
        if "success" in text.lower() or "sent" in text.lower():
            self._status_dot.configure(fg=COLOR_STATUS_OK)
        elif "error" in text.lower() or "fail" in text.lower():
            self._status_dot.configure(fg="#ea0038")
        elif "send" in text.lower() and "in" in text.lower():
            self._status_dot.configure(fg=COLOR_STATUS_BUSY)

        # Update floating window status
        if self.floating_window:
            self.floating_window.update_status(text)

    def _ui(self, fn) -> None:
        self.root.after(0, fn)

    def _validate_form(self) -> tuple[list[str], str, str, datetime | None, bool, float, float, list[str]]:
        raw_phones = self.phone_text.get("1.0", tk.END).strip()
        if not raw_phones:
            raise ValueError("Please enter at least one phone number.")

        phones = []
        for line in raw_phones.replace(",", "\n").split("\n"):
            line = line.strip()
            if line:
                phones.append(line)

        if not phones:
            raise ValueError("Please enter at least one valid phone number.")

        message = self.message_text.get("1.0", tk.END).strip()
        if not message and not self.files_list:
            raise ValueError("Please enter a message or select at least one file.")

        if message and self.timestamp_var.get():
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            message = f"{message}\n\n[{stamp}]"

        country = self.country_var.get().strip() or "91"
        for p in phones:
            normalize_phone(p, country)

        send_at: datetime | None = None
        if self.when_var.get() == "schedule":
            try:
                send_at = datetime.combine(
                    _parse_date(self.date_var.get()),
                    _parse_time(self.time_var.get()),
                )
            except ValueError as exc:
                raise ValueError(str(exc)) from exc
            if send_at <= datetime.now():
                raise ValueError("Scheduled time must be in the future.")

        skip_send = self.open_only_var.get()
        try:
            delay = float(self.delay_var.get())
            if delay < 0.5:
                delay = 0.5
        except Exception:
            delay = 5.0

        try:
            bulk_delay = float(self.bulk_delay_var.get())
            if bulk_delay < 1.0:
                bulk_delay = 1.0
        except Exception:
            bulk_delay = 5.0

        return phones, message, country, send_at, skip_send, delay, bulk_delay, self.files_list

    def _on_send(self) -> None:
        if self._busy:
            return
        try:
            phones, message, country, send_at, skip_send, delay, bulk_delay, files = self._validate_form()
        except ValueError as exc:
            messagebox.showerror("Invalid input", str(exc))
            return

        summary = f"Send to {len(phones)} recipient(s)?"
        if files:
            import os
            filenames = ", ".join(os.path.basename(f) for f in files)
            summary += f"\n\nFiles ({len(files)}): {filenames}"
        if send_at:
            summary += f"\n\nScheduled: {send_at.strftime('%Y-%m-%d %H:%M')}"
        if skip_send:
            summary += "\n\nMode: open chat only (no auto-send)"
        if not messagebox.askyesno("Confirm bulk send", summary):
            return

        gui_hwnd = self.root.winfo_id()
        self._stop_event.clear()
        self._set_busy(True)
        self._set_status("Starting…")

        def worker() -> None:
            def status(msg: str) -> None:
                self._ui(lambda m=msg: self._set_status(m))

            try:
                batch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                hwnd_preloaded = None

                if send_at:
                    def should_stop() -> bool:
                        return self._stop_event.is_set()

                    # Pre-load WhatsApp 15 seconds before send_at
                    prep_at = send_at - timedelta(seconds=15)
                    
                    # Custom countdown wait until prep_at (saying "Opening WhatsApp in __ sec/min")
                    while datetime.now() < prep_at:
                        if should_stop():
                            self._ui(lambda: self._set_status("Cancelled."))
                            for i_rem, phone in enumerate(phones):
                                self._add_history_entry(phone, message, files, "Cancelled", batch_time, i_rem)
                            return
                        diff = prep_at - datetime.now()
                        seconds = diff.total_seconds()
                        if seconds > 60:
                            status(f"Opening WhatsApp in {int(seconds // 60)} min")
                            time.sleep(min(5, seconds - 60))
                        else:
                            status(f"Opening WhatsApp in {int(seconds)} sec")
                            time.sleep(0.5)

                    # Pre-load WhatsApp now (within 15 seconds of target time)
                    if not self._stop_event.is_set():
                        first_phone = phones[0]
                        self._ui(lambda p=first_phone: self._set_status(f"Pre-opening WhatsApp for +{p}…"))
                        hwnd_preloaded = prepare_whatsapp_chat(first_phone, country, on_status=status, show_cmd=7)
                        
                        # Immediately restore focus to the GUI window to keep WhatsApp in the background
                        if hwnd_preloaded:
                            try:
                                force_foreground(gui_hwnd)
                            except Exception:
                                pass

                    # Custom countdown wait until send_at (saying "Sending in __ sec")
                    while datetime.now() < send_at:
                        if should_stop():
                            self._ui(lambda: self._set_status("Cancelled."))
                            for i_rem, phone in enumerate(phones):
                                self._add_history_entry(phone, message, files, "Cancelled", batch_time, i_rem)
                            return
                        diff = send_at - datetime.now()
                        seconds = diff.total_seconds()
                        status(f"Sending in {int(seconds)} sec")
                        time.sleep(0.5)

                total = len(phones)
                success_count = 0
                failed_count = 0

                # Initialize progress variables
                self.total_contacts = total
                self.current_idx = 0
                
                # Estimate time per contact:
                # - Prepare: delay (5.0s) + 1.5s
                # - Text send: 1.5s (if message)
                # - Files send: 3.5s (if files)
                self.t_per_contact = delay + 1.5
                if message:
                    self.t_per_contact += 1.5
                if files:
                    self.t_per_contact += 3.5
                
                # Average delay between contacts is 6.0s (random 4-8s)
                avg_bulk_delay = 6.0
                
                if send_at and hwnd_preloaded:
                    self.total_est_time = (self.t_per_contact - delay) + (total - 1) * self.t_per_contact + max(0, total - 1) * avg_bulk_delay
                else:
                    self.total_est_time = total * self.t_per_contact + max(0, total - 1) * avg_bulk_delay
                
                self.send_start_time = time.time()
                self._ui(lambda: self._tick_etc())

                for idx, phone in enumerate(phones):
                    if self._stop_event.is_set():
                        self._ui(lambda: self._set_status("Cancelled."))
                        for i_rem, rem_phone in enumerate(phones[idx:]):
                            self._add_history_entry(rem_phone, message, files, "Cancelled", batch_time, idx + i_rem)
                        break

                    normalized = normalize_phone(phone, country)
                    self._ui(lambda p=normalized, i=idx+1: self._set_status(f"Sending to +{p} ({i}/{total})…"))

                    # If this is the first contact, and we successfully pre-loaded the chat, use it!
                    if idx == 0 and send_at and hwnd_preloaded:
                        ok = send_whatsapp_prepared(
                            hwnd_preloaded,
                            message,
                            skip_send=skip_send,
                            on_status=status,
                            wait_delay=0.5,  # Minimal delay because it's pre-loaded
                            files=files,
                        )
                    else:
                        ok = send_whatsapp_message(
                            phone,
                            message,
                            default_country_code=country,
                            skip_send=skip_send,
                            on_status=status,
                            wait_delay=delay,
                            files=files,
                        )

                    if ok:
                        success_count += 1
                        self._add_history_entry(phone, message, files, "Success", batch_time, idx)
                    else:
                        failed_count += 1
                        self._add_history_entry(phone, message, files, "Failed", batch_time, idx)

                    # Update index and recalibrate remaining time
                    self.current_idx = idx + 1
                    rem_contacts = total - self.current_idx
                    if rem_contacts > 0:
                        self.total_est_time = rem_contacts * self.t_per_contact + max(0, rem_contacts - 1) * 6.0
                        self.send_start_time = time.time()
                    else:
                        self.total_est_time = 0.0

                    if idx < total - 1 and not self._stop_event.is_set():
                        # Pick a random delay between 4.0 and 8.0 seconds to mimic human typing & prevent bans
                        import random
                        actual_delay = random.uniform(4.0, 8.0)
                        
                        wait_steps = int(actual_delay / 0.5)
                        for step in range(wait_steps):
                            if self._stop_event.is_set():
                                break
                            self._ui(lambda current=step*0.5, total_w=actual_delay: self._set_status(f"Waiting between contacts ({current:.1f}s/{total_w:.1f}s)…"))
                            time.sleep(0.5)

                if not self._stop_event.is_set():
                    if failed_count > 0:
                        msg_summary = f"Process completed: {success_count} succeeded, {failed_count} failed.\n\nCheck history/logs for details."
                        self._ui(lambda: messagebox.showwarning("Done with errors", msg_summary))
                        self._ui(lambda: self._set_status(f"Completed with {failed_count} error(s)."))
                    else:
                        self._ui(lambda: messagebox.showinfo("Done", "All messages processed successfully."))
                        self._ui(lambda: self._set_status("Completed successfully."))
            except ValueError as exc:
                err_msg = str(exc)
                self._ui(lambda msg=err_msg: messagebox.showerror("Error", msg))
            except Exception as exc:
                err_msg = str(exc)
                self._ui(lambda msg=err_msg: messagebox.showerror("Error", msg))
            finally:
                self._ui(lambda: self._set_busy(False))

        self._worker = threading.Thread(target=worker, daemon=True)
        self._worker.start()

    def _on_cancel(self) -> None:
        if self._busy:
            self._stop_event.set()
            self._set_status("Cancelling…")

    def _on_close(self) -> None:
        if self._busy:
            if messagebox.askyesno("Exit", "A task is running. Cancel and exit?"):
                self._stop_event.set()
                self.root.destroy()
        else:
            self.root.destroy()

def main() -> None:
    import os
    import sys
    import ctypes
    try:
        app_id = "alankj.whatsappsender.gui.1.0"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass

    root = tk.Tk()
    try:
        if hasattr(sys, '_MEIPASS'):
            icon_path = os.path.join(sys._MEIPASS, 'app_icon.ico')
        else:
            icon_path = 'app_icon.ico'
        root.iconbitmap(default=icon_path) 
    except Exception:
        pass

    WhatsAppSenderApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
