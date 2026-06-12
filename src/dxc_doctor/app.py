"""Main Textual App for DXC Doctor."""

from __future__ import annotations

import traceback

from rich.markup import escape
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Checkbox, Footer, Input, ProgressBar, Static, TabbedContent, TabPane

from .config import default_output_dir
from .mascot import GREETING, RUNNING_MSG, DONE_MSG, ERROR_MSG
from .models import CheckDefinition, CheckResult, PluginManifest
from .plugin_manager import discover_plugins
from .report import create_zip, write_report
from .runner import run_selected_plugins_sync

STATUS_ICONS = {
    "ok": "[green]+[/]",
    "warning": "[yellow]![/]",
    "error": "[red]x[/]",
    "skipped": "[dim]-[/]",
    "running": "[cyan]*[/]",
}


class DXCDoctorApp(App):
    """DXC Doctor TUI application."""

    TITLE = "DXC Doctor"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("a", "select_all", "All"),
        ("n", "select_none", "None"),
        ("s", "do_start", "Start"),
    ]

    CSS = """
    Screen {
        layout: vertical;
    }

    #header-bar {
        height: 3;
        background: $primary-background;
        padding: 0 2;
        border-bottom: solid $primary;
    }

    #content {
        height: 1fr;
        border: solid $primary;
        margin: 0 1;
    }
    .section-label {
        text-style: bold;
        color: $accent;
        background: $primary-background;
        padding: 0 1;
        width: 100%;
        height: 1;
    }

    #module-tabs {
        height: 1fr;
        padding: 0 1;
    }
    #module-tabs Checkbox {
        height: 1;
        margin: 0;
        padding: 0 1;
        border: none;
        background: transparent;
    }
    #module-tabs Checkbox:focus {
        border: none;
        background: $primary-background;
    }

    #output-section {
        height: auto;
        padding: 0 1 1 1;
        border-top: solid $primary 30%;
    }
    #output-section .label {
        color: $text-muted;
        padding: 0 1;
        height: 1;
    }
    #output-section #output-path {
        margin: 0 1;
    }
    #output-section Checkbox {
        height: 1;
        margin: 0;
        padding: 0 1;
        border: none;
        background: transparent;
    }
    #output-section Checkbox:focus {
        border: none;
        background: $primary-background;
    }

    #progress-section {
        display: none;
        height: 1fr;
    }
    #check-log {
        height: 1fr;
        padding: 0 2;
    }
    #main-progress {
        margin: 1 2;
    }

    #results-section {
        display: none;
        height: 1fr;
    }
    #results-summary {
        padding: 1 2;
        height: auto;
    }
    #results-detail {
        height: 1fr;
        padding: 0 2;
    }
    #results-path {
        color: $text-muted;
        padding: 0 2 1 2;
        height: auto;
    }

    .btn-bar {
        height: 3;
        align: center middle;
        margin: 0 1;
    }
    .btn-bar Button {
        margin: 0 1;
        min-width: 20;
        border: ascii $panel;
    }
    .btn-bar Button:hover {
        border: ascii $accent;
    }
    .btn-bar Button:focus {
        border: ascii $accent;
    }
    #bar-main { display: block; }
    #bar-results { display: none; }
    """

    def __init__(self, args=None, plugins: list[PluginManifest] | None = None) -> None:
        super().__init__()
        self._args = args
        self._plugins: list[PluginManifest] = plugins if plugins is not None else []
        self._output_path = args.output if args else default_output_dir()
        self._diagnosis_active = False

    def compose(self) -> ComposeResult:
        if not self._plugins:
            self._plugins = discover_plugins()

        yield Vertical(
            Static("[bold cyan]DXC Doctor[/]  [green](^_^)[/]  [dim]v0.1.0[/]"),
            Static(GREETING, id="status-msg"),
            id="header-bar",
        )

        with Vertical(id="content"):
            with Vertical(id="main-section"):
                yield Static("  Select Modules", classes="section-label")
                categories: dict[str, list[PluginManifest]] = {}
                for p in self._plugins:
                    categories.setdefault(p.category, []).append(p)
                with TabbedContent(id="module-tabs"):
                    for cat, plugins in categories.items():
                        with TabPane(cat.capitalize(), id=f"cat-{cat}"):
                            for plugin in plugins:
                                if plugin.detected:
                                    yield Checkbox(
                                        f" {plugin.label}",
                                        value=True,
                                        id=f"plugin-{plugin.name}",
                                    )
                                else:
                                    reason = plugin.disabled_reason or "not detected"
                                    yield Checkbox(
                                        f" {plugin.label} [dim]({reason})[/]",
                                        value=False,
                                        disabled=True,
                                        id=f"plugin-{plugin.name}",
                                    )
                with Vertical(id="output-section"):
                    yield Static("Output folder", classes="label")
                    yield Input(value=self._output_path, id="output-path")
                    yield Checkbox(" Pack output into ZIP file", value=True, id="zip-output")

            with Vertical(id="progress-section"):
                yield Static("  Running Diagnostics", classes="section-label")
                yield VerticalScroll(id="check-log")
                yield ProgressBar(id="main-progress", total=100, show_eta=False)

            with Vertical(id="results-section"):
                yield Static("  Diagnostic Results", classes="section-label")
                yield Static("", id="results-summary")
                yield VerticalScroll(id="results-detail")
                yield Static("", id="results-path")

        yield Horizontal(
            Button("Start Diagnosis", variant="success", id="btn-start"),
            Button("Quit", variant="default", id="btn-quit-main"),
            id="bar-main",
            classes="btn-bar",
        )
        yield Horizontal(
            Button("Back", variant="primary", id="btn-back"),
            Button("Quit", variant="default", id="btn-quit-results"),
            id="bar-results",
            classes="btn-bar",
        )

        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid in ("btn-quit-main", "btn-quit-results"):
            self.exit()
        elif bid == "btn-start":
            self._start_diagnosis()
        elif bid == "btn-back":
            self._show_main()

    def action_do_start(self) -> None:
        if not self._diagnosis_active:
            self._start_diagnosis()

    def action_select_all(self) -> None:
        for cb in self.query(Checkbox):
            if cb.id and cb.id.startswith("plugin-") and not cb.disabled:
                cb.value = True

    def action_select_none(self) -> None:
        for cb in self.query(Checkbox):
            if cb.id and cb.id.startswith("plugin-"):
                cb.value = False

    def _start_diagnosis(self) -> None:
        if self._diagnosis_active:
            return

        selected_plugins = []
        for plugin in self._plugins:
            try:
                cb = self.query_one(f"#plugin-{plugin.name}", Checkbox)
                if cb.value:
                    selected_plugins.append(plugin)
            except Exception:
                pass

        if not selected_plugins:
            self.notify("Select at least one module.", severity="warning")
            return

        try:
            self._output_path = self.query_one("#output-path", Input).value
        except Exception:
            pass

        try:
            self._create_zip = self.query_one("#zip-output", Checkbox).value
        except Exception:
            self._create_zip = True

        total = sum(len(p.checks) for p in selected_plugins)
        self._diagnosis_active = True

        self.query_one("#main-section").styles.display = "none"
        self.query_one("#bar-main").styles.display = "none"
        self.query_one("#progress-section").styles.display = "block"

        bar = self.query_one("#main-progress", ProgressBar)
        bar.total = total
        bar.progress = 0

        self.query_one("#status-msg", Static).update(RUNNING_MSG)

        self._run_checks(selected_plugins)

    @work(thread=True)
    def _run_checks(self, plugins: list[PluginManifest]) -> None:
        def on_start(plugin_name: str, check: CheckDefinition) -> None:
            icon = STATUS_ICONS["running"]
            self.call_from_thread(
                self._log_check, check.name, f" {icon} {escape(check.label)} [dim]...[/]"
            )

        def on_done(plugin_name: str, result: CheckResult) -> None:
            icon = STATUS_ICONS.get(result.status, "?")
            short = result.output.splitlines()[0][:50] if result.output else result.error
            dots = "." * max(2, 44 - len(result.label))
            self.call_from_thread(
                self._update_check,
                result.name,
                f" {icon} {escape(result.label)} [dim]{dots}[/] {escape(short)}",
            )
            self.call_from_thread(self._advance_progress)

        try:
            all_results = run_selected_plugins_sync(plugins, on_start, on_done)
            plugins_map = {p.name: p for p in plugins}
            write_report(all_results, self._output_path, plugins_map)
            zip_path = ""
            if self._create_zip:
                zip_path = create_zip(self._output_path)
            self.call_from_thread(self._show_results, all_results, zip_path)
        except Exception:
            self.call_from_thread(
                self.notify, f"Error: {traceback.format_exc()[:500]}", severity="error"
            )
            self.call_from_thread(self._reset)

    def _log_check(self, name: str, text: str) -> None:
        logw = self.query_one("#check-log", VerticalScroll)
        logw.mount(Static(text, id=f"check-{name}"))
        logw.scroll_end()

    def _update_check(self, name: str, text: str) -> None:
        try:
            self.query_one(f"#check-{name}", Static).update(text)
        except Exception:
            pass

    def _advance_progress(self) -> None:
        try:
            self.query_one("#main-progress", ProgressBar).advance(1)
        except Exception:
            pass

    def _reset(self) -> None:
        self._diagnosis_active = False

    def _show_results(self, results: dict[str, list[CheckResult]], zip_path: str = "") -> None:
        self._diagnosis_active = False

        has_errors = any(
            r.status == "error" for checks in results.values() for r in checks
        )
        self.query_one("#status-msg", Static).update(ERROR_MSG if has_errors else DONE_MSG)

        ok = warn = err = skip = 0
        for checks in results.values():
            for r in checks:
                if r.status == "ok": ok += 1
                elif r.status == "warning": warn += 1
                elif r.status == "error": err += 1
                else: skip += 1

        total = ok + warn + err + skip
        self.query_one("#results-summary", Static).update(
            f"[bold]Summary:[/]  "
            f"[green]{ok} passed[/]  "
            f"[yellow]{warn} warnings[/]  "
            f"[red]{err} errors[/]  "
            f"[dim]{skip} skipped[/]  "
            f"[dim]({total} total)[/]"
        )

        detail = self.query_one("#results-detail", VerticalScroll)
        for plugin_name, checks in results.items():
            for r in checks:
                icon = STATUS_ICONS.get(r.status, "[dim]-[/]")
                short = (r.output.splitlines()[0][:50] if r.output else r.error) or r.status
                dots = "." * max(2, 44 - len(r.label))
                detail.mount(Static(f" {icon} {escape(r.label)} [dim]{dots}[/] {escape(short)}"))

        path_text = f"Output saved to: {self._output_path}"
        if zip_path:
            path_text += f"\n[bold]ZIP file: {zip_path}[/]"
        self.query_one("#results-path", Static).update(path_text)

        self.query_one("#progress-section").styles.display = "none"
        self.query_one("#results-section").styles.display = "block"
        self.query_one("#bar-results").styles.display = "block"

    def _show_main(self) -> None:
        self.query_one("#status-msg", Static).update(GREETING)
        self.query_one("#main-section").styles.display = "block"
        self.query_one("#bar-main").styles.display = "block"
        self.query_one("#bar-results").styles.display = "none"
        self.query_one("#progress-section").styles.display = "none"
        self.query_one("#results-section").styles.display = "none"

        # Clear dynamically mounted widgets so re-run doesn't hit DuplicateIds
        self.query_one("#check-log", VerticalScroll).remove_children()
        self.query_one("#results-detail", VerticalScroll).remove_children()
