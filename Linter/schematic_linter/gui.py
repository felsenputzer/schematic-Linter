"""Desktop GUI (tkinter): pick a project folder, choose checks and
thresholds, run the analysis, open the report.

Start it with ``schematic-linter-gui``, ``python -m schematic_linter``, the
standalone ``SchematicLinter.exe``, or by running ``run_linter.py`` from an
IDE such as Spyder.

The analysis runs in a background thread so the window stays responsive;
the thread never touches tkinter itself, it only posts messages to a queue
that the GUI thread polls (tkinter is not thread-safe).
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import traceback
import webbrowser
from pathlib import Path
from typing import Callable, Dict, List, Optional

import tkinter as tk
from tkinter import filedialog, font as tkfont, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from . import __version__, config
from .config import Severity
from .parsers.bom_parser import BomParseError
from .parsers.flatten_check import NonFlattenedNetlistError
from .parsers.netlist_parser import NetlistParseError
from .pipeline import PipelineResult, default_output_dir, run_pipeline
from .project import ProjectDiscoveryError, discover_project
from .rules import RuleInfo, available_rules
from .settings import LintSettings, load_profile, load_settings, save_profile, save_settings

APP_TITLE = "Schematic Linter"
POLL_MS = 100

COLOR_OK = "#1b7a3d"
COLOR_MISSING = "#8a6d00"
COLOR_BAD = "#b42318"
COLOR_MUTED = "#667085"
SEVERITY_COLORS = {Severity.ERROR: "#b42318", Severity.WARNING: "#b54708", Severity.INFO: "#175cd3"}

# Expected input problems -> (dialog title, explanation prefix). Anything
# else is treated as a bug and shown with a traceback.
_INPUT_ERRORS = (
    (ProjectDiscoveryError, "Problem with the project folder", ""),
    (NonFlattenedNetlistError, "Netlist rejected", "The netlist can't be analyzed:\n\n"),
    (NetlistParseError, "Could not read the netlist", ""),
    (BomParseError, "Could not read the eBOM", ""),
)


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def open_path(path: Path) -> None:
    """Opens a file or folder with the OS's default application."""

    path = Path(path)
    if sys.platform == "win32":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    elif path.is_file():
        webbrowser.open(path.resolve().as_uri())
    else:
        subprocess.Popen(["xdg-open", str(path)])


