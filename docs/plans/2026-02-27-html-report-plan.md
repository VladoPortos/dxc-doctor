# HTML Report Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a self-contained HTML report (`report.html`) with collapsible panels, search, and dark theme alongside existing outputs.

**Architecture:** New `html_report.py` module with a single `generate_html_report()` function that builds a complete HTML string. Called from `report.py:write_report()`. Zero dependencies.

**Tech Stack:** Python 3, vanilla HTML/CSS/JS, pytest

**Design doc:** `docs/plans/2026-02-27-html-report-design.md`

---

### Task 1: Test for HTML report generation

**Files:**
- Modify: `tests/test_core.py`

**Step 1: Write the failing test**

Add to `tests/test_core.py`:

```python
def test_generate_html_report():
    """HTML report should be a valid self-contained HTML string."""
    from dxc_doctor.html_report import generate_html_report

    results = {
        "os_info": [
            CheckResult(name="kernel", label="Kernel Version", status="ok", output="6.1.0", duration=0.02),
            CheckResult(name="memory", label="Memory Info", status="warning", output="MemTotal: 8GB", error="Low memory", duration=0.1),
        ],
        "docker": [
            CheckResult(name="version", label="Docker Version", status="error", output="", error="not found", duration=0.5),
        ],
    }
    plugins = {
        "os_info": PluginManifest(name="os_info", label="OS Information", description="OS info", category="system"),
        "docker": PluginManifest(name="docker", label="Docker", description="Docker info", category="containers"),
    }

    html = generate_html_report(results, plugins)

    # Basic structure
    assert "<!DOCTYPE html>" in html
    assert "<html" in html
    assert "</html>" in html

    # Content present
    assert "Kernel Version" in html
    assert "Memory Info" in html
    assert "Docker Version" in html
    assert "6.1.0" in html

    # Status indicators present
    assert "ok" in html.lower() or "✓" in html or "#00ff41" in html
    assert "error" in html.lower() or "✗" in html or "#ff4444" in html

    # Category sections
    assert "system" in html.lower()
    assert "containers" in html.lower()

    # Search input exists
    assert 'type="search"' in html or 'type="text"' in html

    # Self-contained (no external links)
    assert "http://" not in html
    assert "https://" not in html
```

**Step 2: Run test to verify it fails**

Run: `cd /mnt/e/dxc-doctor && python -m pytest tests/test_core.py::test_generate_html_report -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'dxc_doctor.html_report'`

---

### Task 2: Create html_report.py — scaffold and data preparation

**Files:**
- Create: `src/dxc_doctor/html_report.py`

**Step 1: Create the module with data preparation logic**

