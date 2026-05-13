# widgets.py — reusable Tkinter widgets

import re
import tkinter as tk
from tkinter import ttk, scrolledtext
from config import (
    PALETTE, FONT_LABEL, FONT_BODY, FONT_SMALL,
    FONT_TINY, FONT_MONO, PLACEHOLDER_TEXT
)


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def divider(parent, padx=24, pady=(14, 0)):
    tk.Frame(parent, bg=PALETTE["border"], height=1).pack(
        fill="x", padx=padx, pady=pady
    )


def neon_button(parent, text, command, color=None, width=None):
    """Flat button with neon accent styling."""
    bg  = color or PALETTE["accent2"]
    btn = tk.Button(
        parent, text=text,
        font=FONT_LABEL,
        bg=bg, fg=PALETTE["highlight"],
        activebackground=PALETTE["border2"],
        activeforeground=PALETTE["highlight"],
        relief="flat", cursor="hand2",
        padx=14, pady=7,
        command=command,
    )
    if width:
        btn.config(width=width)
    return btn


def ghost_button(parent, text, command):
    return tk.Button(
        parent, text=text,
        font=FONT_SMALL,
        bg=PALETTE["surface2"], fg=PALETTE["text_dim"],
        activebackground=PALETTE["border"],
        activeforeground=PALETTE["text"],
        relief="flat", cursor="hand2",
        padx=12, pady=6,
        command=command,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Input widget
# ══════════════════════════════════════════════════════════════════════════════

class LabeledTextInput(tk.Frame):
    """Bordered scrolled-text with placeholder."""

    def __init__(self, parent, on_change=None, **kwargs):
        super().__init__(parent, bg=PALETTE["bg"])

        hdr = tk.Frame(self, bg=PALETTE["bg"])
        hdr.pack(fill="x")

        tk.Label(
            hdr, text="◈  INPUT TEXT",
            font=FONT_LABEL, bg=PALETTE["bg"], fg=PALETTE["accent"]
        ).pack(side="left")

        tk.Label(
            hdr, text="Ctrl+Enter to run",
            font=FONT_TINY, bg=PALETTE["bg"], fg=PALETTE["text_muted"]
        ).pack(side="right")

        border = tk.Frame(self, bg=PALETTE["accent2"], bd=0)
        border.pack(fill="x", pady=(5, 0))

        self._box = scrolledtext.ScrolledText(
            border,
            height=7, wrap=tk.WORD,
            font=FONT_BODY,
            bg=PALETTE["surface"], fg=PALETTE["text"],
            insertbackground=PALETTE["accent"],
            relief="flat", bd=10,
            selectbackground=PALETTE["accent2"],
            spacing3=3,
        )
        self._box.pack(fill="x", padx=1, pady=1)

        self._box.insert("1.0", PLACEHOLDER_TEXT)
        self._box.config(fg=PALETTE["text_muted"])
        self._box.bind("<FocusIn>",  self._clear_ph)
        self._box.bind("<FocusOut>", self._restore_ph)
        self._on_change = on_change
        if on_change:
            self._box.bind("<KeyRelease>", self._handle_change)

    def bind_key(self, seq, cb):
        self._box.bind(seq, cb)

    def get_text(self):
        raw = self._box.get("1.0", tk.END).strip()
        return "" if raw == PLACEHOLDER_TEXT.strip() else raw

    def set_text(self, text):
        self._box.delete("1.0", tk.END)
        self._box.insert("1.0", text)
        self._box.config(fg=PALETTE["text"])
        if self._on_change:
            self._handle_change(None)

    def highlight_sentiment(self, positive_words, negative_words):
        self._box.tag_remove("positive", "1.0", tk.END)
        self._box.tag_remove("negative", "1.0", tk.END)
        self._box.tag_config("positive", foreground=PALETTE["positive"])
        self._box.tag_config("negative", foreground=PALETTE["negative"])
        content = self._box.get("1.0", tk.END)
        if content.strip() == PLACEHOLDER_TEXT.strip():
            return

        def apply_tags(words, tag):
            for word in words:
                if not word:
                    continue
                start = "1.0"
                pattern = rf"\b{re.escape(word)}\b"
                while True:
                    pos = self._box.search(pattern, start, nocase=1, regexp=True)
                    if not pos:
                        break
                    end = f"{pos}+{len(word)}c"
                    self._box.tag_add(tag, pos, end)
                    start = end

        apply_tags(positive_words, "positive")
        apply_tags(negative_words, "negative")

    def clear(self):
        self._box.delete("1.0", tk.END)
        self._restore_ph(None)

    def _clear_ph(self, _e):
        if self._box.get("1.0", tk.END).strip() == PLACEHOLDER_TEXT.strip():
            self._box.delete("1.0", tk.END)
            self._box.config(fg=PALETTE["text"])

    def _restore_ph(self, _e):
        if not self._box.get("1.0", tk.END).strip():
            self._box.insert("1.0", PLACEHOLDER_TEXT)
            self._box.config(fg=PALETTE["text_muted"])

    def _handle_change(self, _e):
        if self._on_change:
            self._on_change()


# ══════════════════════════════════════════════════════════════════════════════
# Result panel
# ══════════════════════════════════════════════════════════════════════════════

class ResultPanel(tk.Frame):
    """Shows label + score + animated bar."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=PALETTE["bg"])

        card = tk.Frame(self, bg=PALETTE["surface2"], bd=0)
        card.pack(fill="x")

        # top strip (accent line)
        self._strip = tk.Frame(card, bg=PALETTE["accent2"], height=3)
        self._strip.pack(fill="x")

        inner = tk.Frame(card, bg=PALETTE["surface2"])
        inner.pack(fill="x", padx=20, pady=14)

        # left: big label
        left = tk.Frame(inner, bg=PALETTE["surface2"])
        left.pack(side="left", fill="y")

        self._icon_var = tk.StringVar(value="◌")
        tk.Label(
            left, textvariable=self._icon_var,
            font=("Consolas", 36), bg=PALETTE["surface2"], fg=PALETTE["text_muted"]
        ).pack(side="left", padx=(0, 14))

        label_col = tk.Frame(left, bg=PALETTE["surface2"])
        label_col.pack(side="left")

        tk.Label(
            label_col, text="RESULT",
            font=FONT_TINY, bg=PALETTE["surface2"], fg=PALETTE["text_muted"]
        ).pack(anchor="w")

        self._sentiment_var = tk.StringVar(value="AWAITING INPUT")
        self._sentiment_lbl = tk.Label(
            label_col, textvariable=self._sentiment_var,
            font=("Consolas", 20, "bold"),
            bg=PALETTE["surface2"], fg=PALETTE["text_muted"]
        )
        self._sentiment_lbl.pack(anchor="w")

        # right: score
        right = tk.Frame(inner, bg=PALETTE["surface2"])
        right.pack(side="right", anchor="e")

        tk.Label(
            right, text="CONFIDENCE",
            font=FONT_TINY, bg=PALETTE["surface2"], fg=PALETTE["text_muted"]
        ).pack(anchor="e")

        self._score_var = tk.StringVar(value="—")
        tk.Label(
            right, textvariable=self._score_var,
            font=("Consolas", 26, "bold"),
            bg=PALETTE["surface2"], fg=PALETTE["text"]
        ).pack(anchor="e")

        # progress bar
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Result.Horizontal.TProgressbar",
            troughcolor=PALETTE["border"],
            background=PALETTE["accent2"],
            thickness=8,
        )
        self._bar = ttk.Progressbar(
            card, style="Result.Horizontal.TProgressbar",
            orient="horizontal", mode="determinate",
            maximum=100, value=0
        )
        self._bar.pack(fill="x", padx=0, pady=(0, 0))

    def update(self, label, score):
        is_pos = label == "POSITIVE"
        color  = PALETTE["positive"] if is_pos else PALETTE["negative"]
        icon   = "▲" if is_pos else "▼"
        self._icon_var.set(icon)
        self._sentiment_var.set(label)
        self._sentiment_lbl.config(fg=color)
        self._score_var.set(f"{score*100:.1f}%")
        self._bar["value"] = score * 100
        self._strip.config(bg=color)
        style = ttk.Style()
        style.configure("Result.Horizontal.TProgressbar", background=color)

    def reset(self):
        self._icon_var.set("◌")
        self._sentiment_var.set("AWAITING INPUT")
        self._sentiment_lbl.config(fg=PALETTE["text_muted"])
        self._score_var.set("—")
        self._bar["value"] = 0
        self._strip.config(bg=PALETTE["accent2"])


# ══════════════════════════════════════════════════════════════════════════════
# History panel
# ══════════════════════════════════════════════════════════════════════════════

class HistoryPanel(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=PALETTE["bg"])

        hdr = tk.Frame(self, bg=PALETTE["bg"])
        hdr.pack(fill="x", pady=(0, 6))

        tk.Label(
            hdr, text="◈  SESSION LOG",
            font=FONT_LABEL, bg=PALETTE["bg"], fg=PALETTE["accent"]
        ).pack(side="left")

        self._count_var = tk.StringVar(value="0 entries")
        tk.Label(
            hdr, textvariable=self._count_var,
            font=FONT_TINY, bg=PALETTE["bg"], fg=PALETTE["text_muted"]
        ).pack(side="left", padx=8)

        ghost_button(hdr, "✕ Clear", self.clear).pack(side="right")

        canvas_frame = tk.Frame(self, bg=PALETTE["bg"])
        canvas_frame.pack(fill="both", expand=True)

        self._canvas = tk.Canvas(
            canvas_frame, bg=PALETTE["bg"], highlightthickness=0
        )
        sb = ttk.Scrollbar(canvas_frame, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._inner = tk.Frame(self._canvas, bg=PALETTE["bg"])
        self._win   = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")

        self._inner.bind("<Configure>", lambda e: self._canvas.configure(
            scrollregion=self._canvas.bbox("all")
        ))
        self._canvas.bind("<Configure>", lambda e: self._canvas.itemconfig(
            self._win, width=e.width
        ))
        self._canvas.bind_all("<MouseWheel>", lambda e: self._canvas.yview_scroll(
            int(-1*(e.delta/120)), "units"
        ))
        self._count = 0
        self._entries = []

    def add(self, text, label, score, timestamp=None):
        self._count += 1
        self._count_var.set(f"{self._count} entr{'y' if self._count==1 else 'ies'}")
        is_pos = label == "POSITIVE"
        color  = PALETTE["positive"] if is_pos else PALETTE["negative"]
        icon   = "▲" if is_pos else "▼"
        timestamp = timestamp or None

        self._entries.append((text, label, score, timestamp))

        row = tk.Frame(self._inner, bg=PALETTE["surface"], pady=0)
        row.pack(fill="x", pady=(0, 3))

        # left accent bar
        tk.Frame(row, bg=color, width=3).pack(side="left", fill="y")

        body = tk.Frame(row, bg=PALETTE["surface"])
        body.pack(side="left", fill="x", expand=True, padx=10, pady=8)

        top = tk.Frame(body, bg=PALETTE["surface"])
        top.pack(fill="x")

        tk.Label(
            top, text=f"{icon} {label}",
            font=("Consolas", 9, "bold"), bg=PALETTE["surface"], fg=color
        ).pack(side="left")

        tk.Label(
            top, text=f"{score*100:.1f}%",
            font=FONT_TINY, bg=PALETTE["surface"], fg=PALETTE["text_dim"]
        ).pack(side="left", padx=8)

        tk.Label(
            top, text=f"#{self._count}",
            font=FONT_TINY, bg=PALETTE["surface"], fg=PALETTE["text_muted"]
        ).pack(side="right")

        preview = text[:90].replace("\n", " ")
        if len(text) > 90:
            preview += "…"
        tk.Label(
            body, text=preview,
            font=FONT_TINY, bg=PALETTE["surface"], fg=PALETTE["text_dim"],
            anchor="w", wraplength=500
        ).pack(fill="x", pady=(2, 0))

    def clear(self):
        for w in self._inner.winfo_children():
            w.destroy()
        self._count = 0
        self._count_var.set("0 entries")
        self._entries = []