class ScrollableFrame(ttk.Frame):
    """A vertically scrollable container; put children into ``.inner``."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        background = ttk.Style(self).lookup("TFrame", "background") or None
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0, background=background)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._window, width=e.width))
        # Mouse wheel only while the pointer is over this widget.
        self.bind("<Enter>", lambda e: self._bind_wheel(True))
        self.bind("<Leave>", lambda e: self._bind_wheel(False))

    def _bind_wheel(self, on: bool) -> None:
        if on:
            self.bind_all("<MouseWheel>", self._on_wheel)  # Windows / macOS
            self.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))  # X11
            self.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))
        else:
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                self.unbind_all(seq)

    def _on_wheel(self, event) -> None:
        if self.canvas.yview() == (0.0, 1.0):
            return  # everything visible, nothing to scroll
        step = -1 if event.delta > 0 else 1
        if sys.platform == "darwin":
            step = -event.delta
        self.canvas.yview_scroll(step, "units")


class LinterApp:
    def __init__(self, root: tk.Tk, settings: Optional[LintSettings] = None, persist: bool = True):
        self.root = root
        self.persist = persist  # False in tests/smoke test: don't touch the user's saved settings
        self.settings = settings if settings is not None else (load_settings() if persist else LintSettings())
        self.rules: List[RuleInfo] = available_rules()
        self.queue: "queue.Queue[tuple]" = queue.Queue()
        self.worker: Optional[threading.Thread] = None
        self.last_result: Optional[PipelineResult] = None
        self.last_exit_code: Optional[int] = None
        self.on_finished: Optional[Callable[[int], None]] = None  # hook for the smoke test

        root.title(f"{APP_TITLE} {__version__}")
        root.geometry("860x760")
        root.minsize(680, 600)
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.report_callback_exception = self._report_callback_exception

        base = tkfont.nametofont("TkDefaultFont")
        size = base.cget("size")  # > 0: points, < 0: pixels (Tk convention)

        def resized(delta: int) -> int:
            return size + delta if size > 0 else size - delta

        self.font_bold = base.copy()
        self.font_bold.configure(weight="bold")
        self.font_small = base.copy()
        self.font_small.configure(size=resized(-1))
        self.font_big = base.copy()
        self.font_big.configure(weight="bold", size=resized(2))

        self.project_ok = False
        self._refresh_after_id = None

        self.project_var = tk.StringVar(value=self.settings.project_dir)
        self.output_var = tk.StringVar(value=self.settings.output_dir)
        self.open_report_var = tk.BooleanVar(value=self.settings.open_report)
        self.rule_vars: Dict[str, tk.BooleanVar] = {
            r.rule_id: tk.BooleanVar(value=r.rule_id not in self.settings.disabled_rules) for r in self.rules
        }
        self.threshold_vars: Dict[str, tk.StringVar] = {
            t.key: tk.StringVar(value=f"{self.settings.thresholds.get(t.key, t.default):g}")
            for t in config.TUNABLE_THRESHOLDS
        }

        self._build_menu()
        self._build_layout()
        self.project_var.trace_add("write", lambda *_: self._schedule_project_refresh())
        self.output_var.trace_add("write", lambda *_: self._update_output_hint())
        for var in self.rule_vars.values():
            var.trace_add("write", lambda *_: self._update_rule_count())
        self._refresh_project_info()
        self._update_rule_count()
        self.root.after(POLL_MS, self._poll_queue)

    # ------------------------------------------------------------------ UI

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Choose project folder...", command=self.browse_project)
        file_menu.add_separator()
        file_menu.add_command(label="Load check profile...", command=self.load_profile)
        file_menu.add_command(label="Save check profile...", command=self.save_profile)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)
        menubar.add_cascade(label="File", menu=file_menu)
        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="How to use", command=self.show_help)
        help_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        self.root.config(menu=menubar)

    def _build_layout(self) -> None:
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)

        # --- 1. Inputs --------------------------------------------------
        inputs = ttk.LabelFrame(outer, text="Project", padding=10)
        inputs.grid(row=0, column=0, sticky="ew")
        inputs.columnconfigure(1, weight=1)

        ttk.Label(inputs, text="Project folder:").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.project_entry = ttk.Entry(inputs, textvariable=self.project_var)
        self.project_entry.grid(row=0, column=1, sticky="ew")
        self.browse_project_btn = ttk.Button(inputs, text="Browse...", command=self.browse_project)
        self.browse_project_btn.grid(row=0, column=2, padx=(8, 0))

        files = ttk.Frame(inputs)
        files.grid(row=1, column=1, columnspan=2, sticky="ew", pady=(6, 8))
        self.file_labels: Dict[str, ttk.Label] = {}
        for row, (key, caption) in enumerate((("netlist", "Netlist (.ndf)"), ("bom", "eBOM (.csv)"), ("pdf", "Schematic (.pdf)"))):
            ttk.Label(files, text=caption + ":", foreground=COLOR_MUTED).grid(row=row, column=0, sticky="w", padx=(0, 8))
            label = ttk.Label(files, text="")
            label.grid(row=row, column=1, sticky="w")
            self.file_labels[key] = label

        ttk.Label(inputs, text="Report folder:").grid(row=2, column=0, sticky="w", padx=(0, 8))
        self.output_entry = ttk.Entry(inputs, textvariable=self.output_var)
        self.output_entry.grid(row=2, column=1, sticky="ew")
        self.browse_output_btn = ttk.Button(inputs, text="Browse...", command=self.browse_output)
        self.browse_output_btn.grid(row=2, column=2, padx=(8, 0))
        self.output_hint = ttk.Label(inputs, text="", foreground=COLOR_MUTED, font=self.font_small)
        self.output_hint.grid(row=3, column=1, columnspan=2, sticky="w", pady=(2, 0))

        # --- 2. Checks / thresholds / log ---------------------------------
        self.notebook = ttk.Notebook(outer)
        self.notebook.grid(row=1, column=0, sticky="nsew", pady=(10, 10))
        self.notebook.add(self._build_checks_tab(self.notebook), text="Checks")
        self.notebook.add(self._build_thresholds_tab(self.notebook), text="Thresholds")
        self.log_tab = self._build_log_tab(self.notebook)
        self.notebook.add(self.log_tab, text="Log")

        # --- 3. Run bar ------------------------------------------------------
        run_bar = ttk.Frame(outer)
        run_bar.grid(row=2, column=0, sticky="ew")
        run_bar.columnconfigure(1, weight=1)
        self.run_btn = ttk.Button(run_bar, text="Run checks", command=self.run_checks, width=16)
        self.run_btn.grid(row=0, column=0, rowspan=2, sticky="ns", padx=(0, 12), ipady=6)
        self.progress = ttk.Progressbar(run_bar, mode="determinate", value=0)
        self.progress.grid(row=0, column=1, sticky="ew")
        self.status_label = ttk.Label(run_bar, text="Ready.", foreground=COLOR_MUTED)
        self.status_label.grid(row=1, column=1, sticky="w", pady=(4, 0))

        result_bar = ttk.Frame(outer)
        result_bar.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        result_bar.columnconfigure(0, weight=1)
        self.summary_frame = ttk.Frame(result_bar)
        self.summary_frame.grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(result_bar, text="Open report when finished", variable=self.open_report_var).grid(
            row=0, column=1, padx=(0, 12)
        )
        self.open_report_btn = ttk.Button(result_bar, text="Open report", command=self.open_report, state="disabled")
        self.open_report_btn.grid(row=0, column=2)
        self.open_folder_btn = ttk.Button(result_bar, text="Open folder", command=self.open_output_folder, state="disabled")
        self.open_folder_btn.grid(row=0, column=3, padx=(6, 0))

    def _build_checks_tab(self, master) -> ttk.Frame:
        tab = ttk.Frame(master, padding=8)
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)

        top = ttk.Frame(tab)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        top.columnconfigure(0, weight=1)
        self.rule_count_label = ttk.Label(top, text="")
        self.rule_count_label.grid(row=0, column=0, sticky="w")
        ttk.Button(top, text="All", width=6, command=lambda: self._set_all_rules(True)).grid(row=0, column=1)
        ttk.Button(top, text="None", width=6, command=lambda: self._set_all_rules(False)).grid(row=0, column=2, padx=4)

        scroll = ScrollableFrame(tab)
        scroll.grid(row=1, column=0, sticky="nsew")
        scroll.inner.columnconfigure(0, weight=1)
        self._description_labels: List[ttk.Label] = []
        for i, rule in enumerate(self.rules):
            row = ttk.Frame(scroll.inner, padding=(2, 4))
            row.grid(row=i, column=0, sticky="ew")
            row.columnconfigure(1, weight=1)
            ttk.Checkbutton(row, variable=self.rule_vars[rule.rule_id]).grid(row=0, column=0, rowspan=2, sticky="n")
            name = ttk.Label(row, text=rule.name, font=self.font_bold, cursor="hand2")
            name.grid(row=0, column=1, sticky="w")
            description = rule.description
            if rule.requires_bom:
                description += "  Only runs if the project has an eBOM."
            desc = ttk.Label(row, text=description, foreground=COLOR_MUTED, wraplength=600, justify="left")
            desc.grid(row=1, column=1, sticky="w")
            self._description_labels.append(desc)
            for widget in (name, desc):  # clicking the text toggles the check too
                widget.bind("<Button-1>", lambda e, v=self.rule_vars[rule.rule_id]: v.set(not v.get()))
        scroll.canvas.bind(
            "<Configure>",
            lambda e: [lbl.configure(wraplength=max(e.width - 60, 200)) for lbl in self._description_labels],
            add="+",
        )

        bottom = ttk.Frame(tab)
        bottom.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(bottom, text="Load profile...", command=self.load_profile).pack(side="left")
        ttk.Button(bottom, text="Save profile...", command=self.save_profile).pack(side="left", padx=6)
        ttk.Label(
            bottom, text="A profile stores the selected checks and thresholds, to share with colleagues.",
            foreground=COLOR_MUTED, font=self.font_small,
        ).pack(side="left", padx=6)
        return tab

    def _build_thresholds_tab(self, master) -> ttk.Frame:
        tab = ttk.Frame(master, padding=12)
        tab.columnconfigure(2, weight=1)
        for i, spec in enumerate(config.TUNABLE_THRESHOLDS):
            ttk.Label(tab, text=spec.label, font=self.font_bold).grid(row=2 * i, column=0, sticky="w", pady=(8, 0))
            increment = 1 if (spec.kind is int or spec.maximum > 100) else 0.1
            ttk.Spinbox(
                tab, textvariable=self.threshold_vars[spec.key], from_=spec.minimum, to=spec.maximum,
                increment=increment, width=10,
            ).grid(row=2 * i, column=1, sticky="w", padx=12, pady=(8, 0))
            ttk.Label(tab, text=f"default: {spec.default:g}", foreground=COLOR_MUTED).grid(
                row=2 * i, column=2, sticky="w", pady=(8, 0)
            )
            used_by = ", ".join(r.name for r in self.rules if r.rule_id in spec.used_by)
            ttk.Label(
                tab, text=f"{spec.help}  (Used by: {used_by})", foreground=COLOR_MUTED, font=self.font_small,
                wraplength=700, justify="left",
            ).grid(row=2 * i + 1, column=0, columnspan=3, sticky="w")
        ttk.Button(tab, text="Reset to defaults", command=self.reset_thresholds).grid(
            row=2 * len(config.TUNABLE_THRESHOLDS), column=0, sticky="w", pady=(16, 0)
        )
        return tab

    def _build_log_tab(self, master) -> ttk.Frame:
        tab = ttk.Frame(master, padding=4)
        self.log_text = ScrolledText(tab, height=10, wrap="word", state="disabled", font="TkFixedFont")
        self.log_text.pack(fill="both", expand=True)
        self.log_text.tag_configure("error", foreground=COLOR_BAD)
        self.log_text.tag_configure("ok", foreground=COLOR_OK)
        return tab

    # ------------------------------------------------------ input handling

    def _schedule_project_refresh(self) -> None:
        # Debounce: typing a path fires on every keystroke.
        if self._refresh_after_id is not None:
            self.root.after_cancel(self._refresh_after_id)
        self._refresh_after_id = self.root.after(300, self._refresh_project_info)

    def _refresh_project_info(self) -> None:
        self._refresh_after_id = None
        self.project_ok = False
        raw = self.project_var.get().strip()
        labels = self.file_labels
        if not raw:
            labels["netlist"].configure(text="Choose the folder that contains your .ndf netlist.", foreground=COLOR_MUTED)
            labels["bom"].configure(text="", foreground=COLOR_MUTED)
            labels["pdf"].configure(text="", foreground=COLOR_MUTED)
        else:
            try:
                files = discover_project(Path(raw))
            except ProjectDiscoveryError as exc:
                labels["netlist"].configure(text=str(exc), foreground=COLOR_BAD)
                labels["bom"].configure(text="")
                labels["pdf"].configure(text="")
            else:
                self.project_ok = True
                labels["netlist"].configure(text=files.netlist_path.name, foreground=COLOR_OK)
                if files.bom_path:
                    labels["bom"].configure(text=files.bom_path.name, foreground=COLOR_OK)
                else:
                    labels["bom"].configure(
                        text="none - value-based checks will be limited", foreground=COLOR_MISSING
                    )
                if files.pdf_path:
                    labels["pdf"].configure(text=files.pdf_path.name, foreground=COLOR_OK)
                else:
                    labels["pdf"].configure(text="none - report without schematic snippets", foreground=COLOR_MISSING)
        self._update_output_hint()
        self._update_run_state()

    def _update_output_hint(self) -> None:
        if self.output_var.get().strip():
            self.output_hint.configure(text="")
        elif self.project_ok:
            target = default_output_dir(Path(self.project_var.get().strip()))
            self.output_hint.configure(text=f"Leave empty to use the default: {target}")
        else:
            self.output_hint.configure(text="Leave empty to use the default (a 'Reports' folder next to the project).")

    def _update_rule_count(self) -> None:
        enabled = sum(v.get() for v in self.rule_vars.values())
        self.rule_count_label.configure(text=f"{enabled} of {len(self.rules)} checks enabled")
        self._update_run_state()

    def _update_run_state(self) -> None:
        if not hasattr(self, "run_btn"):
            return
        running = self.worker is not None
        ready = self.project_ok and any(v.get() for v in self.rule_vars.values())
        self.run_btn.configure(state="normal" if (ready and not running) else "disabled")

    def _set_all_rules(self, value: bool) -> None:
        for var in self.rule_vars.values():
            var.set(value)

    def reset_thresholds(self) -> None:
        for spec in config.TUNABLE_THRESHOLDS:
            self.threshold_vars[spec.key].set(f"{spec.default:g}")

    def browse_project(self) -> None:
        current = self.project_var.get().strip()
        initial = current if current and Path(current).is_dir() else str(Path.home())
        chosen = filedialog.askdirectory(
            parent=self.root, initialdir=initial, title="Choose the project folder (with the .ndf netlist)"
        )
        if chosen:
            self.project_var.set(str(Path(chosen)))

    def browse_output(self) -> None:
        current = self.output_var.get().strip() or self.project_var.get().strip()
        initial = current if current and Path(current).is_dir() else str(Path.home())
        chosen = filedialog.askdirectory(parent=self.root, initialdir=initial, title="Choose where to save the report")
        if chosen:
            self.output_var.set(str(Path(chosen)))

    # ------------------------------------------------------------ settings

    def _collect_thresholds(self) -> Dict[str, object]:
        """Validated thresholds; raises ValueError with a user-facing message."""

        raw = {key: var.get().strip().replace(",", ".") for key, var in self.threshold_vars.items()}
        return config.validate_thresholds(raw)

    def current_settings(self, thresholds: Optional[Dict] = None) -> LintSettings:
        if thresholds is None:
            try:
                thresholds = self._collect_thresholds()
            except ValueError:
                thresholds = dict(self.settings.thresholds)  # keep the last valid ones
        defaults = {t.key: t.default for t in config.TUNABLE_THRESHOLDS}
        non_default = {k: v for k, v in thresholds.items() if float(v) != float(defaults[k])}
        return LintSettings(
            disabled_rules=sorted(rid for rid, var in self.rule_vars.items() if not var.get()),
            thresholds=non_default,
            project_dir=self.project_var.get().strip(),
            output_dir=self.output_var.get().strip(),
            open_report=bool(self.open_report_var.get()),
        )

    def _apply_profile(self, profile: LintSettings) -> None:
        for rule_id, var in self.rule_vars.items():
            var.set(rule_id not in profile.disabled_rules)
        for spec in config.TUNABLE_THRESHOLDS:
            self.threshold_vars[spec.key].set(f"{profile.thresholds.get(spec.key, spec.default):g}")

    def load_profile(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.root, title="Load check profile", filetypes=[("Linter profile", "*.json"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            self._apply_profile(load_profile(Path(path)))
        except ValueError as exc:
            messagebox.showerror("Could not load profile", str(exc), parent=self.root)
            return
        self.log(f"Loaded check profile {path}")

    def save_profile(self) -> None:
        try:
            thresholds = self._collect_thresholds()
        except ValueError as exc:
            self._show_threshold_error(exc)
            return
        path = filedialog.asksaveasfilename(
            parent=self.root, title="Save check profile", defaultextension=".json",
            initialfile="linter-profile.json", filetypes=[("Linter profile", "*.json")],
        )
        if not path:
            return
        try:
            save_profile(self.current_settings(thresholds), Path(path))
        except OSError as exc:
            messagebox.showerror("Could not save profile", str(exc), parent=self.root)
            return
        self.log(f"Saved check profile to {path}")

    def _show_threshold_error(self, exc: Exception) -> None:
        self.notebook.select(1)
        messagebox.showerror("Invalid threshold", str(exc), parent=self.root)

    # ------------------------------------------------------------- running

    def run_checks(self) -> None:
        if self.worker is not None:
            return
        try:
            thresholds = self._collect_thresholds()
        except ValueError as exc:
            self._show_threshold_error(exc)
            return
        enabled = {rid for rid, var in self.rule_vars.items() if var.get()}
        project_dir = Path(self.project_var.get().strip())
        output_raw = self.output_var.get().strip()
        output_dir = Path(output_raw) if output_raw else None

        self.settings = self.current_settings(thresholds)
        if self.persist:
            save_settings(self.settings)

        self._clear_summary()
        self.last_result = None
        self.open_report_btn.configure(state="disabled")
        self.open_folder_btn.configure(state="disabled")
        self.notebook.select(self.log_tab)
        self.log(f"--- Analyzing {project_dir} ---")
        self.progress.configure(mode="indeterminate")
        self.progress.start(12)
        self._set_status("Running...", COLOR_MUTED)

        def work() -> None:
            try:
                result = run_pipeline(
                    project_dir, output_dir, enabled_rules=enabled, thresholds=thresholds,
                    progress=lambda msg: self.queue.put(("progress", msg)),
                )
            except Exception as exc:  # noqa: BLE001 -- everything must reach the GUI thread
                self.queue.put(("error", exc, traceback.format_exc()))
            else:
                self.queue.put(("done", result))

        self.worker = threading.Thread(target=work, name="linter-analysis", daemon=True)
        self.worker.start()
        self._update_run_state()

    def _poll_queue(self) -> None:
        try:
            while True:
                message = self.queue.get_nowait()
                kind = message[0]
                if kind == "progress":
                    self.log(message[1])
                    self._set_status(message[1] + "...", COLOR_MUTED)
                elif kind == "done":
                    self._finish_ok(message[1])
                elif kind == "error":
                    self._finish_error(message[1], message[2])
        except queue.Empty:
            pass
        self.root.after(POLL_MS, self._poll_queue)

    def _end_run(self, exit_code: int) -> None:
        self.progress.stop()
        self.progress.configure(mode="determinate", value=0)
        self.worker = None
        self.last_exit_code = exit_code
        self._update_run_state()
        if self.on_finished is not None:
            self.on_finished(exit_code)

    def _finish_ok(self, result: PipelineResult) -> None:
        self.last_result = result
        counts = {sev: sum(1 for f in result.findings if f.severity == sev) for sev in Severity}
        self.log(
            f"Done: {_plural(counts[Severity.ERROR], 'error')}, {_plural(counts[Severity.WARNING], 'warning')}, "
            f"{_plural(counts[Severity.INFO], 'info')} ({len(result.graph.components)} components, "
            f"{len(result.graph.nets)} nets)",
            "ok",
        )
        self.log(f"Report: {result.report_path}")
        self._show_summary(counts)
        self._set_status("Finished. Click 'Open report' to view the findings.", COLOR_OK)
        self.open_report_btn.configure(state="normal")
        self.open_folder_btn.configure(state="normal")
        self._end_run(1 if counts[Severity.ERROR] else 0)
        if self.open_report_var.get():
            self.open_report()

    def _finish_error(self, exc: Exception, tb: str) -> None:
        for exc_type, title, prefix in _INPUT_ERRORS:
            if isinstance(exc, exc_type):
                self.log(f"{title}: {exc}", "error")
                self._set_status(title + ".", COLOR_BAD)
                self._end_run(2)
                messagebox.showerror(title, prefix + str(exc), parent=self.root)
                return
        if isinstance(exc, PermissionError):
            title, text = "Could not write the report", (
                f"{exc}\n\nIs the report still open in another program, or is the folder read-only? "
                "Close it or choose a different report folder."
            )
        else:
            title, text = "Unexpected error", (
                f"The analysis failed with an unexpected error:\n\n{exc}\n\n"
                "Details are in the Log tab - please send them to the tool's maintainer."
            )
        self.log(tb, "error")
        self._set_status(title + ".", COLOR_BAD)
        self._end_run(5)
        messagebox.showerror(title, text, parent=self.root)

    # ---------------------------------------------------------------- output

    def log(self, text: str, tag: Optional[str] = None) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text.rstrip("\n") + "\n", (tag,) if tag else ())
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _set_status(self, text: str, color: str) -> None:
        self.status_label.configure(text=text, foreground=color)

    def _clear_summary(self) -> None:
        for child in self.summary_frame.winfo_children():
            child.destroy()

    def _show_summary(self, counts: Dict[Severity, int]) -> None:
        self._clear_summary()
        for sev, word in ((Severity.ERROR, "error"), (Severity.WARNING, "warning"), (Severity.INFO, "info")):
            n = counts[sev]
            ttk.Label(
                self.summary_frame, text=_plural(n, word), font=self.font_big,
                foreground=SEVERITY_COLORS[sev] if n else COLOR_MUTED,
            ).pack(side="left", padx=(0, 16))

    def open_report(self) -> None:
        if self.last_result is not None:
            self._open(self.last_result.report_path)

    def open_output_folder(self) -> None:
        if self.last_result is not None:
            self._open(self.last_result.report_path.parent)

    def _open(self, path: Path) -> None:
        try:
            open_path(path)
        except OSError as exc:
            messagebox.showerror("Could not open", f"{path}\n\n{exc}", parent=self.root)

    def show_help(self) -> None:
        messagebox.showinfo(
            "How to use",
            "1. Choose the project folder. It must contain exactly one netlist (.ndf), and can also contain "
            "one eBOM (.csv) and one schematic PDF (.pdf). With an eBOM, value-based checks work better; "
            "with a PDF, the report shows schematic snippets for each finding.\n\n"
            "2. Optionally choose which checks to run (Checks tab) and adjust thresholds (Thresholds tab). "
            "Your choices are remembered for next time.\n\n"
            "3. Click 'Run checks'. The HTML report opens in your browser. Click the Errors/Warnings/Infos "
            "badges in the report to filter by severity.\n\n"
            "Errors are almost certainly wrong, warnings deserve a look, infos are often fine.",
            parent=self.root,
        )

    def show_about(self) -> None:
        messagebox.showinfo(
            "About",
            f"{APP_TITLE} {__version__}\n\nTopology-aware netlist linter for flat Zuken Design Gateway netlists. "
            "It checks structural connectivity only; it is not a substitute for engineering review.",
            parent=self.root,
        )

    def _report_callback_exception(self, exc_type, exc, tb) -> None:
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        try:
            self.log(text, "error")
        finally:
            messagebox.showerror("Unexpected error", f"{exc}\n\nDetails are in the Log tab.", parent=self.root)

    def on_close(self) -> None:
        if self.worker is not None and not messagebox.askyesno(
            "Analysis running", "An analysis is still running. Quit anyway?", parent=self.root
        ):
            return
        if self.persist:
            save_settings(self.current_settings())
        self.root.destroy()


def _enable_windows_dpi_awareness() -> None:
    """Crisp (non-blurry) text on high-DPI Windows displays."""

    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:  # noqa: BLE001 -- older Windows / already set: just keep default scaling
        pass


def _ensure_std_streams() -> None:
    # A windowed (no-console) exe or pythonw.exe has sys.stdout/stderr = None,
    # which breaks any library that prints or warns.
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))


def _smoke_test(project_dir: str, output_dir: str) -> int:
    """Non-interactive self-test for CI: drives the real window through one
    full run (same code path as clicking 'Run checks') and returns the exit
    code (0/1 like the CLI; 2+ on failure)."""

    root = tk.Tk()
    app = LinterApp(root, settings=LintSettings(project_dir=project_dir, output_dir=output_dir, open_report=False), persist=False)
    app._refresh_project_info()
    if not app.project_ok or len(app.rules) == 0:
        root.destroy()
        return 2
    codes: List[int] = []

    def finished(code: int) -> None:
        codes.append(code)
        root.after(0, root.destroy)

    app.on_finished = finished
    messagebox.showerror = lambda *a, **k: None  # never block CI on a dialog
    root.after(200, app.run_checks)
    root.after(300_000, root.destroy)  # hard timeout
    root.mainloop()
    return codes[0] if codes else 6


def main(argv: Optional[List[str]] = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    _ensure_std_streams()
    _enable_windows_dpi_awareness()

    if argv[:1] == ["--smoke-test"] and len(argv) == 3:
        sys.exit(_smoke_test(argv[1], argv[2]))

    root = tk.Tk()
    if sys.platform.startswith("linux"):
        style = ttk.Style(root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
    app = LinterApp(root)
    if argv and Path(argv[0]).is_dir():  # e.g. a folder dropped onto the .exe
        app.project_var.set(str(Path(argv[0]).resolve()))
    root.mainloop()


if __name__ == "__main__":
    main()
