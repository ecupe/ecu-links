"""Small HTML pieces shared by build.py and instagram.py (standard library only)."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
ARROW = ('<svg class="link-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
         'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 17 17 7M7 7h10v10"/></svg>')
NEW_TAB = '<span class="sr-only" data-i18n="link.newTab">Opens in a new tab</span>'
EXTERNAL = 'target="_blank" rel="noopener noreferrer"'
PLAY = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>'
STACK = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
         'stroke-linejoin="round" aria-hidden="true"><rect x="8" y="8" width="12" height="12" rx="2.5"/>'
         '<path d="M16 8V6.5A2.5 2.5 0 0 0 13.5 4h-7A2.5 2.5 0 0 0 4 6.5v7A2.5 2.5 0 0 0 6.5 16H8"/></svg>')


def icon(name):
    """Inline a Simple Icons SVG so it can follow currentColor."""
    svg = (ROOT / "images" / "icons" / name).read_text(encoding="utf-8")
    svg = re.sub(r"<title>.*?</title>", "", svg)
    return svg.replace('role="img"', 'class="link-icon" aria-hidden="true" focusable="false" fill="currentColor"', 1)
