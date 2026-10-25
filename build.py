"""Build index.html from templates/index.html, site.json and locales/*.json (standard library only).

Also writes one small share page per song (s/<slug>/index.html, so links show that song's cover
when shared) and, when the optional `segno` package is installed, images/qr.svg for site_url.
"""
from html import escape
from pathlib import Path
import json
import re
import shutil
import sys
import unicodedata

ROOT = Path(__file__).resolve().parent
DEFAULT_LANGUAGE = "en"
LANGUAGE_ORDER = ["en", "es", "pt", "fr", "de", "it", "ar"]
GROUP_KINDS = {1: "streaming", 2: "socials", 3: "more"}
# Hover glow per platform (keyed by icon filename).
BRAND = {
    "spotify.svg": "#1ed760",
    "applemusic.svg": "#fa2d48",
    "instagram.svg": "#e1306c",
    "tiktok.svg": "#25f4ee",
    "youtube.svg": "#ff2a3d",
    "x.svg": "#e7e9ea",
    "github.svg": "#e7e9ea",
    "steam.svg": "#66c0f4",
    "discord.svg": "#5865f2",
}
ARROW = ('<svg class="link-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
         'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 17 17 7M7 7h10v10"/></svg>')
NEW_TAB = '<span class="sr-only" data-i18n="link.newTab">Opens in a new tab</span>'


def slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "song"


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
        f'data-goatcounter-click="release-{slugify(label)}" style="--accent:{track.get("accent", "#f5c84b")}">'
        f'<span class="release-art-wrap"><img class="release-art" src="{escape(track["cover"])}" alt="" width="180" height="180" loading="lazy">'
        f'<span class="release-vinyl" aria-hidden="true"></span></span>'
        f'<span class="release-copy"><span class="release-kicker" data-i18n="release.kicker">Latest release</span>'
        f'<span class="release-title">{escape(label)}</span>'
        f'<span class="release-cta">{icon(icon_name)}<span data-i18n="release.cta">Watch the lyric video</span>{ARROW}</span></span>'
        f'<span class="shine" aria-hidden="true"></span>{NEW_TAB}</a></section>'
    )


def link_group(group_index, title, links):
    links = [link for link in links if link[1]]  # a link without a URL stays hidden until it is filled in
    if not links:
        return ""
    kind = GROUP_KINDS.get(group_index, "more")
    tiles = "".join(
        f'<a class="link-button" href="{escape(url)}" target="_blank" rel="noopener noreferrer" data-magic '
        f'data-goatcounter-click="link-{slugify(label)}" style="--brand:{BRAND.get(icon_name, "#f5c84b")}">'
        f'<span class="link-glyph">{icon(icon_name)}</span><span class="link-label">{escape(label)}</span>{ARROW}'
        f'<span class="shine" aria-hidden="true"></span>{NEW_TAB}</a>'
        for label, url, icon_name in links
    )
    return (
        f'\n      <section class="link-section glass {kind}" data-reveal aria-labelledby="group-{group_index}">'
        f'<h2 id="group-{group_index}" class="section-heading" data-i18n="content.group.{group_index}">{escape(title)}</h2>'
        f'<div class="link-list">{tiles}</div></section>'
    )