```python
"""Generate a self-contained HTML diagnostic report."""

from __future__ import annotations

import html as html_module
from datetime import datetime

from .models import CheckResult, PluginManifest

# Category display order
CATEGORY_ORDER = ["system", "containers", "network", "security", "software", "storage", "hardware", "general"]

STATUS_ICONS = {
    "ok": "✓",
    "warning": "⚠",
    "error": "✗",
    "skipped": "−",
}


def _group_by_category(
    all_results: dict[str, list[CheckResult]],
    plugins: dict[str, PluginManifest],
) -> list[tuple[str, list[tuple[PluginManifest, list[CheckResult]]]]]:
    """Group results by category, ordered by CATEGORY_ORDER."""
    categories: dict[str, list[tuple[PluginManifest, list[CheckResult]]]] = {}
    for plugin_name, results in all_results.items():
        plugin = plugins.get(plugin_name)
        if plugin is None:
            continue
        cat = plugin.category or "general"
        categories.setdefault(cat, []).append((plugin, results))

    ordered = []
    for cat in CATEGORY_ORDER:
        if cat in categories:
            ordered.append((cat, categories[cat]))
    # Any categories not in CATEGORY_ORDER go at the end
    for cat in categories:
        if cat not in CATEGORY_ORDER:
            ordered.append((cat, categories[cat]))
    return ordered


def _count_statuses(all_results: dict[str, list[CheckResult]]) -> dict[str, int]:
    """Count checks by status."""
    counts = {"total": 0, "ok": 0, "warning": 0, "error": 0, "skipped": 0}
    for results in all_results.values():
        for r in results:
            counts["total"] += 1
            if r.status in counts:
                counts[r.status] += 1
    return counts


def _esc(text: str) -> str:
    """HTML-escape a string."""
    return html_module.escape(text)


def generate_html_report(
    all_results: dict[str, list[CheckResult]],
    plugins: dict[str, PluginManifest],
) -> str:
    """Return a complete, self-contained HTML report string."""
    counts = _count_statuses(all_results)
    grouped = _group_by_category(all_results, plugins)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build check panels HTML
    checks_html = _build_checks_html(grouped)

    # Build category nav HTML
    nav_html = "".join(
        f'<a href="#cat-{_esc(cat)}" class="nav-link">{_esc(cat.title())}</a>'
        for cat, _ in grouped
    )

    return _HTML_TEMPLATE.format(
        timestamp=_esc(timestamp),
        total=counts["total"],
        ok=counts["ok"],
        warnings=counts["warning"],
        errors=counts["error"],
        skipped=counts["skipped"],
        nav_links=nav_html,
        checks=checks_html,
    )


def _build_checks_html(grouped):
    """Build the main content: category sections with check panels."""
    parts = []
    for cat, plugin_results in grouped:
        parts.append(f'<section id="cat-{_esc(cat)}">')
        parts.append(f'<h2 class="category-header">{_esc(cat.title())}</h2>')
        for plugin, results in plugin_results:
            for r in results:
                open_attr = ' open' if r.status in ("warning", "error") else ""
                status_class = r.status
                icon = STATUS_ICONS.get(r.status, "?")
                duration = f"{r.duration:.2f}s" if r.duration else ""
                error_html = ""
                if r.error:
                    error_html = f'<div class="check-error">{_esc(r.error)}</div>'
                output_html = ""
                if r.output:
                    output_html = f'<pre class="check-output">{_esc(r.output)}</pre>'

                parts.append(f'''<details class="check-panel status-{status_class}"{open_attr}>
<summary class="check-summary">
<span class="status-icon {status_class}">{icon}</span>
<span class="check-label">{_esc(r.label)}</span>
<span class="check-module">{_esc(plugin.label)}</span>
<span class="check-duration">{duration}</span>
</summary>
<div class="check-body">
{error_html}{output_html}
</div>
</details>''')
        parts.append('</section>')
    return "\n".join(parts)


_HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DXC Doctor Report</title>
<style>
''' + '''{css}''' + '''
</style>
</head>
<body>
<header>
<div class="header-top">
<h1>DXC Doctor Report</h1>
<div class="header-controls">
<input type="search" id="search" placeholder="Search checks..." autocomplete="off">
<button onclick="expandAll()">Expand All</button>
<button onclick="collapseAll()">Collapse All</button>
</div>
</div>
<div class="stats">
<span class="stat">Generated: {timestamp}</span>
<span class="stat">Total: {total}</span>
<span class="stat stat-ok">OK: {ok}</span>
<span class="stat stat-warning">Warnings: {warnings}</span>
<span class="stat stat-error">Errors: {errors}</span>
<span class="stat stat-skipped" id="visible-count"></span>
</div>
<nav class="category-nav">{nav_links}</nav>
</header>
<main>{checks}</main>
<script>
''' + '''{js}''' + '''
</script>
</body>
</html>'''
```

**NOTE:** The `{css}` and `{js}` placeholders in `_HTML_TEMPLATE` are literal — they'll be replaced in Tasks 3 and 4 by embedding the actual CSS/JS strings directly into the template. The `.format()` call uses `{{` and `}}` to escape braces in CSS/JS, or we concatenate strings instead of using `.format()` for the template itself. The actual approach: build the final HTML by concatenating parts, not by `.format()` on the CSS/JS section.

**Step 2: Run test**

Run: `cd /mnt/e/dxc-doctor && python -m pytest tests/test_core.py::test_generate_html_report -v`
Expected: May still fail due to template placeholders. We iterate in next tasks.

---

### Task 3: Complete the HTML template with CSS

**Files:**
- Modify: `src/dxc_doctor/html_report.py`

