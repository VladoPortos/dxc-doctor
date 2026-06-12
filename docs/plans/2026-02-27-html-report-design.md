# HTML Report Design for DXC Doctor

**Date:** 2026-02-27
**Status:** Approved

## Summary

Add a self-contained, single-file HTML report (`report.html`) generated alongside existing `summary.json` and `summary.txt` outputs. The report features collapsible per-check panels, full-text search, category navigation, and a dark terminal-inspired theme.

## Approach

**Pure Inline HTML** - A new Python module (`html_report.py`) builds a complete HTML string with all CSS and JS inlined. Zero external dependencies. Compatible with the existing PyInstaller single-binary build.

## Architecture

### New file: `src/dxc_doctor/html_report.py`

Single public function:

```python
def generate_html_report(
    all_results: dict[str, list[CheckResult]],
    plugins: dict[str, PluginManifest],
) -> str:
```

### Integration point: `src/dxc_doctor/report.py`

In `write_report()`, after existing summary generation:

```python
from .html_report import generate_html_report
html = generate_html_report(all_results, plugins)
(output_path / "report.html").write_text(html)
```

## Report Layout

```
┌──────────────────────────────────────────────────────┐
│  DXC Doctor Report       [search box]       [stats]  │
│  Generated: 2026-02-27                               │
├──────────────────────────────────────────────────────┤
│  [System] [Containers] [Network] [Security] [...]    │
├──────────────────────────────────────────────────────┤
│                                                      │
│  ── System ────────────────────────────────────────  │
│  ▸ [+] Kernel Version                     0.02s     │
│  ▾ [!] Memory Information                 0.15s     │
│  │  MemTotal: 32768000 kB                           │
│  │  MemFree:  12345000 kB                           │
│  ▸ [x] Docker Version                     0.50s     │
│                                                      │
│  ── Containers ────────────────────────────────────  │
│  ...                                                │
└──────────────────────────────────────────────────────┘
```

## Features

### Header
- Title, generation timestamp
- Summary stats: total checks, OK count, warning count, error count

### Category Navigation
- Horizontal bar with anchor links to each category section
- Smooth-scroll on click

### Check Panels
- HTML `<details>` element per check (native collapsible, no JS needed for basic behavior)
- Status icon: green checkmark (ok), yellow warning triangle (warning), red X (error)
- Check label, module name (muted), duration badge
- `<pre>` block with output content
- Error messages shown in red
- Default state: errors/warnings expanded, OK checks collapsed

### Search
- Single search input in the header
- Filters panels by matching against label text + output content
- Non-matching panels hidden via `display:none`
- Matched text highlighted with `<mark>` tags
- "Expand All" / "Collapse All" buttons

### Visual Style
- Dark terminal-inspired theme
- Background: `#1a1a2e`, panels: `#16213e`, text: `#e0e0e0`
- Monospace for output (`Consolas, 'Courier New', monospace`)
- Sans-serif for UI chrome (`system-ui`)
- Status colors: `#00ff41` (ok), `#ffd700` (warning), `#ff4444` (error)
- Subtle borders and box-shadows for depth
- Smooth CSS transitions on expand/collapse

## JavaScript (~50 lines, vanilla)
- Search filtering with debounce
- Expand/collapse all toggle
- Visible count update after filtering

## Integration Notes
- No new dependencies
- No changes to PyInstaller spec needed
- No changes to existing output formats
- HTML file included in ZIP output automatically (already zips entire output dir)