def upcoming_card():
    """Countdown card for the next release; hidden until site.json enables it."""
    up = SITE.get("upcoming") or {}
    if not up.get("enabled"):
        return ""
    cover = up.get("cover") or "images/og-card.jpg"
    presave = up.get("presave", "")
    listen = up.get("listen") or presave
    unit = lambda key, label: (f'<span class="count-unit"><b data-unit="{key}">00</b>'
                               f'<small data-i18n="upcoming.{key}">{label}</small></span>')
    action = lambda cls, url, key, text, click: (
        f'<a class="upcoming-action {cls}" href="{escape(url)}" target="_blank" rel="noopener noreferrer" '
        f'data-goatcounter-click="{click}"><span data-i18n="{key}">{text}</span>{ARROW}{NEW_TAB}</a>' if url else "")
    return (
        f'\n      <section class="link-section glass upcoming" data-reveal data-release="{escape(up["release"])}" aria-labelledby="upcoming-title">'
        f'<div class="upcoming-art"><img src="{escape(cover)}" alt="" width="160" height="160" loading="lazy"></div>'
        f'<div class="upcoming-copy"><p class="upcoming-kicker"><span class="pulse" aria-hidden="true"></span>'
        f'<span data-i18n="upcoming.kicker" data-when="before">Coming soon</span>'
        f'<span data-i18n="upcoming.out" data-when="after">Out now</span></p>'
        f'<h2 id="upcoming-title" class="upcoming-title">{escape(up.get("title", ""))}</h2>'
        f'<div class="countdown" data-when="before" role="timer" aria-live="off">'
        f'{unit("days", "days")}{unit("hours", "hours")}{unit("minutes", "min")}{unit("seconds", "sec")}</div>'
        f'<div class="upcoming-actions">{action("presave", presave, "upcoming.presave", "Pre-save", "presave")}'
        f'{action("listen", listen, "upcoming.listen", "Listen now", "upcoming-listen")}</div></div></section>'
    )


def contact_section():
    form_id = (SITE.get("contact") or {}).get("formspree", "").strip()
    if not form_id:
        return ""
    field = lambda name, key, label, tag: (
        f'<label class="field"><span data-i18n="{key}">{label}</span>'
        + (f'<textarea name="{name}" rows="4" required maxlength="2000"></textarea>' if tag == "textarea" else
           f'<input name="{name}" type="{"email" if name == "email" else "text"}" required maxlength="120" '
           f'autocomplete="{"email" if name == "email" else "name"}">')
        + '</label>')
    return (
        '\n      <section class="link-section glass contact" data-reveal aria-labelledby="contact-heading">'
        '<h2 id="contact-heading" class="section-heading" data-i18n="contact.heading">Contact &amp; booking</h2>'
        '<p class="contact-intro" data-i18n="contact.intro">Collabs, shows, or just to say hi. I read everything.</p>'
        f'<form id="contact-form" class="contact-form" action="https://formspree.io/f/{escape(form_id)}" method="POST">'
        f'{field("name", "contact.name", "Name", "input")}{field("email", "contact.email", "Email", "input")}'
        f'{field("message", "contact.message", "Message", "textarea")}'
        '<input type="text" name="_gotcha" class="sr-only" tabindex="-1" autocomplete="off" aria-hidden="true">'
        '<div class="contact-row"><button class="cta cta-small" type="submit" data-goatcounter-click="contact-send">'
        '<span data-i18n="contact.send">Send message</span></button>'
        '<p id="contact-status" class="contact-status" role="status" aria-live="polite"></p></div></form></section>'
    )


def analytics_tag():
    code = (SITE.get("analytics") or {}).get("goatcounter", "").strip()
    if not code:
        return ""
    return (f'<script data-goatcounter="https://{escape(code)}.goatcounter.com/count" '
            'async src="https://gc.zgo.at/count.js"></script>')


def share_pages(tracks, base):
    """One tiny page per song so chat apps preview that song's cover; it forwards to the player."""
    out = ROOT / "s"
    slugs = {track["slug"] for track in tracks}
    if out.exists():
        # Rewrite in place (OneDrive can briefly lock folders); drop pages of removed songs.
        for old in out.iterdir():
            if old.is_dir() and old.name not in slugs:
                shutil.rmtree(old, ignore_errors=True)
    for track in tracks:
        page = out / track["slug"]
        page.mkdir(parents=True, exist_ok=True)
        title = escape(f'{track["title"]} · {SITE["name"]}')
        target = f'../../?song={track["slug"]}'
        page.joinpath("index.html").write_text(
            '<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{title}</title><meta property="og:title" content="{title}">'
            f'<meta property="og:description" content="{escape(SITE["name"])} — listen now">'
            f'<meta property="og:image" content="{escape(base + track["cover"])}">'
            f'<meta property="og:url" content="{escape(base + "s/" + track["slug"] + "/")}">'
            '<meta name="twitter:card" content="summary_large_image">'
            f'<meta http-equiv="refresh" content="0; url={target}">'
            f'<link rel="canonical" href="{escape(base + "?song=" + track["slug"])}"></head>'
            f'<body style="background:#05060a;color:#fff;font-family:system-ui"><a href="{target}">{title}</a></body></html>\n',
            encoding="utf-8", newline="\n")


