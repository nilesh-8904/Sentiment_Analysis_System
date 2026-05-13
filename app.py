# app.py — main application window with modern UI

import re
import textwrap
import tkinter as tk
import threading
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import csv
import os

try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

from config import PALETTE, FONT_TITLE, FONT_LABEL, FONT_SMALL, FONT_BODY, EMOTION_LABELS, POSITIVE_WORDS, NEGATIVE_WORDS
from extras import translate_to_english, summarize_text, detect_fake_review, extract_text_from_file, extract_texts_from_file
from model import SentimentModel
from widgets import LabeledTextInput, ResultPanel, HistoryPanel


class ModernButton(tk.Canvas):
    """Modern rounded button widget"""
    def __init__(self, parent, text, command=None, bg_color=PALETTE["accent"], 
                 hover_color=PALETTE["accent_dim"], text_color=PALETTE["highlight"],
                 icon=None, width=120, height=36, **kwargs):
        super().__init__(parent, highlightthickness=0, bg=PALETTE["bg"], 
                         width=width, height=height, **kwargs)
        self.command = command
        self.bg_color = bg_color
        self.hover_color = hover_color
        self.text_color = text_color
        self.text = text
        self.icon = icon
        self.current_color = bg_color
        
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<Button-1>", self.on_click)
        
        self.draw_button()
    
    def draw_button(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1:
            w, h = 120, 36
        
        # Create rounded rectangle
        radius = 12
        self.create_rounded_rect(0, 0, w, h, radius, fill=self.current_color, outline="")
        
        # Add text
        if self.icon:
            self.create_text(w//2 - 10, h//2, text=self.icon, font=("Segoe UI", 12), 
                            fill=self.text_color, anchor="e")
            self.create_text(w//2 + 5, h//2, text=self.text, font=("Segoe UI", 10, "bold"),
                            fill=self.text_color, anchor="w")
        else:
            self.create_text(w//2, h//2, text=self.text, font=("Segoe UI", 10, "bold"),
                            fill=self.text_color)
    
    def create_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        points = []
        points.append((x1 + radius, y1))
        points.append((x2 - radius, y1))
        points.append((x2, y1))
        points.append((x2, y1 + radius))
        points.append((x2, y2 - radius))
        points.append((x2, y2))
        points.append((x2 - radius, y2))
        points.append((x1 + radius, y2))
        points.append((x1, y2))
        points.append((x1, y2 - radius))
        points.append((x1, y1 + radius))
        points.append((x1, y1))
        
        polygon_points = []
        for p in points:
            polygon_points.extend(p)
        
        self.create_polygon(polygon_points, smooth=True, **kwargs)
    
    def on_enter(self, e):
        self.current_color = self.hover_color
        self.draw_button()
    
    def on_leave(self, e):
        self.current_color = self.bg_color
        self.draw_button()
    
    def on_click(self, e):
        if self.command:
            self.command()


class GradientFrame(tk.Canvas):
    """Frame with gradient background"""
    def __init__(self, parent, color1=PALETTE["bg"], color2=PALETTE["surface"], **kwargs):
        super().__init__(parent, highlightthickness=0, **kwargs)
        self.color1 = color1
        self.color2 = color2
        self.bind("<Configure>", self.draw_gradient)
    
    def draw_gradient(self, event=None):
        self.delete("gradient")
        w = self.winfo_width()
        h = self.winfo_height()
        
        # Create vertical gradient
        for i in range(h):
            ratio = i / h
            r = int(int(self.color1[1:3], 16) * (1 - ratio) + int(self.color2[1:3], 16) * ratio)
            g = int(int(self.color1[3:5], 16) * (1 - ratio) + int(self.color2[3:5], 16) * ratio)
            b = int(int(self.color1[5:7], 16) * (1 - ratio) + int(self.color2[5:7], 16) * ratio)
            color = f"#{r:02x}{g:02x}{b:02x}"
            self.create_line(0, i, w, i, fill=color, tags="gradient")
        
        self.tag_lower("gradient")


class SentimentApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Sentiment Analyser")
        self.geometry("900x750")
        self.minsize(700, 600)
        self.configure(bg=PALETTE["bg"])
        
        # Set modern window icon (optional)
        try:
            self.iconbitmap("icon.ico")
        except:
            pass

        self._realtime_var = tk.BooleanVar(value=False)
        self._word_count = 0

        self._build_menu()
        self._build_ui()

        # load model — callbacks post to main thread via .after()
        self._model = SentimentModel(
            on_ready=lambda: self.after(0, self._on_model_ready),
            on_error=lambda msg: self.after(0, lambda: self._on_model_error(msg)),
        )
        
        # Animation variables
        self.animation_after_id = None

    def _build_menu(self):
        self.menu = tk.Menu(self, bg=PALETTE["surface"], fg=PALETTE["text"],
                            activebackground=PALETTE["accent"], activeforeground=PALETTE["highlight"])
        self.config(menu=self.menu)

        # File menu
        file_menu = tk.Menu(self.menu, tearoff=0, bg=PALETTE["surface"], fg=PALETTE["text"])
        self.menu.add_cascade(label="📁 File", menu=file_menu)
        file_menu.add_command(label="📄 Open File", command=self._upload_file)
        file_menu.add_command(label="📊 Batch Analyze", command=self._batch_analyze)
        file_menu.add_command(label="💾 Save Report", command=self._save_report)
        file_menu.add_separator()
        file_menu.add_command(label="❌ Exit", command=self.quit)

        # View menu
        view_menu = tk.Menu(self.menu, tearoff=0, bg=PALETTE["surface"], fg=PALETTE["text"])
        self.menu.add_cascade(label="👁 View", menu=view_menu)
        view_menu.add_checkbutton(label="Real-time Analysis", variable=self._realtime_var, command=self._toggle_realtime)
        view_menu.add_command(label="📈 Show Statistics", command=self._show_stats)

        # Tools menu
        tools_menu = tk.Menu(self.menu, tearoff=0, bg=PALETTE["surface"], fg=PALETTE["text"])
        self.menu.add_cascade(label="🔧 Tools", menu=tools_menu)
        tools_menu.add_command(label="📱 Social Media Analysis", command=self._batch_analyze)
        tools_menu.add_separator()
        tools_menu.add_command(label="🥧 Show Sentiment Chart", command=self._show_pie_chart)
        tools_menu.add_command(label="📊 Show Trend Dashboard", command=self._show_trends)
        tools_menu.add_command(label="📝 Generate Summary", command=self._show_summary)
        tools_menu.add_command(label="⚠️ Detect Fake Review", command=self._show_fake_review)

        # Help menu
        help_menu = tk.Menu(self.menu, tearoff=0, bg=PALETTE["surface"], fg=PALETTE["text"])
        self.menu.add_cascade(label="ℹ️ Help", menu=help_menu)
        help_menu.add_command(label="📖 About", command=self._show_about)

    # ─────────────────────────────────────────────────────────────────────────
    # UI layout with modern design
    # ─────────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        PX = 28   # horizontal padding constant
        
        # Main container
        main_container = tk.Frame(self, bg=PALETTE["bg"])
        main_container.pack(fill="both", expand=True)

        # ── Header with gradient ──────────────────────────────────────────────
        header_frame = tk.Frame(main_container, bg=PALETTE["bg"])
        header_frame.pack(fill="x", padx=PX, pady=(15, 0))
        
        # Logo/Title container
        title_container = tk.Frame(header_frame, bg=PALETTE["bg"])
        title_container.pack(side="left")
        
        # Animated title
        self.title_label = tk.Label(
            title_container, text="🎭", font=("Segoe UI", 32),
            bg=PALETTE["bg"], fg=PALETTE["accent"]
        )
        self.title_label.pack(side="left", padx=(0, 8))
        
        title_text = tk.Label(
            title_container, text="SENTIMENT", font=("Segoe UI", 24, "bold"),
            bg=PALETTE["bg"], fg=PALETTE["highlight"]
        )
        title_text.pack(side="left")
        
        title_text2 = tk.Label(
            title_container, text=" ANALYSER", font=("Segoe UI", 24, "bold"),
            bg=PALETTE["bg"], fg=PALETTE["accent"]
        )
        title_text2.pack(side="left")
        
        # Subtitle
        subtitle = tk.Label(
            title_container, text="\nAI-Powered Sentiment Analysis", 
            font=("Segoe UI", 9), bg=PALETTE["bg"], fg=PALETTE["text_muted"]
        )
        subtitle.pack(side="left", padx=(10, 0))
        
        # Status with icon
        self._status_var = tk.StringVar(value="⟳  Loading model…")
        status_frame = tk.Frame(header_frame, bg=PALETTE["bg"])
        status_frame.pack(side="right")
        
        self.status_icon = tk.Label(status_frame, text="⚡", font=("Segoe UI", 12),
                                    bg=PALETTE["bg"], fg=PALETTE["accent"])
        self.status_icon.pack(side="left", padx=(0, 5))
        
        self._status_lbl = tk.Label(
            status_frame, textvariable=self._status_var,
            font=("Segoe UI", 9), bg=PALETTE["bg"], fg=PALETTE["text_muted"]
        )
        self._status_lbl.pack(side="left")

        # ── Decorative line ──────────────────────────────────────────────────
        line_frame = tk.Frame(main_container, bg=PALETTE["bg"], height=2)
        line_frame.pack(fill="x", padx=PX, pady=(15, 10))
        
        line_canvas = tk.Canvas(line_frame, height=2, bg=PALETTE["bg"], highlightthickness=0)
        line_canvas.pack(fill="x")
        line_canvas.create_line(0, 1, line_canvas.winfo_reqwidth(), 1, 
                                fill=PALETTE["accent"], width=2, tags="line")
        
        def animate_line(event=None):
            width = line_canvas.winfo_width()
            if width > 0:
                line_canvas.coords("line", 0, 1, width, 1)
        
        line_canvas.bind("<Configure>", animate_line)

        # ── Text input with modern styling ───────────────────────────────────
        input_label = tk.Label(
            main_container, text="✏️ Enter your text", font=("Segoe UI", 11, "bold"),
            bg=PALETTE["bg"], fg=PALETTE["text"]
        )
        input_label.pack(anchor="w", padx=PX, pady=(10, 5))
        
        self._input = LabeledTextInput(main_container, on_change=self._on_text_change)
        self._input.pack(fill="x", padx=PX, pady=(0, 10))
        self._input.bind_key("<Control-Return>", lambda _: self._run_analysis())
        
        # Add word count indicator
        self.word_count_label = tk.Label(
            main_container, text="", font=("Segoe UI", 8),
            bg=PALETTE["bg"], fg=PALETTE["text_muted"]
        )
        self.word_count_label.pack(anchor="e", padx=PX, pady=(0, 5))

        # ── Button bar with modern buttons ───────────────────────────────────
        button_container = tk.Frame(main_container, bg=PALETTE["bg"])
        button_container.pack(fill="x", padx=PX, pady=(0, 15))
        
        # Create a canvas for shadow effect
        button_bar = tk.Frame(button_container, bg=PALETTE["bg"])
        button_bar.pack()
        
        # Modern buttons
        self._analyse_btn = ModernButton(
            button_bar, text="ANALYSE", command=self._run_analysis,
            bg_color=PALETTE["accent"], hover_color=PALETTE["accent_dim"],
            text_color=PALETTE["highlight"], icon="🔍", width=130, height=40
        )
        self._analyse_btn.pack(side="left", padx=4)
        self._analyse_btn.config(state="disabled")
        
        upload_btn = ModernButton(
            button_bar, text="UPLOAD", command=self._upload_file,
            bg_color=PALETTE["surface"], hover_color=PALETTE["accent_dim"],
            text_color=PALETTE["text"], icon="📁", width=120, height=40
        )
        upload_btn.pack(side="left", padx=4)
        
        save_btn = ModernButton(
            button_bar, text="SAVE", command=self._save_report,
            bg_color=PALETTE["surface"], hover_color=PALETTE["accent_dim"],
            text_color=PALETTE["text"], icon="💾", width=110, height=40
        )
        save_btn.pack(side="left", padx=4)
        
        pdf_btn = ModernButton(
            button_bar, text="PDF", command=self._save_pdf_report,
            bg_color=PALETTE["surface"], hover_color=PALETTE["accent_dim"],
            text_color=PALETTE["text"], icon="📄", width=100, height=40
        )
        pdf_btn.pack(side="left", padx=4)
        
        clear_btn = ModernButton(
            button_bar, text="CLEAR", command=self._clear,
            bg_color=PALETTE["surface"], hover_color=PALETTE["negative"],
            text_color=PALETTE["text"], icon="🗑️", width=110, height=40
        )
        clear_btn.pack(side="left", padx=4)

        # ── Result panel with animation ──────────────────────────────────────
        result_label = tk.Label(
            main_container, text="📊 Analysis Result", font=("Segoe UI", 11, "bold"),
            bg=PALETTE["bg"], fg=PALETTE["text"]
        )
        result_label.pack(anchor="w", padx=PX, pady=(10, 5))
        
        self._result = ResultPanel(main_container)
        self._result.pack(fill="x", padx=PX, pady=(0, 10))

        # ── Separator with icon ──────────────────────────────────────────────
        history_header = tk.Frame(main_container, bg=PALETTE["bg"])
        history_header.pack(fill="x", padx=PX, pady=(10, 5))
        
        tk.Label(
            history_header, text="📜", font=("Segoe UI", 14),
            bg=PALETTE["bg"], fg=PALETTE["accent"]
        ).pack(side="left", padx=(0, 8))
        
        tk.Label(
            history_header, text="Analysis History", font=("Segoe UI", 11, "bold"),
            bg=PALETTE["bg"], fg=PALETTE["text"]
        ).pack(side="left")
        
        # Clear history button
        clear_history_btn = tk.Label(
            history_header, text="🗑️ Clear", font=("Segoe UI", 9),
            bg=PALETTE["bg"], fg=PALETTE["text_muted"], cursor="hand2"
        )
        clear_history_btn.pack(side="right")
        clear_history_btn.bind("<Button-1>", lambda e: self._clear_history())
        clear_history_btn.bind("<Enter>", lambda e: clear_history_btn.config(fg=PALETTE["negative"]))
        clear_history_btn.bind("<Leave>", lambda e: clear_history_btn.config(fg=PALETTE["text_muted"]))

        # ── History panel ────────────────────────────────────────────────────
        self._history = HistoryPanel(main_container)
        self._history.pack(fill="both", expand=True, padx=PX, pady=(0, 20))
        
        # Start title animation
        self.animate_title()

    def animate_title(self):
        """Animate the title icon"""
        icons = ["🎭", "😊", "😢", "😠", "😲", "🎭"]
        current = self.title_label.cget("text")
        if current in icons:
            next_idx = (icons.index(current) + 1) % len(icons)
            self.title_label.config(text=icons[next_idx])
        self.animation_after_id = self.after(1500, self.animate_title)

    # ─────────────────────────────────────────────────────────────────────────
    # Model callbacks
    # ─────────────────────────────────────────────────────────────────────────
    def _on_model_ready(self):
        self._update_status()
        self._analyse_btn.config(state="normal")
        self.status_icon.config(text="✅", fg=PALETTE["positive"])
        self.after(2000, lambda: self.status_icon.config(text="⚡"))

    def _on_model_error(self, msg):
        self._set_status(f"✗  {msg}", PALETTE["negative"])
        self.status_icon.config(text="❌", fg=PALETTE["negative"])

    # ─────────────────────────────────────────────────────────────────────────
    # Text change handling
    # ─────────────────────────────────────────────────────────────────────────
    def _on_text_change(self):
        text = self._input.get_text()
        words = len(text.split()) if text else 0
        self._word_count = words
        self.word_count_label.config(text=f"📝 {words} words" if words > 0 else "")
        self._update_status()
        if self._realtime_var.get() and text and self._model.ready:
            self._run_analysis()

    def _toggle_realtime(self):
        if self._realtime_var.get():
            self._on_text_change()  # trigger if enabled
            # Show notification
            self.status_icon.config(text="⚡", fg=PALETTE["accent"])
            self.after(1500, lambda: self.status_icon.config(text="⚡"))

    # ─────────────────────────────────────────────────────────────────────────
    # Analysis
    # ─────────────────────────────────────────────────────────────────────────
    def _run_analysis(self):
        if not self._model.ready:
            self._set_status("⟳  Model not ready yet…", PALETTE["text_muted"])
            return

        text = self._input.get_text()
        if not text.strip():
            return

        self._analyse_btn.config(state="disabled")
        self._set_status("⟳  Analysing…", PALETTE["text_muted"])
        self.status_icon.config(text="⏳", fg=PALETTE["accent"])

        def worker():
            try:
                translated_text, source_lang = translate_to_english(text)
                result = self._model.predict(translated_text)
                self.after(0, lambda: self._show_result(text, translated_text, source_lang, result))
            except Exception as exc:
                self.after(0, lambda: self._set_status(f"✗  {exc}", PALETTE["negative"]))
            finally:
                self.after(0, lambda: self._analyse_btn.config(state="normal"))
                self.after(0, lambda: self.status_icon.config(text="⚡"))

        threading.Thread(target=worker, daemon=True).start()

    def _show_result(self, original_text, translated_text, source_lang, result):
        label = result["label"]
        score = result["score"]
        
        # Animate result panel
        self._result.update(label, score)
        self._result.master.after(100, lambda: self._result.config(bg=PALETTE["accent_dim"]))
        self._result.master.after(300, lambda: self._result.config(bg=PALETTE["bg"]))
        
        self._input.highlight_sentiment(POSITIVE_WORDS, NEGATIVE_WORDS)
        fake_result = detect_fake_review(original_text)
        if fake_result["label"] == "Fake/Spam":
            self._set_status(f"⚠️ {fake_result['label']} ({fake_result['score']:.2f})", PALETTE["negative"])
        else:
            self._update_status()

        timestamp = datetime.now()
        self._history.add(original_text, label, score, timestamp)

        if source_lang != "en":
            self._set_status(f"✓  {label} ({score:.2f}) — Translated from {source_lang}", PALETTE["positive"])

    # ─────────────────────────────────────────────────────────────────────────
    # Additional methods
    # ─────────────────────────────────────────────────────────────────────────
    def _clear(self):
        self._input.clear()
        self._result.reset()
        self._word_count = 0
        self.word_count_label.config(text="")
        self._update_status()

    def _clear_history(self):
        if messagebox.askyesno("Clear History", "Are you sure you want to clear all history?"):
            self._history.clear()
            self._set_status("✓  History cleared", PALETTE["positive"])

    def _upload_file(self):
        file_path = filedialog.askopenfilename(filetypes=[
            ("Text files", "*.txt"),
            ("CSV files", "*.csv"),
            ("PDF files", "*.pdf"),
            ("Word docs", "*.docx"),
            ("All files", "*.*")
        ])
        if file_path:
            try:
                text = extract_text_from_file(file_path)
                self._input.set_text(text)
                self._run_analysis()
                self._set_status(f"✓  Loaded: {Path(file_path).name}", PALETTE["positive"])
            except Exception as e:
                self._set_status(f"✗  Error loading file: {e}", PALETTE["negative"])

    def _save_report(self):
        if not self._history._entries:
            self._set_status("✗  No entries to save", PALETTE["negative"])
            return
        file_path = filedialog.asksaveasfilename(defaultextension=".txt", 
                                                  filetypes=[("Text files", "*.txt"), ("CSV files", "*.csv")])
        if file_path:
            try:
                ext = os.path.splitext(file_path)[1].lower()
                if ext == ".csv":
                    with open(file_path, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        writer.writerow(["#", "Text", "Sentiment", "Score", "Timestamp"])
                        for i, (text, label, score, timestamp) in enumerate(self._history._entries, 1):
                            writer.writerow([i, text, label, f"{score:.4f}", timestamp.isoformat() if timestamp else ""])
                else:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write("=" * 60 + "\n")
                        f.write("SENTIMENT ANALYSIS REPORT\n")
                        f.write("=" * 60 + "\n\n")
                        for i, (text, label, score, timestamp) in enumerate(self._history._entries, 1):
                            ts = timestamp.strftime("%Y-%m-%d %H:%M:%S") if timestamp else "n/a"
                            f.write(f"{i}. Text: {text}\n")
                            f.write(f"   Sentiment: {label}, Score: {score:.4f}, Time: {ts}\n\n")
                        f.write("=" * 60 + "\n")
                        f.write(f"Total Analyses: {len(self._history._entries)}\n")
                self._set_status("✓  Report saved", PALETTE["positive"])
            except Exception as e:
                self._set_status(f"✗  Error saving report: {e}", PALETTE["negative"])

    def _batch_analyze(self):
        file_path = filedialog.askopenfilename(filetypes=[
            ("CSV files", "*.csv"),
            ("Text files", "*.txt"),
            ("PDF files", "*.pdf"),
            ("Word docs", "*.docx"),
            ("All files", "*.*")
        ])
        if not file_path:
            return
        try:
            texts = extract_texts_from_file(file_path)
            if not texts:
                messagebox.showwarning("Warning", "No texts found in file.")
                return
            self._run_batch_analysis(texts)
        except Exception as e:
            messagebox.showerror("Error", f"Error loading file: {e}")

    def _run_batch_analysis(self, texts):
        if not self._model.ready:
            messagebox.showwarning("Warning", "Model not ready yet.")
            return
        
        # Create modern progress window
        progress_win = tk.Toplevel(self)
        progress_win.title("Batch Analysis")
        progress_win.geometry("450x200")
        progress_win.configure(bg=PALETTE["bg"])
        progress_win.transient(self)
        progress_win.grab_set()
        
        # Center the window
        progress_win.update_idletasks()
        x = (progress_win.winfo_screenwidth() // 2) - (450 // 2)
        y = (progress_win.winfo_screenheight() // 2) - (200 // 2)
        progress_win.geometry(f"450x200+{x}+{y}")
        
        tk.Label(progress_win, text="📊 Batch Analysis in Progress", 
                font=("Segoe UI", 12, "bold"), bg=PALETTE["bg"], fg=PALETTE["text"]).pack(pady=15)
        
        progress = ttk.Progressbar(progress_win, orient="horizontal", length=350, mode="determinate")
        progress.pack(pady=10)
        progress["maximum"] = len(texts)
        
        status_label = tk.Label(progress_win, text="", font=("Segoe UI", 9),
                                bg=PALETTE["bg"], fg=PALETTE["text_muted"])
        status_label.pack(pady=5)
        
        results = []
        
        def worker():
            for i, text in enumerate(texts):
                if text:
                    result = self._model.predict(text)
                    results.append((text, result["label"], result["score"]))
                    progress["value"] = i + 1
                    status_label.config(text=f"Processing {i+1}/{len(texts)}")
                    progress_win.update()
            progress_win.destroy()
            self._show_batch_results(results)
        
        threading.Thread(target=worker, daemon=True).start()

    def _show_batch_results(self, results):
        win = tk.Toplevel(self)
        win.title("Batch Results")
        win.geometry("900x650")
        win.configure(bg=PALETTE["bg"])
        
        # Header
        header = tk.Frame(win, bg=PALETTE["accent"], height=60)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        tk.Label(header, text="📊 Batch Analysis Results", font=("Segoe UI", 16, "bold"),
                bg=PALETTE["accent"], fg=PALETTE["highlight"]).pack(pady=15)
        
        # Create Treeview with modern styling
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=PALETTE["surface"], foreground=PALETTE["text"],
                       fieldbackground=PALETTE["surface"], font=("Segoe UI", 9))
        style.configure("Treeview.Heading", background=PALETTE["bg"], foreground=PALETTE["text"],
                       font=("Segoe UI", 10, "bold"))
        style.map("Treeview", background=[("selected", PALETTE["accent"])])
        
        tree_frame = tk.Frame(win, bg=PALETTE["bg"])
        tree_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        tree = ttk.Treeview(tree_frame, columns=("Text", "Sentiment", "Score"), show="headings", height=20)
        tree.heading("Text", text="Text")
        tree.heading("Sentiment", text="Sentiment")
        tree.heading("Score", text="Score")
        tree.column("Text", width=500)
        tree.column("Sentiment", width=150)
        tree.column("Score", width=100)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        for text, label, score in results:
            # Add emoji for sentiment
            emoji = "😊" if label in {"Happy", "Surprise"} else "😢" if label in {"Angry", "Sad", "Fear"} else "😐"
            tree.insert("", "end", values=(text[:80] + "..." if len(text) > 80 else text, f"{emoji} {label}", f"{score:.2f}"))
        
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Add to history
        for text, label, score in results:
            self._history.add(text, label, score, datetime.now())
        
        # Summary label
        positive = sum(1 for _, label, _ in results if label in {"Happy", "Surprise"})
        negative = sum(1 for _, label, _ in results if label in {"Angry", "Sad", "Fear"})
        neutral = sum(1 for _, label, _ in results if label == "Neutral")
        
        summary_frame = tk.Frame(win, bg=PALETTE["bg"])
        summary_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        summary_text = f"📈 Summary: {positive} Positive  |  {negative} Negative  |  {neutral} Neutral  |  Total: {len(results)}"
        tk.Label(summary_frame, text=summary_text, font=("Segoe UI", 10, "bold"),
                bg=PALETTE["bg"], fg=PALETTE["text"]).pack()

    def _show_stats(self):
        if not self._history._entries:
            messagebox.showinfo("Info", "No data to show statistics.")
            return
        
        positive = sum(1 for _, label, _, _ in self._history._entries if label in {"Happy", "Surprise"})
        negative = sum(1 for _, label, _, _ in self._history._entries if label in {"Angry", "Sad", "Fear"})
        neutral = sum(1 for _, label, _, _ in self._history._entries if label == "Neutral")
        total = len(self._history._entries)
        
        win = tk.Toplevel(self)
        win.title("Statistics")
        win.geometry("500x400")
        win.configure(bg=PALETTE["bg"])
        win.transient(self)
        
        # Center window
        win.update_idletasks()
        x = (win.winfo_screenwidth() // 2) - (500 // 2)
        y = (win.winfo_screenheight() // 2) - (400 // 2)
        win.geometry(f"500x400+{x}+{y}")
        
        # Header
        header = tk.Frame(win, bg=PALETTE["accent"], height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="📊 Statistics Dashboard", font=("Segoe UI", 14, "bold"),
                bg=PALETTE["accent"], fg=PALETTE["highlight"]).pack(pady=12)
        
        # Stats cards
        stats_frame = tk.Frame(win, bg=PALETTE["bg"])
        stats_frame.pack(fill="x", padx=30, pady=30)
        
        # Total card
        total_card = tk.Frame(stats_frame, bg=PALETTE["surface"], relief="flat", bd=0)
        total_card.pack(side="left", fill="both", expand=True, padx=5)
        tk.Label(total_card, text=f"{total}", font=("Segoe UI", 24, "bold"),
                bg=PALETTE["surface"], fg=PALETTE["accent"]).pack(pady=(15, 0))
        tk.Label(total_card, text="Total Analyses", font=("Segoe UI", 10),
                bg=PALETTE["surface"], fg=PALETTE["text_muted"]).pack(pady=(0, 15))
        
        # Positive card
        pos_card = tk.Frame(stats_frame, bg=PALETTE["surface"], relief="flat", bd=0)
        pos_card.pack(side="left", fill="both", expand=True, padx=5)
        tk.Label(pos_card, text=f"{positive}", font=("Segoe UI", 24, "bold"),
                bg=PALETTE["surface"], fg=PALETTE["positive"]).pack(pady=(15, 0))
        tk.Label(pos_card, text=f"Positive ({positive/total*100:.1f}%)", font=("Segoe UI", 10),
                bg=PALETTE["surface"], fg=PALETTE["text_muted"]).pack(pady=(0, 15))
        
        # Negative card
        neg_card = tk.Frame(stats_frame, bg=PALETTE["surface"], relief="flat", bd=0)
        neg_card.pack(side="left", fill="both", expand=True, padx=5)
        tk.Label(neg_card, text=f"{negative}", font=("Segoe UI", 24, "bold"),
                bg=PALETTE["surface"], fg=PALETTE["negative"]).pack(pady=(15, 0))
        tk.Label(neg_card, text=f"Negative ({negative/total*100:.1f}%)", font=("Segoe UI", 10),
                bg=PALETTE["surface"], fg=PALETTE["text_muted"]).pack(pady=(0, 15))
        
        # Neutral card
        neu_card = tk.Frame(stats_frame, bg=PALETTE["surface"], relief="flat", bd=0)
        neu_card.pack(side="left", fill="both", expand=True, padx=5)
        tk.Label(neu_card, text=f"{neutral}", font=("Segoe UI", 24, "bold"),
                bg=PALETTE["surface"], fg=PALETTE["text"]).pack(pady=(15, 0))
        tk.Label(neu_card, text=f"Neutral ({neutral/total*100:.1f}%)", font=("Segoe UI", 10),
                bg=PALETTE["surface"], fg=PALETTE["text_muted"]).pack(pady=(0, 15))
        
        # Progress bar visualization
        progress_frame = tk.Frame(win, bg=PALETTE["bg"])
        progress_frame.pack(fill="x", padx=40, pady=20)
        
        if total > 0:
            canvas = tk.Canvas(progress_frame, bg=PALETTE["bg"], height=30, highlightthickness=0)
            canvas.pack(fill="x")
            
            pos_width = (positive / total) * 400
            neg_width = (negative / total) * 400
            neu_width = (neutral / total) * 400
            
            canvas.create_rectangle(0, 5, pos_width, 25, fill=PALETTE["positive"], outline="")
            canvas.create_rectangle(pos_width, 5, pos_width + neg_width, 25, fill=PALETTE["negative"], outline="")
            canvas.create_rectangle(pos_width + neg_width, 5, pos_width + neg_width + neu_width, 25, fill=PALETTE["surface"], outline="")

    def _save_pdf_report(self):
        if not REPORTLAB_AVAILABLE:
            messagebox.showwarning("Dependency missing", "Install reportlab to generate PDF reports: pip install reportlab")
            return
        if not self._history._entries:
            self._set_status("✗  No entries to save", PALETTE["negative"])
            return
        file_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")])
        if not file_path:
            return
        try:
            pdf = canvas.Canvas(file_path, pagesize=letter)
            width, height = letter
            pdf.setFont("Helvetica-Bold", 18)
            pdf.drawString(40, height - 50, "Sentiment Analysis Report")
            pdf.setFont("Helvetica", 10)
            pdf.drawString(40, height - 70, f"Generated: {datetime.now().isoformat()}")
            y = height - 100
            for i, (text, label, score, timestamp) in enumerate(self._history._entries, 1):
                if y < 120:
                    pdf.showPage()
                    y = height - 50
                pdf.setFont("Helvetica-Bold", 11)
                ts = timestamp.strftime("%Y-%m-%d %H:%M:%S") if timestamp else "n/a"
                pdf.drawString(40, y, f"{i}. {label} ({score:.2f}) — {ts}")
                y -= 16
                pdf.setFont("Helvetica", 9)
                for line in textwrap.wrap(text, 90):
                    pdf.drawString(50, y, line)
                    y -= 12
                    if y < 80:
                        pdf.showPage()
                        y = height - 50
                y -= 14
            pdf.save()
            self._set_status("✓  PDF report saved", PALETTE["positive"])
        except Exception as exc:
            self._set_status(f"✗  Error saving PDF: {exc}", PALETTE["negative"])

    def _show_summary(self):
        text = self._input.get_text()
        if not text.strip():
            messagebox.showinfo("Info", "Enter text before generating a summary.")
            return
        try:
            summary = summarize_text(text)
            win = tk.Toplevel(self)
            win.title("AI Summary")
            win.geometry("600x400")
            win.configure(bg=PALETTE["bg"])
            win.transient(self)
            
            # Header
            header = tk.Frame(win, bg=PALETTE["accent"], height=40)
            header.pack(fill="x")
            header.pack_propagate(False)
            tk.Label(header, text="📝 AI-Generated Summary", font=("Segoe UI", 12, "bold"),
                    bg=PALETTE["accent"], fg=PALETTE["highlight"]).pack(pady=8)
            
            text_box = tk.Text(win, bg=PALETTE["surface"], fg=PALETTE["text"], 
                              wrap="word", font=("Segoe UI", 10), padx=15, pady=15)
            text_box.pack(fill="both", expand=True, padx=20, pady=20)
            text_box.insert("1.0", summary)
            text_box.config(state="disabled")
        except Exception as exc:
            messagebox.showerror("Error", f"Unable to generate summary: {exc}")

    def _show_fake_review(self):
        text = self._input.get_text()
        if not text.strip():
            messagebox.showinfo("Info", "Enter text before checking for fake review signals.")
            return
        result = detect_fake_review(text)
        
        # Show styled messagebox
        win = tk.Toplevel(self)
        win.title("Fake Review Detection")
        win.geometry("400x200")
        win.configure(bg=PALETTE["bg"])
        win.transient(self)
        
        # Center window
        win.update_idletasks()
        x = (win.winfo_screenwidth() // 2) - (400 // 2)
        y = (win.winfo_screenheight() // 2) - (200 // 2)
        win.geometry(f"400x200+{x}+{y}")
        
        color = PALETTE["negative"] if result["label"] == "Fake/Spam" else PALETTE["positive"]
        icon = "⚠️" if result["label"] == "Fake/Spam" else "✅"
        
        tk.Label(win, text=f"{icon} Fake Review Detection", font=("Segoe UI", 14, "bold"),
                bg=PALETTE["bg"], fg=color).pack(pady=20)
        tk.Label(win, text=f"Label: {result['label']}", font=("Segoe UI", 12),
                bg=PALETTE["bg"], fg=PALETTE["text"]).pack()
        tk.Label(win, text=f"Confidence Score: {result['score']:.2f}", font=("Segoe UI", 10),
                bg=PALETTE["bg"], fg=PALETTE["text_muted"]).pack(pady=5)
        
        tk.Button(win, text="OK", command=win.destroy,
                 bg=PALETTE["accent"], fg=PALETTE["highlight"],
                 activebackground=PALETTE["accent_dim"], font=("Segoe UI", 10, "bold"),
                 relief="flat", padx=20, pady=5).pack(pady=15)

    def _show_pie_chart(self):
        if not MATPLOTLIB_AVAILABLE:
            messagebox.showwarning("Dependency missing", "Install matplotlib for charts: pip install matplotlib")
            return
        if not self._history._entries:
            messagebox.showinfo("Info", "No history to display.")
            return
        
        labels = ["Positive", "Negative", "Neutral"]
        positive = sum(1 for _, label, _, _ in self._history._entries if label in {"Happy", "Surprise"})
        negative = sum(1 for _, label, _, _ in self._history._entries if label in {"Angry", "Sad", "Fear"})
        neutral = sum(1 for _, label, _, _ in self._history._entries if label == "Neutral")
        sizes = [positive, negative, neutral]
        colors = [PALETTE["positive"], PALETTE["negative"], PALETTE["surface"]]
        
        win = tk.Toplevel(self)
        win.title("Sentiment Distribution")
        win.geometry("600x550")
        win.configure(bg=PALETTE["bg"])
        
        # Use modern matplotlib style
        plt.style.use('seaborn-v0_8-darkgrid')
        fig, ax = plt.subplots(figsize=(6, 5))
        wedges, texts, autotexts = ax.pie(sizes, labels=labels, autopct="%.1f%%", 
                                           colors=colors, startangle=140,
                                           textprops={'fontsize': 12, 'color': PALETTE["text"]})
        for autotext in autotexts:
            autotext.set_color(PALETTE["highlight"])
            autotext.set_fontsize(11)
            autotext.set_weight('bold')
        
        ax.set_title("Sentiment Distribution", fontsize=14, color=PALETTE["text"], pad=20)
        chart = FigureCanvasTkAgg(fig, master=win)
        chart.draw()
        chart.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

    def _show_trends(self):
        if not MATPLOTLIB_AVAILABLE:
            messagebox.showwarning("Dependency missing", "Install matplotlib for charts: pip install matplotlib")
            return
        if not self._history._entries:
            messagebox.showinfo("Info", "No history to display.")
            return
        
        bucket = defaultdict(lambda: {"positive": 0, "negative": 0, "neutral": 0})
        for _, label, _, timestamp in self._history._entries:
            if not timestamp:
                continue
            date_key = timestamp.date()
            if label in {"Happy", "Surprise"}:
                bucket[date_key]["positive"] += 1
            elif label in {"Angry", "Sad", "Fear"}:
                bucket[date_key]["negative"] += 1
            else:
                bucket[date_key]["neutral"] += 1
        
        dates = sorted(bucket.keys())
        positives = [bucket[d]["positive"] for d in dates]
        negatives = [bucket[d]["negative"] for d in dates]
        neutrals = [bucket[d]["neutral"] for d in dates]
        
        win = tk.Toplevel(self)
        win.title("Sentiment Trends")
        win.geometry("800x550")
        win.configure(bg=PALETTE["bg"])
        
        plt.style.use('seaborn-v0_8-darkgrid')
        fig, ax = plt.subplots(figsize=(9, 5))
        
        ax.plot(dates, positives, label="Positive", color=PALETTE["positive"], 
               marker='o', linewidth=2, markersize=6)
        ax.plot(dates, negatives, label="Negative", color=PALETTE["negative"],
               marker='s', linewidth=2, markersize=6)
        ax.plot(dates, neutrals, label="Neutral", color=PALETTE["text"],
               marker='^', linewidth=2, markersize=6)
        
        ax.set_title("Daily Sentiment Trend Analysis", fontsize=14, color=PALETTE["text"], pad=20)
        ax.set_xlabel("Date", fontsize=11, color=PALETTE["text"])
        ax.set_ylabel("Number of Analyses", fontsize=11, color=PALETTE["text"])
        ax.legend(loc='best', framealpha=0.9)
        ax.grid(True, alpha=0.3)
        ax.set_facecolor(PALETTE["bg"])
        fig.patch.set_facecolor(PALETTE["bg"])
        
        fig.autofmt_xdate()
        chart = FigureCanvasTkAgg(fig, master=win)
        chart.draw()
        chart.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

    def _show_about(self):
        about_text = """🎭 Sentiment Analyser v2.0

AI-Powered Sentiment Analysis Tool

Features:
• Real-time sentiment analysis
• Multi-language support
• Batch processing
• Visual analytics dashboard
• PDF/CSV report generation
• Fake review detection
• AI text summarization

Built with:
• Python & Tkinter
• HuggingFace Transformers
• Matplotlib

© Final Year Project 2024"""
        
        win = tk.Toplevel(self)
        win.title("About")
        win.geometry("450x400")
        win.configure(bg=PALETTE["bg"])
        win.transient(self)
        
        # Center window
        win.update_idletasks()
        x = (win.winfo_screenwidth() // 2) - (450 // 2)
        y = (win.winfo_screenheight() // 2) - (400 // 2)
        win.geometry(f"450x400+{x}+{y}")
        
        # Header with gradient
        header = tk.Frame(win, bg=PALETTE["accent"], height=80)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        tk.Label(header, text="🎭", font=("Segoe UI", 36),
                bg=PALETTE["accent"], fg=PALETTE["highlight"]).pack(pady=(15, 0))
        tk.Label(header, text="Sentiment Analyser", font=("Segoe UI", 14, "bold"),
                bg=PALETTE["accent"], fg=PALETTE["highlight"]).pack()
        
        text_box = tk.Text(win, bg=PALETTE["surface"], fg=PALETTE["text"],
                          font=("Segoe UI", 10), padx=20, pady=15, wrap="word")
        text_box.pack(fill="both", expand=True, padx=20, pady=20)
        text_box.insert("1.0", about_text)
        text_box.config(state="disabled")
        
        tk.Button(win, text="Close", command=win.destroy,
                 bg=PALETTE["accent"], fg=PALETTE["highlight"],
                 activebackground=PALETTE["accent_dim"], font=("Segoe UI", 10, "bold"),
                 relief="flat", padx=20, pady=5).pack(pady=(0, 20))

    def _update_status(self):
        base = "✓  Model ready" if self._model.ready else "⟳  Loading model…"
        self._status_var.set(f"{base} | Words: {self._word_count}")
        self._status_lbl.config(fg=PALETTE["positive"] if self._model.ready else PALETTE["text_muted"])

    def _set_status(self, msg: str, color: str = None):
        self._status_var.set(msg)
        if color:
            self._status_lbl.config(fg=color)
            # Reset after 3 seconds for non-error messages
            if color != PALETTE["negative"]:
                self.after(3000, self._update_status)