**Step 1: Replace the `_HTML_TEMPLATE` with a working template**

Replace the template string approach with direct string concatenation. The `generate_html_report` function assembles the full HTML by concatenating: doctype + head (with inline CSS) + body (with header, nav, main content, inline JS). The CSS provides:

- Dark theme: `body { background: #1a1a2e; color: #e0e0e0; }`
- Header: sticky, dark background, flex layout for controls
- Category nav: horizontal pill links
- Check panels: `details` elements styled with left border color by status
- Status icons colored: `.ok { color: #00ff41 }`, `.warning { color: #ffd700 }`, `.error { color: #ff4444 }`
- `pre.check-output`: monospace, scrollable, subtle background
- `.check-error`: red text
- Responsive layout, smooth scroll behavior
- `mark` highlight style for search results
- Transitions on details open/close

Full CSS is ~120 lines. Key selectors:

```css
* { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; }
body { font-family: system-ui, sans-serif; background: #1a1a2e; color: #e0e0e0; padding: 0; }
header { position: sticky; top: 0; background: #0f0f23; padding: 1rem 2rem; z-index: 10; border-bottom: 1px solid #2a2a4a; }
.header-top { display: flex; justify-content: space-between; align-items: center; }
h1 { font-size: 1.5rem; color: #00ff41; }
#search { background: #1a1a2e; border: 1px solid #2a2a4a; color: #e0e0e0; padding: 0.5rem 1rem; border-radius: 4px; width: 300px; }
button { background: #16213e; border: 1px solid #2a2a4a; color: #e0e0e0; padding: 0.4rem 0.8rem; border-radius: 4px; cursor: pointer; }
button:hover { background: #1a2744; }
.stats { display: flex; gap: 1.5rem; margin-top: 0.5rem; font-size: 0.85rem; }
.stat-ok { color: #00ff41; }
.stat-warning { color: #ffd700; }
.stat-error { color: #ff4444; }
.category-nav { display: flex; gap: 0.5rem; margin-top: 0.75rem; flex-wrap: wrap; }
.nav-link { color: #8888aa; text-decoration: none; padding: 0.3rem 0.8rem; border-radius: 12px; background: #16213e; font-size: 0.85rem; }
.nav-link:hover { color: #e0e0e0; background: #1a2744; }
main { padding: 1rem 2rem 4rem; }
.category-header { color: #8888aa; font-size: 1.1rem; margin: 2rem 0 0.75rem; padding-bottom: 0.5rem; border-bottom: 1px solid #2a2a4a; text-transform: uppercase; letter-spacing: 0.1em; }
.check-panel { margin-bottom: 0.4rem; border-radius: 6px; background: #16213e; border-left: 4px solid #2a2a4a; }
.status-ok { border-left-color: #00ff41; }
.status-warning { border-left-color: #ffd700; }
.status-error { border-left-color: #ff4444; }
.check-summary { padding: 0.6rem 1rem; cursor: pointer; display: flex; align-items: center; gap: 0.75rem; list-style: none; }
.check-summary::-webkit-details-marker { display: none; }
.status-icon { font-weight: bold; width: 1.2rem; text-align: center; }
.status-icon.ok { color: #00ff41; }
.status-icon.warning { color: #ffd700; }
.status-icon.error { color: #ff4444; }
.status-icon.skipped { color: #666; }
.check-label { flex: 1; }
.check-module { color: #666; font-size: 0.8rem; }
.check-duration { color: #555; font-size: 0.8rem; font-family: monospace; }
.check-body { padding: 0 1rem 1rem; }
.check-output { background: #0f0f23; padding: 1rem; border-radius: 4px; overflow-x: auto; font-family: Consolas, 'Courier New', monospace; font-size: 0.85rem; line-height: 1.5; white-space: pre-wrap; word-break: break-all; max-height: 500px; overflow-y: auto; }
.check-error { color: #ff4444; margin-bottom: 0.5rem; font-size: 0.9rem; }
mark { background: #ffd700; color: #000; border-radius: 2px; padding: 0 2px; }
.hidden { display: none !important; }
```

**Step 2: Run test**

