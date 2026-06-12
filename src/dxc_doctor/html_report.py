"""Self-contained HTML report generator for DXC Doctor."""

from __future__ import annotations

import html as _html_mod
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import CheckResult, PluginManifest

CATEGORY_ORDER = [
    "system",
    "containers",
    "network",
    "security",
    "software",
    "storage",
    "hardware",
    "general",
]

STATUS_ICONS = {
    "ok": "✓",       # checkmark
    "warning": "⚠",  # warning sign
    "error": "✗",    # cross mark
    "skipped": "−",  # minus sign
}

# ---------------------------------------------------------------------------
# CSS (kept as a plain string constant -- no f-string interpolation)
# ---------------------------------------------------------------------------
_CSS = r"""
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{
  background:#1a1a2e;color:#e0e0e0;
  font-family:'Segoe UI',system-ui,-apple-system,sans-serif;
  line-height:1.5;padding:0;margin:0;
}
a{color:#64b5f6;text-decoration:none}
a:hover{text-decoration:underline}

/* header */
.header{
  position:sticky;top:0;z-index:100;
  background:#0f3460;padding:10px 24px;
  border-bottom:2px solid #1a1a2e;
}
.header-row{
  display:flex;flex-wrap:wrap;align-items:center;gap:12px;
}
.header-row + .header-row{margin-top:8px}
.header h1{font-size:1.3rem;color:#e94560;margin-right:auto}
.host-info{font-size:.8rem;color:#b0b0b0}
.host-info b{color:#e0e0e0;font-weight:600}
.header .stats{font-size:.85rem;color:#b0b0b0}
.header input[type="search"]{
  padding:6px 12px;border:1px solid #444;border-radius:4px;
  background:#1a1a2e;color:#e0e0e0;font-size:.9rem;width:220px;
}
.header button{
  padding:4px 12px;border:1px solid #444;border-radius:4px;
  background:#16213e;color:#e0e0e0;cursor:pointer;font-size:.8rem;
}
.header button:hover{background:#1a1a2e}
.cat-nav{display:flex;gap:8px;flex-wrap:wrap;font-size:.8rem;margin-right:auto}

/* status filter chips */
.filters{display:flex;gap:6px;flex-wrap:wrap}
.filter-chip{
  padding:4px 12px;border:1px solid #444;border-radius:14px;
  background:#16213e;color:#b0b0b0;cursor:pointer;font-size:.8rem;
  transition:background .15s,color .15s;
}
.filter-chip:hover{background:#1a1a2e}
.filter-chip.active{border-color:#e94560;color:#fff;background:#1a1a2e}
.filter-chip .dot{font-weight:bold;margin-right:4px}
.filter-chip[data-status="ok"] .dot{color:#00ff41}
.filter-chip[data-status="warning"] .dot{color:#ffd700}
.filter-chip[data-status="error"] .dot{color:#ff4444}
.filter-chip[data-status="skipped"] .dot{color:#888}

/* main */
.container{max-width:1100px;margin:24px auto;padding:0 16px}
.category-section{margin-bottom:32px}
.category-section h2{
  font-size:1.1rem;color:#e94560;
  border-bottom:1px solid #333;padding-bottom:6px;margin-bottom:12px;
}
.category-section h2 .cat-count{color:#888;font-size:.8rem;font-weight:normal}

/* check panels */
.check-panel{
  background:#16213e;border-radius:6px;margin-bottom:8px;
  border-left:4px solid #555;overflow:hidden;
  transition:border-left-color .15s;
}
.check-panel.status-ok{border-left-color:#00ff41}
.check-panel.status-warning{border-left-color:#ffd700}
.check-panel.status-error{border-left-color:#ff4444}
.check-panel.status-skipped{border-left-color:#888}

.check-panel summary{
  padding:10px 16px;cursor:pointer;display:flex;align-items:center;gap:10px;
  list-style:none;font-size:.9rem;
}
.check-panel summary:hover{background:#1a2540}
.check-panel summary::-webkit-details-marker{display:none}
.check-panel summary::marker{display:none}

.status-icon{font-weight:bold;font-size:1.1rem;width:1.2em;text-align:center}
.status-icon.ok{color:#00ff41}
.status-icon.warning{color:#ffd700}
.status-icon.error{color:#ff4444}
.status-icon.skipped{color:#888}

.check-label{flex:1;font-weight:600}
.check-module{color:#888;font-size:.8rem}
.check-duration{color:#666;font-size:.78rem;min-width:60px;text-align:right}

.check-body{
  padding:8px 16px 14px;border-top:1px solid #222;
}
.check-body pre{
  background:#111;padding:10px;border-radius:4px;
  font-family:'Cascadia Code','Fira Code',monospace;font-size:.82rem;
  white-space:pre-wrap;word-break:break-word;color:#ccc;
  max-height:400px;overflow:auto;
}
.check-body .error-text{color:#ff4444;margin-top:6px;font-size:.85rem}

mark{background:#ffd700;color:#000;border-radius:2px;padding:0 1px}

#visible-count{font-size:.8rem;color:#888;margin-left:8px}
.hidden{display:none !important}
"""

