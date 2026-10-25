"""Build index.html from templates/index.html, site.json and locales/*.json (standard library only)."""
from html import escape
from pathlib import Path
import json
import re
import sys

ROOT = Path(__file__).resolve().parent
DEFAULT_LANGUAGE = "en"
LANGUAGE_ORDER = ["en", "es", "pt", "fr", "de", "it", "ar"]
# Hover glow per platform (keyed by icon filename).
BRAND = {
    "spotify.svg": "#1ed760",
    "applemusic.svg": "#fa2d48",
    "instagram.svg": "#e1306c",
    "tiktok.svg": "#25f4ee",
    "youtube.svg": "#ff2a3d",
    "x.svg": "#e7e9ea",
}
ARROW = ('<svg class="link-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
         'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 17 17 7M7 7h10v10"/></svg>')
NEW_TAB = '<span class="sr-only" data-i18n="link.newTab">Opens in a new tab</span>'


def icon(name):
    """Inline a Simple Icons SVG so it can follow currentColor."""
    svg = (ROOT / "images" / "icons" / name).read_text(encoding="utf-8")
    svg = re.sub(r"<title>.*?</title>", "", svg)
    return svg.replace('role="img"', 'class="link-icon" aria-hidden="true" focusable="false" fill="currentColor"', 1)


def release_card(group_index, title, links):
    label, url, icon_name = links[0]
    track = next((t for t in SITE["tracks"] if t["title"] == label), SITE["tracks"][0])
    return (
        f'\n      <section class="link-section glass featured" data-reveal aria-labelledby="group-{group_index}">'
        f'<h2 id="group-{group_index}" class="section-heading" data-i18n="content.group.{group_index}">{escape(title)}</h2>'
        f'<a class="release-link" href="{escape(url)}" target="_blank" rel="noopener noreferrer" data-tilt '
        f'style="--accent:{track.get("accent", "#f5c84b")}">'
        f'<span class="release-art-wrap"><img class="release-art" src="{escape(track["cover"])}" alt="" width="180" height="180" loading="lazy">'
        f'<span class="release-vinyl" aria-hidden="true"></span></span>'
        f'<span class="release-copy"><span class="release-kicker" data-i18n="release.kicker">Latest release</span>'
        f'<span class="release-title">{escape(label)}</span>'
        f'<span class="release-cta">{icon(icon_name)}<span data-i18n="release.cta">Watch the lyric video</span>{ARROW}</span></span>'
        f'<span class="shine" aria-hidden="true"></span>{NEW_TAB}</a></section>'
    )


def link_group(group_index, title, links):
    kind = "streaming" if group_index == 1 else "socials"
    tiles = "".join(
        f'<a class="link-button" href="{escape(url)}" target="_blank" rel="noopener noreferrer" data-magic '
        f'style="--brand:{BRAND.get(icon_name, "#f5c84b")}">'
        f'<span class="link-glyph">{icon(icon_name)}</span><span class="link-label">{escape(label)}</span>{ARROW}'
        f'<span class="shine" aria-hidden="true"></span>{NEW_TAB}</a>'
        for label, url, icon_name in links
    )
    return (
        f'\n      <section class="link-section glass {kind}" data-reveal aria-labelledby="group-{group_index}">'
        f'<h2 id="group-{group_index}" class="section-heading" data-i18n="content.group.{group_index}">{escape(title)}</h2>'
        f'<div class="link-list">{tiles}</div></section>'
    )


def load_locales():
    locales = {}
    for path in sorted((ROOT / "locales").glob("*.json")):
        locales[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    reference = locales[DEFAULT_LANGUAGE]["messages"]
    for code, locale in locales.items():
        missing = set(reference) ^ set(locale["messages"])
        if missing:
            sys.exit(f"locales/{code}.json keys differ from en.json: {sorted(missing)}")
        for key, text in reference.items():
            if set(re.findall(r"\{\w+\}", text)) != set(re.findall(r"\{\w+\}", locale["messages"][key])):
                sys.exit(f"locales/{code}.json: placeholders differ in {key}")
    # English wording in site.json wins, so the page and its catalog never disagree.
    reference["content.tagline"] = SITE["tagline"]
    for index, (title, _links) in enumerate(SITE["groups"]):
        reference[f"content.group.{index}"] = title
    return locales


def script_json(value):
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


SITE = json.loads((ROOT / "site.json").read_text(encoding="utf-8"))


def main():
    locales = load_locales()
    order = [c for c in LANGUAGE_ORDER if c in locales] + sorted(set(locales) - set(LANGUAGE_ORDER))
    sections = "".join(
        release_card(i, title, links) if i == 0 else link_group(i, title, links)
        for i, (title, links) in enumerate(SITE["groups"])
    )
    tracks = [{**t, "artist": t.get("artist", SITE["name"])} for t in SITE["tracks"]]
    page = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    replacements = {
        "__SECTIONS__": sections,
        "__LANGUAGE_OPTIONS__": "".join(
            f'<option value="{c}" lang="{c}">{escape(locales[c]["name"])}</option>' for c in order),
        "__TRACK_DATA__": script_json({"name": SITE["name"], "tracks": tracks}),
        "__I18N_DATA__": script_json({"name": SITE["name"], "defaultLanguage": DEFAULT_LANGUAGE,
                                      "locales": {c: locales[c] for c in order}}),
        "__FIRST_COVER__": escape(tracks[0]["cover"]) if tracks else "",
        "__FIRST_TITLE__": escape(tracks[0]["title"]) if tracks else "",
        "__DESCRIPTION__": escape(locales[DEFAULT_LANGUAGE]["messages"]["meta.description"].replace("{name}", SITE["name"])),
        "__TAGLINE__": escape(SITE["tagline"]),
        "__NAME__": escape(SITE["name"]),
    }
    for token, value in replacements.items():
        page = page.replace(token, value)
    leftover = re.findall(r"__[A-Z_]+__", page)
    if leftover:
        sys.exit(f"Unreplaced placeholders: {leftover}")
    (ROOT / "index.html").write_text(page, encoding="utf-8", newline="\n")
    print(f"index.html built: {len(SITE['groups'])} link groups, {len(tracks)} tracks, {len(order)} languages")


if __name__ == "__main__":
    main()