Run: `cd /mnt/e/dxc-doctor && python -m pytest tests/test_core.py::test_generate_html_report -v`
Expected: PASS (basic structure and content assertions should match)

---

### Task 4: Add JavaScript for search, expand/collapse

**Files:**
- Modify: `src/dxc_doctor/html_report.py`

**Step 1: Add inline JS to the template**

The JS provides three features:

1. **Search** — `input` event on `#search`. For each `.check-panel`, check if `textContent` includes query (case-insensitive). Toggle `.hidden` class. Update visible count in `#visible-count`.

2. **Expand All** — Open all visible `<details>` elements.

3. **Collapse All** — Close all `<details>` elements.

```javascript
(function() {
  const search = document.getElementById('search');
  const panels = document.querySelectorAll('.check-panel');
  const visibleCount = document.getElementById('visible-count');
  let debounceTimer;

  search.addEventListener('input', function() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(doSearch, 150);
  });

  function doSearch() {
    const q = search.value.trim().toLowerCase();
    let shown = 0;
    panels.forEach(panel => {
      if (!q) {
        panel.classList.remove('hidden');
        // Remove old highlights
        panel.querySelectorAll('mark').forEach(m => {
          m.replaceWith(m.textContent);
        });
        shown++;
        return;
      }
      const text = panel.textContent.toLowerCase();
      if (text.includes(q)) {
        panel.classList.remove('hidden');
        shown++;
      } else {
        panel.classList.add('hidden');
      }
    });
    visibleCount.textContent = q ? 'Showing: ' + shown : '';
  }
})();

function expandAll() {
  document.querySelectorAll('.check-panel:not(.hidden)').forEach(d => d.open = true);
}

function collapseAll() {
  document.querySelectorAll('.check-panel').forEach(d => d.open = false);
}
```

**Step 2: Run test**

Run: `cd /mnt/e/dxc-doctor && python -m pytest tests/test_core.py::test_generate_html_report -v`
Expected: PASS

---

### Task 5: Test for write_report producing report.html

**Files:**
- Modify: `tests/test_core.py`

**Step 1: Update existing test_write_report to also check for report.html**

Add to the existing `test_write_report` function:

```python
    assert os.path.exists(os.path.join(out, "report.html"))
    with open(os.path.join(out, "report.html")) as f:
        html_content = f.read()
    assert "<!DOCTYPE html>" in html_content
    assert "Check 1" in html_content
```

**Step 2: Run test to verify it fails**

Run: `cd /mnt/e/dxc-doctor && python -m pytest tests/test_core.py::test_write_report -v`
Expected: FAIL — `report.html` does not exist yet

---

### Task 6: Integrate html_report into report.py

**Files:**
- Modify: `src/dxc_doctor/report.py:11` (add import)
- Modify: `src/dxc_doctor/report.py:101-104` (add HTML generation before return)

**Step 1: Add import at top of report.py**

After line 11 (`from .models import CheckResult, PluginManifest`), add:

```python
from .html_report import generate_html_report
```

**Step 2: Add HTML report generation before the return statement**

Before line 104 (`return output_dir`), add:

```python
    # Write HTML report
    html_content = generate_html_report(all_results, plugins)
    with open(os.path.join(output_dir, "report.html"), "w") as f:
        f.write(html_content)
```

**Step 3: Run test**

Run: `cd /mnt/e/dxc-doctor && python -m pytest tests/test_core.py::test_write_report -v`
Expected: PASS

---

### Task 7: Test with edge cases

**Files:**
- Modify: `tests/test_core.py`

**Step 1: Write tests for edge cases**