# ---------------------------------------------------------------------------
# JavaScript (plain string constant)
# ---------------------------------------------------------------------------
_JS = r"""
(function(){
  var searchInput = document.getElementById('search-input');
  var panels = Array.prototype.slice.call(document.querySelectorAll('.check-panel'));
  var sections = Array.prototype.slice.call(document.querySelectorAll('.category-section'));
  var chips = Array.prototype.slice.call(document.querySelectorAll('.filter-chip'));
  var countEl = document.getElementById('visible-count');
  var debounceTimer;
  var activeStatus = 'all';

  // Remember original label text for highlight rebuilding
  panels.forEach(function(p){
    var label = p.querySelector('.check-label');
    if(label) label.dataset.orig = label.textContent;
  });

  function highlightLabel(panel, q){
    var label = panel.querySelector('.check-label');
    if(!label) return;
    var orig = label.dataset.orig || '';
    while(label.firstChild) label.removeChild(label.firstChild);
    if(!q){
      label.appendChild(document.createTextNode(orig));
      return;
    }
    var lower = orig.toLowerCase();
    var idx = 0;
    while(true){
      var pos = lower.indexOf(q, idx);
      if(pos === -1){
        label.appendChild(document.createTextNode(orig.slice(idx)));
        break;
      }
      if(pos > idx) label.appendChild(document.createTextNode(orig.slice(idx, pos)));
      var mark = document.createElement('mark');
      mark.textContent = orig.slice(pos, pos + q.length);
      label.appendChild(mark);
      idx = pos + q.length;
    }
  }

  function applyFilters(){
    var q = searchInput.value.toLowerCase().trim();
    var visible = 0;
    panels.forEach(function(p){
      var statusOk = (activeStatus === 'all') || p.dataset.status === activeStatus;
      var searchOk = !q || p.textContent.toLowerCase().indexOf(q) !== -1;
      if(statusOk && searchOk){
        p.classList.remove('hidden');
        visible++;
      } else {
        p.classList.add('hidden');
      }
      highlightLabel(p, searchOk && q ? q : '');
    });
    // Hide category sections with no visible panels
    sections.forEach(function(s){
      var any = s.querySelector('.check-panel:not(.hidden)');
      if(any){ s.classList.remove('hidden'); } else { s.classList.add('hidden'); }
    });
    countEl.textContent = visible + ' / ' + panels.length + ' checks shown';
  }

  searchInput.addEventListener('input', function(){
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(applyFilters, 200);
  });

  chips.forEach(function(chip){
    chip.addEventListener('click', function(){
      activeStatus = chip.dataset.status;
      chips.forEach(function(c){ c.classList.toggle('active', c === chip); });
      applyFilters();
    });
  });

  window.expandAll = function(){
    panels.forEach(function(p){ if(!p.classList.contains('hidden')) p.open = true; });
  };
  window.collapseAll = function(){
    panels.forEach(function(p){ p.open = false; });
  };

  applyFilters();
})();
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _esc(text: str) -> str:
    """HTML-escape a string."""
    return _html_mod.escape(str(text), quote=True)


def _group_by_category(
    all_results: dict[str, list[CheckResult]],
    plugins: dict[str, PluginManifest],
) -> dict[str, list[tuple[str, CheckResult]]]:
    """Group check results by category.

    Returns {category: [(plugin_name, check_result), ...]}.
    """
    groups: dict[str, list[tuple[str, CheckResult]]] = {}
    for plugin_name, checks in all_results.items():
        cat = "general"
        if plugin_name in plugins:
            cat = plugins[plugin_name].category or "general"
        for cr in checks:
            groups.setdefault(cat, []).append((plugin_name, cr))
    return groups


def _count_statuses(all_results: dict[str, list[CheckResult]]) -> dict[str, int]:
    """Count total checks per status."""
    counts: dict[str, int] = {"ok": 0, "warning": 0, "error": 0, "skipped": 0}
    for checks in all_results.values():
        for cr in checks:
            counts[cr.status] = counts.get(cr.status, 0) + 1
    return counts


def _build_checks_html(
    grouped: dict[str, list[tuple[str, CheckResult]]],
    plugins: dict[str, PluginManifest],
) -> str:
    """Build the HTML for all category sections and check panels."""
    parts: list[str] = []

    # Sort categories by CATEGORY_ORDER, unknown at end
    order_map = {c: i for i, c in enumerate(CATEGORY_ORDER)}
    sorted_cats = sorted(grouped.keys(), key=lambda c: order_map.get(c, 999))

    for cat in sorted_cats:
        items = grouped[cat]
        cat_id = _esc(cat)
        cat_label = _esc(cat.replace("_", " ").title())

        parts.append(f'<div class="category-section" id="cat-{cat_id}">')
        parts.append(
            f'<h2>{cat_label} <span class="cat-count">({len(items)} checks)</span></h2>'
        )

        for plugin_name, cr in items:
            status = cr.status
            icon = STATUS_ICONS.get(status, "?")
            open_attr = ' open' if status in ("warning", "error") else ''
            duration_str = f"{cr.duration:.2f}s" if cr.duration else ""
            module_label = _esc(plugin_name)

            parts.append(
                f'<details class="check-panel status-{_esc(status)}"'
                f' data-status="{_esc(status)}"{open_attr}>'
                f"<summary>"
                f'<span class="status-icon {_esc(status)}">{icon}</span>'
                f'<span class="check-label">{_esc(cr.label)}</span>'
                f'<span class="check-module">{module_label}</span>'
                f'<span class="check-duration">{_esc(duration_str)}</span>'
                f"</summary>"
                f'<div class="check-body">'
            )
            if cr.output:
                parts.append(f"<pre>{_esc(cr.output)}</pre>")
            if cr.error:
                parts.append(f'<div class="error-text">{_esc(cr.error)}</div>')
            parts.append("</div></details>")

        parts.append("</div>")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_html_report(
    all_results: dict[str, list[CheckResult]],
    plugins: dict[str, PluginManifest],
    host_meta: dict | None = None,
) -> str:
    """Generate a self-contained HTML report string.

    Parameters
    ----------
    all_results : dict mapping plugin name to list of CheckResult
    plugins : dict mapping plugin name to PluginManifest
    host_meta : optional host metadata dict (hostname, os, kernel, ...)

    Returns
    -------
    str
        Complete HTML document as a string.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    counts = _count_statuses(all_results)
    total = sum(counts.values())
    grouped = _group_by_category(all_results, plugins)

    # Build category nav links
    order_map = {c: i for i, c in enumerate(CATEGORY_ORDER)}
    sorted_cats = sorted(grouped.keys(), key=lambda c: order_map.get(c, 999))
    nav_links = " ".join(
        f'<a href="#cat-{_esc(c)}">{_esc(c.replace("_", " ").title())}</a>'
        for c in sorted_cats
    )

    stats_text = (
        f'Total: {_esc(str(total))} checks &mdash; '
        f'<span style="color:#00ff41">{counts["ok"]} ok</span> &middot; '
        f'<span style="color:#ffd700">{counts["warning"]} warning</span> &middot; '
        f'<span style="color:#ff4444">{counts["error"]} error</span>'
    )
    if counts.get("skipped"):
        stats_text += f' &middot; <span style="color:#888">{counts["skipped"]} skipped</span>'

    host_html = ""
    if host_meta:
        bits = []
        if host_meta.get("hostname"):
            bits.append(f"<b>{_esc(host_meta['hostname'])}</b>")
        if host_meta.get("os"):
            bits.append(_esc(host_meta["os"]))
        if host_meta.get("kernel"):
            bits.append(f"kernel {_esc(host_meta['kernel'])}")
        if host_meta.get("arch"):
            bits.append(_esc(host_meta["arch"]))
        if host_meta.get("user"):
            bits.append(f"run by {_esc(host_meta['user'])}")
        if host_meta.get("tool_version"):
            bits.append(f"dxc-doctor {_esc(host_meta['tool_version'])}")
        host_html = f'<div class="host-info">{" &middot; ".join(bits)}</div>\n'

    filter_chips = (
        f'<div class="filters">'
        f'<span class="filter-chip active" data-status="all">All ({total})</span>'
        f'<span class="filter-chip" data-status="ok"><span class="dot">✓</span>{counts["ok"]}</span>'
        f'<span class="filter-chip" data-status="warning"><span class="dot">⚠</span>{counts["warning"]}</span>'
        f'<span class="filter-chip" data-status="error"><span class="dot">✗</span>{counts["error"]}</span>'
        f'<span class="filter-chip" data-status="skipped"><span class="dot">−</span>{counts["skipped"]}</span>'
        f'</div>'
    )

    checks_html = _build_checks_html(grouped, plugins)

    # Assemble full HTML by concatenating parts.
    # _CSS and _JS are plain strings so their braces don't conflict with f-string.
    html = (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        "<title>DXC Doctor Report</title>\n"
        "<style>" + _CSS + "</style>\n"
        "</head>\n"
        "<body>\n"
        '<div class="header">\n'
        '<div class="header-row">\n'
        "<h1>DXC Doctor</h1>\n"
        f"{host_html}"
        f'<div class="stats">{stats_text}</div>\n'
        "</div>\n"
        '<div class="header-row">\n'
        f'<div class="cat-nav">{nav_links}</div>\n'
        f"{filter_chips}\n"
        '<input type="search" id="search-input" placeholder="Filter checks…">\n'
        '<button onclick="expandAll()">Expand All</button>\n'
        '<button onclick="collapseAll()">Collapse All</button>\n'
        '<span id="visible-count"></span>\n'
        "</div>\n"
        "</div>\n"
        '<div class="container">\n'
        f'<p style="color:#666;font-size:.78rem;margin-bottom:16px">Generated: {_esc(timestamp)}</p>\n'
        f"{checks_html}\n"
        "</div>\n"
        "<script>" + _JS + "</script>\n"
        "</body>\n"
        "</html>"
    )

    return html