def qr_code(url):
    try:
        import segno
    except ImportError:
        if not (ROOT / "images" / "qr.svg").exists():
            print("note: install segno (py -m pip install segno) to generate images/qr.svg")
        return
    segno.make(url, error="m").save(str(ROOT / "images" / "qr.svg"), scale=10, border=2,
                                    dark="#07080d", light="#ffffff", xmldecl=False, svgns=True)


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
        if f"content.group.{index}" not in reference:
            sys.exit(f"Add content.group.{index} to every locales/*.json for the group '{title}'")
        reference[f"content.group.{index}"] = title
    return locales


def script_json(value):
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


SITE = json.loads((ROOT / "site.json").read_text(encoding="utf-8"))


def main():
    locales = load_locales()
    base = SITE.get("site_url", "").rstrip("/") + "/"
    order = [c for c in LANGUAGE_ORDER if c in locales] + sorted(set(locales) - set(LANGUAGE_ORDER))
    sections = upcoming_card() + "".join(
        release_card(i, title, links) if i == 0 else link_group(i, title, links)
        for i, (title, links) in enumerate(SITE["groups"])
    )
    tracks = [{**t, "artist": t.get("artist", SITE["name"]), "slug": slugify(t["title"])} for t in SITE["tracks"]]
    for track in tracks:
        track["share"] = base + "s/" + track["slug"] + "/"
    page = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    replacements = {
        "__SECTIONS__": sections,
        "__CONTACT__": contact_section(),
        "__ANALYTICS__": analytics_tag(),
        "__LANGUAGE_OPTIONS__": "".join(
            f'<option value="{c}" lang="{c}">{escape(locales[c]["name"])}</option>' for c in order),
        "__TRACK_DATA__": script_json({"name": SITE["name"], "site": base, "tracks": tracks}),
        "__I18N_DATA__": script_json({"name": SITE["name"], "defaultLanguage": DEFAULT_LANGUAGE,
                                      "locales": {c: locales[c] for c in order}}),
        "__FIRST_COVER__": escape(tracks[0]["cover"]) if tracks else "",
        "__FIRST_TITLE__": escape(tracks[0]["title"]) if tracks else "",
        "__DESCRIPTION__": escape(locales[DEFAULT_LANGUAGE]["messages"]["meta.description"].replace("{name}", SITE["name"])),
        "__TAGLINE__": escape(SITE["tagline"]),
        "__SITE_URL__": escape(base),
        "__NAME__": escape(SITE["name"]),
    }
    for token, value in replacements.items():
        page = page.replace(token, value)
    leftover = re.findall(r"__[A-Z_]+__", page)
    if leftover:
        sys.exit(f"Unreplaced placeholders: {leftover}")
    (ROOT / "index.html").write_text(page, encoding="utf-8", newline="\n")
    share_pages(tracks, base)
    qr_code(base)
    print(f"index.html built: {len(SITE['groups'])} link groups, {len(tracks)} tracks, {len(order)} languages,"
          f" countdown {'on' if (SITE.get('upcoming') or {}).get('enabled') else 'off'},"
          f" analytics {'on' if analytics_tag() else 'off'}, contact {'on' if contact_section() else 'off'}")


if __name__ == "__main__":
    main()