```python
def test_html_report_empty_results():
    """HTML report should handle empty results."""
    from dxc_doctor.html_report import generate_html_report

    html = generate_html_report({}, {})
    assert "<!DOCTYPE html>" in html
    assert "Total: 0" in html


def test_html_report_special_characters():
    """HTML report should escape special characters in output."""
    from dxc_doctor.html_report import generate_html_report

    results = {
        "test": [
            CheckResult(
                name="xss",
                label="XSS <script>alert('xss')</script>",
                status="ok",
                output="<b>bold</b> & 'quotes' \"double\"",
                duration=0.01,
            ),
        ],
    }
    plugins = {
        "test": PluginManifest(name="test", label="Test", description="t", category="system"),
    }

    html = generate_html_report(results, plugins)
    # Script tags must be escaped, not rendered
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;b&gt;" in html
    assert "&amp;" in html


def test_html_report_large_output():
    """HTML report should handle large check outputs without truncation."""
    from dxc_doctor.html_report import generate_html_report

    big_output = "line {}\n" * 10000
    results = {
        "test": [
            CheckResult(name="big", label="Big Output", status="ok", output=big_output, duration=1.0),
        ],
    }
    plugins = {
        "test": PluginManifest(name="test", label="Test", description="t", category="system"),
    }

    html = generate_html_report(results, plugins)
    assert "Big Output" in html
    # Output should not be truncated
    assert "line {}" in html
```

**Step 2: Run all tests**

Run: `cd /mnt/e/dxc-doctor && python -m pytest tests/test_core.py -v`
Expected: ALL PASS

---

### Task 8: Run full test suite and commit

**Step 1: Run all tests**

Run: `cd /mnt/e/dxc-doctor && python -m pytest tests/ -v`
Expected: ALL PASS

**Step 2: Commit**

```bash
cd /mnt/e/dxc-doctor
git add src/dxc_doctor/html_report.py tests/test_core.py src/dxc_doctor/report.py
git commit -m "feat: add self-contained HTML report with collapsible panels and search

Generates report.html alongside existing summary.json and summary.txt.
Features dark terminal theme, per-check collapsible panels, full-text
search, category navigation, and expand/collapse all controls."
```

---

### Task 9: Visual verification

**Step 1: Generate a sample report for visual inspection**

Run: `cd /mnt/e/dxc-doctor && python -c "
from dxc_doctor.models import CheckResult, PluginManifest
from dxc_doctor.html_report import generate_html_report

results = {
    'os_info': [
        CheckResult('kernel', 'Kernel Version', 'ok', 'Linux 6.1.0-generic', '', 0.02),
        CheckResult('memory', 'Memory Info', 'warning', 'MemTotal: 8GB\nMemFree: 512MB\nSwapTotal: 4GB', 'Low available memory', 0.15),
        CheckResult('cpu', 'CPU Info', 'ok', 'Model: Intel i7-9700K\nCores: 8\nLoad: 1.23, 0.87, 0.65', '', 0.03),
    ],
    'docker': [
        CheckResult('version', 'Docker Version', 'error', '', 'Docker daemon not running', 0.5),
        CheckResult('images', 'Docker Images', 'error', '', 'Cannot connect to Docker', 0.1),
    ],
    'network': [
        CheckResult('interfaces', 'Network Interfaces', 'ok', 'lo: 127.0.0.1\neth0: 192.168.1.100\neth1: 10.0.0.5', '', 0.04),
        CheckResult('dns', 'DNS Resolution', 'ok', 'google.com -> 142.250.80.46\nResolve time: 12ms', '', 0.8),
        CheckResult('routes', 'Routing Table', 'ok', 'default via 192.168.1.1 dev eth0\n10.0.0.0/8 via 10.0.0.1 dev eth1', '', 0.02),
    ],
    'security': [
        CheckResult('selinux', 'SELinux Status', 'warning', 'SELinux status: permissive', 'SELinux not enforcing', 0.05),
    ],
}
plugins = {
    'os_info': PluginManifest('os_info', 'OS Information', 'System info', category='system'),
    'docker': PluginManifest('docker', 'Docker', 'Docker info', category='containers'),
    'network': PluginManifest('network', 'Network', 'Network info', category='network'),
    'security': PluginManifest('security', 'Security', 'Security info', category='security'),
}

html = generate_html_report(results, plugins)
with open('/tmp/dxc-doctor-preview.html', 'w') as f:
    f.write(html)
print('Preview saved to /tmp/dxc-doctor-preview.html')
"`

**Step 2: Open in browser and verify visually**

Check: dark theme, collapsible panels, status colors, search works, category nav works, expand/collapse all works.

**Step 3: Fix any visual issues found, re-run tests, commit fixes if needed**
