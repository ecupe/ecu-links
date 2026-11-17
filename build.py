"""Build the whole static site (standard library only).

Reads site.json (personal site), studio.json (MECU Interactive) and locales/*.json, and writes:

- index.html                               the personal home page (templates/index.html)
- projects/<slug>/index.html               one page per project that has a "page" block
- mecu-interactive/index.html              the studio home
- mecu-interactive/games/<slug>/index.html one page per game
- s/<slug>/index.html                      a small share page per song
- sitemap.xml, and images/qr.svg when the optional `segno` package is installed

Sub-pages share templates/page.html. Every page gets only the translations it uses.
"""
from datetime import date
from html import escape
from pathlib import Path
import json
import re
import shutil
import sys
import unicodedata

from ui import ARROW, EXTERNAL, NEW_TAB, PLAY, icon
import instagram

ROOT = Path(__file__).resolve().parent
DEFAULT_LANGUAGE = "en"
LANGUAGE_ORDER = ["en", "es", "pt", "fr", "de", "it", "ar"]
GROUP_KINDS = {1: "streaming", 2: "socials", 3: "more"}
# Hover colour per platform (keyed by icon filename).
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
ECU_MARK = ('<svg class="brand-mark" viewBox="0 0 64 64" aria-hidden="true">'
            '<rect class="blade blade-spine" x="10" y="8" width="9" height="48" rx="4.5"/>'
            '<rect class="blade blade-1" x="10" y="8" width="44" height="10" rx="5"/>'
            '<rect class="blade blade-2" x="10" y="27" width="34" height="10" rx="5"/>'
            '<rect class="blade blade-3" x="10" y="46" width="44" height="10" rx="5"/></svg>')

# Translations each kind of page needs (prefix match), so no page ships the whole catalog.
SHARED_KEYS = ("language.", "theme.", "nav.label", "nav.menu", "nav.close", "nav.home", "link.newTab",
               "share.copied", "hero.scroll", "footer.top", "app.install")
HOME_SKIP = ("studio.", "page.")
VIEWER_KEYS = ("stories.", "media.")  # only where a story viewer is on the page
STUDIO_KEYS = SHARED_KEYS + ("studio.", "stories.", "media.", "ig.")
PROJECT_KEYS = SHARED_KEYS + ("page.", "project.", "projects.", "site.footer", "nav.projects")

SITE = json.loads((ROOT / "site.json").read_text(encoding="utf-8-sig"))
STUDIO = json.loads((ROOT / "studio.json").read_text(encoding="utf-8-sig"))
YEAR = str(date.today().year)
# Instagram accounts (data/instagram/<handle>.json), checked once when the build starts.
SITE_IG = instagram.load(SITE["instagram"]) if SITE.get("instagram") else None
STUDIO_IG = instagram.load(STUDIO["instagram"])


def slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "song"


def script_json(value):
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def words(text):
    """Wrap each word so the big titles can break and animate per word."""
    return " ".join(f'<span class="word">{escape(word)}</span>' for word in text.split())


def block_head(number, heading_id, key, text, note_key="", note=""):
    note_html = f'<p class="block-note" data-i18n="{note_key}">{escape(note)}</p>' if note_key else ""
    return (f'<div class="block-head" data-reveal><span class="block-no" aria-hidden="true">{number:02d}</span>'
            f'<h2 id="{heading_id}" class="block-title" data-i18n="{key}">{escape(text)}</h2>{note_html}</div>')


def status_pill(prefix, status, messages):
    key = f"{prefix}.{status}"
    if key not in messages:
        sys.exit(f"Unknown status '{status}': add {key} to every locales/*.json")
    return (f'<span class="status" data-status="{escape(status)}"><i aria-hidden="true"></i>'
            f'<span data-i18n="{key}">{escape(messages[key])}</span></span>')


# ───────── Personal home page ─────────

def release_card(group_index, title, links):
    label, url, icon_name = links[0]
    track = next((t for t in SITE["tracks"] if t["title"] == label), SITE["tracks"][0])
    return (
        f'<div class="release featured" data-reveal><h3 id="group-{group_index}" class="sr-only" '
        f'data-i18n="content.group.{group_index}">{escape(title)}</h3>'
        f'<a class="release-link" href="{escape(url)}" {EXTERNAL} '
        f'data-goatcounter-click="release-{slugify(label)}" style="--accent:{track.get("accent", "#f5c84b")}">'
        f'<span class="release-art-wrap" data-tilt><img class="release-art" src="{escape(track["cover"])}" alt="" '
        f'width="640" height="640" loading="lazy"><span class="release-vinyl" aria-hidden="true"></span></span>'
        f'<span class="release-copy"><span class="release-kicker" data-i18n="release.kicker">Latest release</span>'
        f'<span class="release-title">{escape(label)}</span>'
        f'<span class="release-cta btn">{icon(icon_name)}<span data-i18n="release.cta">Watch the lyric video</span>{ARROW}</span></span>'
        f'{NEW_TAB}</a></div>'
    )


def link_group(group_index, title, links, reveal=True):
    links = [link for link in links if link[1]]  # a link without a URL stays hidden until it is filled in
    if not links:
        return ""
    kind = GROUP_KINDS.get(group_index, "more")
    tiles = "".join(
        f'<a class="link-button" href="{escape(url)}" {EXTERNAL} data-magic '
        f'data-goatcounter-click="link-{slugify(label)}" style="--brand:{BRAND.get(icon_name, "#f5c84b")}">'
        f'<span class="link-glyph">{icon(icon_name)}</span><span class="link-label">{escape(label)}</span>{ARROW}{NEW_TAB}</a>'
        for label, url, icon_name in links
    )
    return (
        f'<div class="link-group {kind}"{" data-reveal" if reveal else ""}>'
        f'<h3 id="group-{group_index}" class="label" data-i18n="content.group.{group_index}">{escape(title)}</h3>'
        f'<div class="link-list">{tiles}</div></div>'
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
        f'<a class="upcoming-action {cls}" href="{escape(url)}" {EXTERNAL} '
        f'data-goatcounter-click="{click}"><span data-i18n="{key}">{text}</span>{ARROW}{NEW_TAB}</a>' if url else "")
    return (
        f'<div class="upcoming" data-reveal data-release="{escape(up["release"])}" role="group" aria-labelledby="upcoming-title">'
        f'<div class="upcoming-art"><img src="{escape(cover)}" alt="" width="160" height="160" loading="lazy"></div>'
        f'<div class="upcoming-copy"><p class="upcoming-kicker"><span class="pulse" aria-hidden="true"></span>'
        f'<span data-i18n="upcoming.kicker" data-when="before">Coming soon</span>'
        f'<span data-i18n="upcoming.out" data-when="after">Out now</span></p>'
        f'<h3 id="upcoming-title" class="upcoming-title">{escape(up.get("title", ""))}</h3>'
        f'<div class="countdown" data-when="before" role="timer" aria-live="off">'
        f'{unit("days", "days")}{unit("hours", "hours")}{unit("minutes", "min")}{unit("seconds", "sec")}</div>'
        f'<div class="upcoming-actions">{action("presave", presave, "upcoming.presave", "Pre-save", "presave")}'
        f'{action("listen", listen, "upcoming.listen", "Listen now", "upcoming-listen")}</div></div></div>'
    )


def music_section(number, m, groups):
    return (
        '\n      <section id="music" class="block music" aria-labelledby="music-title">'
        + block_head(number, "music-title", "nav.music", m["nav.music"], "music.note", m["music.note"])
        + upcoming_card() + groups.get(0, "") + groups.get(1, "")
        + '<div class="discography" data-reveal><h3 id="discography-heading" class="label" data-i18n="music.heading">'
        f'{escape(m["music.heading"])}</h3><div id="discography" class="track-grid"></div></div></section>'
    )


def instagram_feed(account, m, root, label_tag):
    """InstagramHighlights + InstagramGallery for one account, each under a small label."""
    rail = instagram.highlights(account, root, m)
    label = lambda key: f'<{label_tag} class="label" data-i18n="{key}">{escape(m[key])}</{label_tag}>'
    return (
        (f'<div class="hl-wrap" data-reveal>{label("ig.highlights")}{rail}</div>' if rail else "")
        + f'<div class="ig-wrap" data-reveal>{label("ig.posts")}{instagram.gallery(account, root, m)}</div>'
    )


def about_instagram(m):
    """The Instagram part of About; nothing when the account has no visible content."""
    account = SITE_IG
    if not account or not (account["posts"] or account["highlights"]):
        return ""
    return (
        '<div id="instagram" class="ig"><div class="ig-head" data-reveal>'
        f'<h3 class="ig-title">Instagram</h3><div class="ig-meta"><a class="ig-profile" href="{escape(account["url"])}" {EXTERNAL} '
        f'data-goatcounter-click="ig-handle">@{escape(account["handle"])}{ARROW}{NEW_TAB}</a>'
        f'<p class="ig-intro" data-i18n="about.ig.intro">{escape(m["about.ig.intro"])}</p></div>'
        f'{instagram.follow_button(account, m)}</div>{instagram_feed(account, m, "", "h4")}</div>'
    )


def about_section(number, m, socials):
    identity = "".join(
        f'<li data-reveal><span class="identity-no" aria-hidden="true">{i + 1:02d}</span>'
        f'<h3 class="identity-title" data-i18n="about.role.{i}">{escape(m[f"about.role.{i}"])}</h3>'
        f'<p data-i18n="about.role.{i}.body">{escape(m[f"about.role.{i}.body"])}</p></li>' for i in range(3))
    return (
        '\n      <section id="about" class="block about" aria-labelledby="about-heading">'
        + block_head(number, "about-heading", "about.heading", m["about.heading"])
        + '<div class="about-grid"><div class="about-photo" data-reveal><picture>'
        '<source srcset="images/profile-320.webp 1x, images/profile-640.webp 2x" type="image/webp">'
        '<img src="images/profile-320.jpg" srcset="images/profile-320.jpg 1x, images/profile-640.jpg 2x" alt="" '
        'width="320" height="320" loading="lazy"></picture><span class="about-badge" aria-hidden="true">ECU</span></div>'
        f'<div class="about-copy"><p class="about-lead" data-reveal data-i18n="about.lead">'
        f'{escape(m["about.lead"].replace("{name}", SITE["name"]))}</p>'
        f'<p class="about-body" data-reveal data-i18n="about.body">{escape(m["about.body"])}</p></div></div>'
        f'<div class="identity-wrap"><p class="label" data-reveal data-i18n="about.identity">{escape(m["about.identity"])}</p>'
        f'<ol class="identity">{identity}</ol></div>{about_instagram(m)}{socials}</section>'
    )


def project_slug(project):
    return (project.get("page") or {}).get("slug", "")


def project_link(project):
    """Where a project leads, and whether that leaves the site."""
    slug = project_slug(project)
    href = f"projects/{slug}/" if slug else project["url"]
    return href, bool(not slug and re.match(r"https?://", project["url"]))


def featured_project(p, m):
    """A project with "featured": true gets a full panel instead of a row."""
    key = f'project.{p["key"]}'
    href, external = project_link(p)
    cta = p.get("cta", "projects.visit")
    if cta not in m:
        sys.exit(f"Add {cta} to every locales/*.json for the project '{p['name']}'")
    if p.get("mark") == "mecu":
        art = '<span class="teaser-mark mecu-mark" aria-hidden="true"></span>'
    elif p.get("image"):
        art = f'<span class="teaser-art"><img src="{escape(p["image"])}" alt="" width="1200" height="750" loading="lazy"></span>'
    else:
        art = ""
    kicker = " · ".join(escape(part) for part in [*p.get("tags", []), p.get("year", "")] if part)
    return (
        f'<div class="teaser{"" if art else " teaser-plain"}" data-reveal><a class="teaser-link" href="{escape(href)}" '
        f'{EXTERNAL + " " if external else ""}data-goatcounter-click="project-{slugify(p["name"])}">{art}'
        f'<span class="teaser-copy"><span class="teaser-top"><span class="teaser-kicker">{kicker}</span>'
        f'{status_pill("projects.status", p.get("status", "live"), m)}</span>'
        f'<span class="teaser-title" role="heading" aria-level="3">{escape(p["name"])}</span>'
        f'<span class="teaser-body" data-i18n="{key}">{escape(m[key])}</span>'
        f'<span class="btn btn-invert"><span data-i18n="{cta}">{escape(m[cta])}</span>{ARROW}</span></span>'
        f'{NEW_TAB if external else ""}</a></div>'
    )


def projects_section(number, m):
    projects = SITE.get("projects") or []
    if not projects:
        return ""
    panels, rows = "", ""
    for p in projects:
        key = f'project.{p["key"]}'
        if key not in m:
            sys.exit(f"Add {key} to every locales/*.json for the project '{p['name']}'")
        if p.get("featured"):
            panels += featured_project(p, m)
            continue
        href, external = project_link(p)
        tags = "".join(f"<li>{escape(t)}</li>" for t in p.get("tags", []))
        image = p.get("image", "")
        thumb = (f'<span class="project-thumb"><img src="{escape(image)}" alt="" width="1200" height="750" loading="lazy"></span>'
                 if image else "")
        year = f'<span class="project-year">{escape(p["year"])}</span>' if p.get("year") else ""
        index = rows.count('class="project-row"') + 1
        rows += (
            f'<a class="project-row" href="{escape(href)}" {EXTERNAL + " " if external else ""}'
            f'{"data-preview=" + chr(34) + escape(image) + chr(34) + " " if image else ""}'
            f'data-goatcounter-click="project-{slugify(p["name"])}">'
            f'<span class="project-no" aria-hidden="true">{index:02d}</span>'
            f'<span class="project-main"><span class="project-name">{escape(p["name"])}</span>'
            f'<span class="project-desc" data-i18n="{key}">{escape(m[key])}</span></span>{thumb}'
            f'<span class="project-meta"><ul class="project-tags">{tags}</ul>'
            f'{status_pill("projects.status", p.get("status", "live"), m)}{year}</span>'
            f'{ARROW}{NEW_TAB if external else ""}</a>'
        )
    return (
        '\n      <section id="projects" class="block projects" aria-labelledby="projects-heading">'
        + block_head(number, "projects-heading", "projects.heading", m["projects.heading"],
                     "projects.intro", m["projects.intro"])
        + (f'<div class="feature-list">{panels}</div>' if panels else "")
        + (f'<div class="project-list" data-reveal>{rows}</div>'
           '<div class="project-preview" aria-hidden="true"><img alt=""></div>' if rows else "")
        + '</section>'
    )


def contact_form():
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
        f'<form id="contact-form" class="contact-form" data-reveal action="https://formspree.io/f/{escape(form_id)}" method="POST">'
        f'{field("name", "contact.name", "Name", "input")}{field("email", "contact.email", "Email", "input")}'
        f'{field("message", "contact.message", "Message", "textarea")}'
        '<input type="text" name="_gotcha" class="sr-only" tabindex="-1" autocomplete="off" aria-hidden="true">'
        '<div class="contact-row"><button class="cta cta-small" type="submit" data-goatcounter-click="contact-send">'
        '<span data-i18n="contact.send">Send message</span></button>'
        '<p id="contact-status" class="contact-status" role="status" aria-live="polite"></p></div></form>'
    )


def contact_section(number, m, more):
    form = contact_form()
    if not form and not more:
        return ""
    if not form:
        return ('\n      <section class="block elsewhere" aria-labelledby="group-3">' + more + '</section>')
    return (
        '\n      <section id="contact" class="block contact" aria-labelledby="contact-heading">'
        + block_head(number, "contact-heading", "contact.heading", m["contact.heading"])
        + '<div class="contact-grid"><div class="contact-side">'
        f'<p class="contact-title" data-reveal data-i18n="contact.title">{escape(m["contact.title"])}</p>'
        f'<p class="contact-intro" data-reveal data-i18n="contact.intro">{escape(m["contact.intro"])}</p>{more}</div>'
        f'{form}</div></section>'
    )


def home_nav(m, has_projects, has_contact):
    items = [("top", "nav.home"), ("music", "nav.music"), ("about", "nav.about")]
    if has_projects:
        items.append(("projects", "nav.projects"))
    if has_contact:
        items.append(("contact", "nav.contact"))
    links = "".join(f'<a class="nav-link" href="#{target}" data-i18n="{key}">{escape(m[key])}</a>' for target, key in items)
    return links + (f'<a class="nav-link nav-out nav-pill" href="{STUDIO["path"]}/" data-goatcounter-click="nav-studio">'
                    f'<span data-i18n="nav.studio">{escape(m["nav.studio"])}</span>{ARROW}</a>')


def marquee(items):
    """A band of repeating words. `items` are (i18n key or "", text)."""
    run = "".join(
        (f'<span data-i18n="{key}">{escape(text)}</span>' if key else f'<span>{escape(text)}</span>') + '<i></i>'
        for key, text in items)
    return f'<div class="marquee" aria-hidden="true"><div class="marquee-track">{run * 4}</div></div>'


def analytics_tag():
    code = (SITE.get("analytics") or {}).get("goatcounter", "").strip()
    if not code:
        return ""
    return (f'<script data-goatcounter="https://{escape(code)}.goatcounter.com/count" '
            'async src="https://gc.zgo.at/count.js"></script>')


# ───────── Shared page shell (templates/page.html) ─────────

def language_options(locales, order):
    return "".join(f'<option value="{c}" lang="{c}">{escape(locales[c]["name"])}</option>' for c in order)


def i18n_block(locales, order, keep=None, skip=()):
    """The catalogs for one page, trimmed to the keys it uses."""
    def wanted(key):
        return key.startswith(keep) if keep else not key.startswith(skip)
    trimmed = {c: {**locales[c], "messages": {k: v for k, v in locales[c]["messages"].items() if wanted(k)}}
               for c in order}
    return script_json({"name": SITE["name"], "defaultLanguage": DEFAULT_LANGUAGE, "locales": trimmed})


def fill(template, replacements, target):
    page = (ROOT / "templates" / template).read_text(encoding="utf-8")
    for token, value in replacements.items():
        page = page.replace(token, value)
    leftover = re.findall(r"__[A-Z][A-Z_]+__", page)
    if leftover:
        sys.exit(f"{target}: unreplaced placeholders {sorted(set(leftover))}")
    path = ROOT / target
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8", newline="\n")


def subpage(target, *, brand, title, description, nav, main, footer, i18n, locales, order,
            title_key="", description_key="", og_image="images/og-card.jpg", extra_css=(), extra_js=(), data=""):
    """Write one sub-page. `target` is its folder ("mecu-interactive", "projects/ecu-links", ...)."""
    depth = target.strip("/").count("/") + 1
    root = "../" * depth
    base = SITE.get("site_url", "").rstrip("/") + "/"
    home = root if brand == "ecu" else root + STUDIO["path"] + "/"
    if brand == "mecu":
        brand_link = (f'<a class="brand brand-mecu" href="{home}" aria-label="{escape(STUDIO["name"])}">'
                      f'<span class="mecu-mark" aria-hidden="true"></span><span class="brand-word">{escape(STUDIO["name"])}</span></a>')
        icons = (f'<link rel="icon" href="{root}images/mecu/icon-192.png" type="image/png">'
                 f'<link rel="apple-touch-icon" href="{root}images/mecu/icon-192.png">')
    else:
        brand_link = (f'<a class="brand" href="{home}" aria-label="{escape(SITE["name"])}">{ECU_MARK}'
                      '<span class="brand-word">ECU</span></a>')
        icons = (f'<link rel="icon" href="{root}images/favicon.svg" type="image/svg+xml">'
                 f'<link rel="apple-touch-icon" href="{root}images/apple-touch-icon.png">')
    styles = "".join(f'<link rel="stylesheet" href="{root}assets/css/{name}">' for name in ("site.css", *extra_css))
    scripts = "".join(f'<script src="{root}assets/js/{name}" defer></script>'
                      for name in ("i18n.js", "motion.js", "features.js", "nav.js", *extra_js))
    fill("page.html", {
        "__MAIN__": main,
        "__FOOTER__": footer,
        "__NAV__": nav,
        "__BRAND_LINK__": brand_link,
        "__DATA__": data,
        "__I18N_DATA__": i18n,
        "__TRACK_DATA__": script_json({"name": SITE["name"], "site": base, "tracks": []}),
        "__LANGUAGE_OPTIONS__": language_options(locales, order),
        "__ANALYTICS__": analytics_tag(),
        "__STYLES__": styles,
        "__SCRIPTS__": scripts,
        "__ICONS__": icons,
        "__TITLE_ATTR__": f' data-i18n="{title_key}"' if title_key else "",
        "__DESCRIPTION_ATTR__": f' data-i18n-content="{description_key}"' if description_key else "",
        "__TITLE__": escape(title),
        "__DESCRIPTION__": escape(description),
        "__OG_IMAGE__": escape(base + og_image),
        "__CANONICAL__": escape(base + target.strip("/") + "/"),
        "__THEME_COLOR__": "#000000" if brand == "mecu" else "#0a0a0b",
        "__BRAND__": brand,
        "__ROOT__": root,
        "__NAME__": escape(SITE["name"]),
    }, f"{target.strip('/')}/index.html")
    return base + target.strip("/") + "/"


# ───────── Project pages ─────────

def project_page(project, locales, order):
    m = locales[DEFAULT_LANGUAGE]["messages"]
    page = project["page"]
    key = f'project.{project["key"]}'
    features = "".join(f'<li data-reveal data-i18n="{key}.f{i}">{escape(m[f"{key}.f{i}"])}</li>'
                       for i in range(page.get("features", 0)))
    stack = "".join(f"<li>{escape(item)}</li>" for item in page.get("stack", []))
    facts = (
        f'<div><dt data-i18n="page.role">{escape(m["page.role"])}</dt>'
        f'<dd data-i18n="{key}.role">{escape(m[f"{key}.role"])}</dd></div>'
        f'<div><dt data-i18n="page.status">{escape(m["page.status"])}</dt>'
        f'<dd>{status_pill("projects.status", project.get("status", "live"), m)}</dd></div>'
        + (f'<div><dt data-i18n="page.year">{escape(m["page.year"])}</dt><dd>{escape(project["year"])}</dd></div>'
           if project.get("year") else "")
        + (f'<div><dt data-i18n="page.stack">{escape(m["page.stack"])}</dt><dd><ul class="project-tags">{stack}</ul></dd></div>'
           if stack else "")
    )
    actions = ""
    if page.get("site"):
        actions += (f'<a class="btn" href="{escape(page["site"])}"><span data-i18n="projects.visit">'
                    f'{escape(m["projects.visit"])}</span>{ARROW}</a>')
    if project.get("url"):
        actions += (f'<a class="btn btn-ghost" href="{escape(project["url"])}" {EXTERNAL}><span data-i18n="projects.source">'
                    f'{escape(m["projects.source"])}</span>{ARROW}{NEW_TAB}</a>')
    image = project.get("image", "")
    figure = (f'<figure class="page-figure" data-reveal><img src="../../{escape(image)}" alt="" width="1200" height="750"></figure>'
              if image else "")
    main = (
        '<header class="page-hero">'
        f'<a class="back-link" data-reveal href="../../#projects">{ARROW}<span data-i18n="page.back">{escape(m["page.back"])}</span></a>'
        f'<h1 class="page-title" data-split>{words(project["name"])}</h1>'
        f'<p class="page-summary" data-reveal data-i18n="{key}.summary">{escape(m[f"{key}.summary"])}</p>'
        f'<div class="page-actions" data-reveal>{actions}</div></header>'
        f'{figure}<section class="block page-body"><dl class="facts" data-reveal>{facts}</dl>'
        f'<div class="page-features"><h2 class="label" data-reveal data-i18n="page.features">{escape(m["page.features"])}</h2>'
        f'<ol class="feature-list">{features}</ol></div></section>'
    )
    nav = (f'<a class="nav-link nav-out" href="../../" data-i18n="nav.home">{escape(m["nav.home"])}</a>'
           f'<a class="nav-link nav-out" href="../../#projects" data-i18n="nav.projects">{escape(m["nav.projects"])}</a>')
    footer = (f'<div class="footer-row"><span class="flag-stripe" aria-hidden="true"><i></i><i></i><i></i></span>'
              f'<p class="site-footer" data-i18n="site.footer">{escape(m["site.footer"].replace("{name}", SITE["name"]))}</p></div>')
    return subpage(
        f'projects/{page["slug"]}', brand="ecu", title=f'{project["name"]} | {SITE["name"]}',
        description=m[f"{key}.summary"], nav=nav, main=main, footer=footer,
        i18n=i18n_block(locales, order, keep=PROJECT_KEYS), locales=locales, order=order,
        og_image=image or "images/og-card.jpg")


# ───────── MECU Interactive ─────────

def type_cover(title):
    """Typographic stand-in until a game has real cover art."""
    return (f'<span class="cover-type" aria-hidden="true"><span class="cover-type-word">{escape(title)}</span>'
            f'<span class="mecu-mark"></span><span class="cover-type-tag">{escape(STUDIO["name"])}</span></span>')


def game_cover(game, root):
    if game.get("cover"):
        return f'<img src="{root}{escape(game["cover"])}" alt="" width="1600" height="900" loading="lazy">'
    return type_cover(game["title"])


def update_rows(updates, m, root):
    rows = ""
    for update in updates:
        key = f'studio.update.{update["key"]}'
        tag_key = f'studio.updates.tag.{update["tag"]}'
        for needed in (f"{key}.title", f"{key}.body", tag_key):
            if needed not in m:
                sys.exit(f"Add {needed} to every locales/*.json for the update '{update['key']}'")
        media = (f'<span class="update-media"><img src="{root}{escape(update["image"])}" alt="" width="640" height="360" loading="lazy"></span>'
                 if update.get("image") else "")
        actions = ""
        if update.get("video"):
            actions += (f'<button class="btn btn-small" type="button" data-video="{root}{escape(update["video"])}"'
                        + (f' data-poster="{root}{escape(update["image"])}"' if update.get("image") else "")
                        + f'>{PLAY}<span data-i18n="studio.updates.watch">{escape(m["studio.updates.watch"])}</span></button>')
        if update.get("link"):
            actions += (f'<a class="btn btn-ghost btn-small" href="{escape(update["link"])}" {EXTERNAL}>'
                        f'<span data-i18n="studio.updates.open">{escape(m["studio.updates.open"])}</span>{ARROW}{NEW_TAB}</a>')
        rows += (
            f'<article class="update" data-reveal><div class="update-meta"><time datetime="{escape(update["date"])}">'
            f'{escape(update["date"].replace("-", "."))}</time><span class="tag" data-i18n="{tag_key}">{escape(m[tag_key])}</span></div>'
            f'<div class="update-copy"><h3 class="update-title" data-i18n="{key}.title">{escape(m[f"{key}.title"])}</h3>'
            f'<p class="update-body" data-i18n="{key}.body">{escape(m[f"{key}.body"])}</p>'
            f'<div class="update-actions">{actions}</div></div>{media}</article>'
        )
    return rows


def studio_nav(m, root=""):
    """`root` is "" on the studio home and "../../" on game pages (links then leave the page)."""
    items = [("games", "studio.nav.games"), ("about", "studio.nav.about"), ("updates", "studio.nav.updates"),
             ("instagram", "studio.nav.instagram")]
    out = " nav-out" if root else ""
    return "".join(f'<a class="nav-link{out}" href="{root}#{target}" data-i18n="{key}">{escape(m[key])}</a>'
                   for target, key in items)


def studio_footer(m, root):
    back = m["studio.back"].replace("{name}", SITE["name"])
    return (
        '<div class="footer-word footer-wordmark" aria-hidden="true"></div>'
        f'<div class="footer-row"><p class="site-footer"><span>© {YEAR}</span> <span data-i18n="studio.footer">{escape(m["studio.footer"])}</span></p>'
        f'<a class="footer-link" href="{escape(STUDIO_IG["url"])}" {EXTERNAL}>Instagram{ARROW}{NEW_TAB}</a>'
        f'<a class="footer-link" href="{root}" data-i18n="studio.back">{escape(back)}</a></div>'
    )


def studio_home(locales, order):
    m = locales[DEFAULT_LANGUAGE]["messages"]
    root = "../"
    name = STUDIO["name"]
    founder = m["studio.hero.founder"].replace("{name}", SITE["name"])
    intro = STUDIO.get("intro") or {}
    intro_layer = (
        f'<div class="s-intro" id="studio-intro" hidden><video muted playsinline preload="none" '
        f'poster="{root}{escape(intro.get("poster", ""))}" data-src="{root}{escape(intro["video"])}"></video>'
        f'<button class="intro-skip" id="studio-intro-skip" type="button" data-i18n="gate.skip">Skip intro</button></div>'
        if intro.get("video") else "")
    replay = (f'<button class="btn btn-ghost" type="button" data-video="{root}{escape(intro["video"])}" '
              f'data-poster="{root}{escape(intro.get("poster", ""))}">{PLAY}<span data-i18n="studio.hero.replay">'
              f'{escape(m["studio.hero.replay"])}</span></button>' if intro.get("video") else "")
    hero = (
        '<header class="hero s-hero"><div class="s-hero-mark mecu-mark" aria-hidden="true"></div>'
        f'<div class="hero-meta"><p class="eyebrow" data-reveal data-i18n="studio.hero.kicker">{escape(m["studio.hero.kicker"])}</p>'
        f'<a class="hero-studio" data-reveal href="{root}" data-i18n="studio.hero.founder">{escape(founder)}</a></div>'
        f'<h1 class="hero-title s-title" data-split>{words(name)}</h1>'
        f'<div class="hero-foot"><p class="hero-subtitle" data-reveal data-i18n="studio.hero.tagline">{escape(m["studio.hero.tagline"])}</p>'
        f'<div class="hero-actions" data-reveal><a class="btn" href="#games"><span data-i18n="studio.games.heading">'
        f'{escape(m["studio.games.heading"])}</span>{ARROW}</a>{replay}</div></div></header>'
    )
    band = marquee([("", game["title"]) for game in STUDIO["games"]]
                   + [("studio.hero.kicker", m["studio.hero.kicker"]), ("", name)])

    cards = ""
    for game in STUDIO["games"]:
        key = f'studio.game.{game["slug"]}'
        cards += (
            f'<a class="game-card" href="games/{escape(game["slug"])}/" data-reveal data-goatcounter-click="game-{escape(game["slug"])}">'
            f'<span class="game-cover">{game_cover(game, root)}</span>'
            f'<span class="game-info">{status_pill("studio.status", game["status"], m)}'
            f'<span class="game-title">{escape(game["title"])}</span>'
            f'<span class="game-tagline" data-i18n="{key}.tagline">{escape(m[f"{key}.tagline"])}</span>'
            f'<span class="btn"><span data-i18n="studio.games.view">{escape(m["studio.games.view"])}</span>{ARROW}</span></span></a>'
        )
    games = (
        '<section id="games" class="block games" aria-labelledby="games-heading">'
        + block_head(1, "games-heading", "studio.games.heading", m["studio.games.heading"],
                     "studio.games.intro", m["studio.games.intro"])
        + f'<div class="game-list">{cards}</div>'
        f'<p class="games-soon" data-reveal data-i18n="studio.games.soon">{escape(m["studio.games.soon"])}</p></section>'
    )

    principles = "".join(
        f'<li data-reveal><span class="principle-no" aria-hidden="true">{i + 1:02d}</span>'
        f'<h3 data-i18n="studio.about.p{i}.title">{escape(m[f"studio.about.p{i}.title"])}</h3>'
        f'<p data-i18n="studio.about.p{i}.body">{escape(m[f"studio.about.p{i}.body"])}</p></li>' for i in range(3))
    about = (
        '<section id="about" class="block s-about" aria-labelledby="about-heading">'
        + block_head(2, "about-heading", "studio.about.heading", m["studio.about.heading"])
        + f'<p class="about-lead" data-reveal data-i18n="studio.about.lead">{escape(m["studio.about.lead"].replace("{name}", SITE["name"]))}</p>'
        f'<p class="about-body" data-reveal data-i18n="studio.about.body">{escape(m["studio.about.body"])}</p>'
        f'<ol class="principles">{principles}</ol></section>'
    )

    rows = update_rows(STUDIO.get("updates", []), m, root)
    updates = (
        '<section id="updates" class="block updates" aria-labelledby="updates-heading">'
        + block_head(3, "updates-heading", "studio.updates.heading", m["studio.updates.heading"],
                     "studio.updates.intro", m["studio.updates.intro"])
        + (f'<div class="update-list">{rows}</div>' if rows else
           f'<p class="empty-note" data-reveal data-i18n="studio.updates.empty">{escape(m["studio.updates.empty"])}</p>')
        + '</section>'
    )

    instagram_section = (
        '<section id="instagram" class="block instagram" aria-labelledby="instagram-heading">'
        + block_head(4, "instagram-heading", "studio.ig.heading", m["studio.ig.heading"],
                     "studio.ig.intro", m["studio.ig.intro"])
        + f'<div class="ig">{instagram_feed(STUDIO_IG, m, root, "h3")}'
        f'<div class="ig-actions" data-reveal>{instagram.follow_button(STUDIO_IG, m)}</div></div></section>'
    )

    contact = (
        '<section class="teaser s-contact" data-reveal aria-labelledby="s-contact-title"><div class="teaser-link">'
        '<span class="teaser-copy">'
        f'<span id="s-contact-title" class="teaser-title" role="heading" aria-level="2" data-i18n="studio.contact.heading">{escape(m["studio.contact.heading"])}</span>'
        f'<span class="teaser-body" data-i18n="studio.contact.body">{escape(m["studio.contact.body"])}</span>'
        f'<span class="teaser-actions"><a class="btn btn-invert" href="{root}#contact"><span data-i18n="studio.contact.cta">'
        f'{escape(m["studio.contact.cta"])}</span>{ARROW}</a>'
        f'<a class="btn btn-invert btn-ghost" href="{escape(STUDIO_IG["url"])}" {EXTERNAL}>Instagram{ARROW}{NEW_TAB}</a></span>'
        '</span></div></section>'
    )
    data = (f'<script id="instagram-data" type="application/json">'
            f'{script_json(instagram.viewer_data(STUDIO_IG, root))}</script>' if instagram.has_viewer(STUDIO_IG) else "")
    main = intro_layer + hero + band + f'<div class="sections">{games}{about}{updates}{instagram_section}{contact}</div>'
    return subpage(
        STUDIO["path"], brand="mecu", title=m["studio.meta.title"],
        description=m["studio.meta.description"].replace("{name}", SITE["name"]),
        title_key="studio.meta.title", description_key="studio.meta.description",
        nav=studio_nav(m), main=main, footer=studio_footer(m, root),
        i18n=i18n_block(locales, order, keep=STUDIO_KEYS + ("gate.skip",)), locales=locales, order=order,
        og_image="images/mecu/og-card.jpg", extra_css=("studio.css", "instagram.css", "media.css"),
        extra_js=("media.js", "instagram.js", "studio.js"),
        data=data)


def game_page(game, locales, order):
    m = locales[DEFAULT_LANGUAGE]["messages"]
    root = "../../../"
    key = f'studio.game.{game["slug"]}'
    for needed in (f"{key}.tagline", f"{key}.summary"):
        if needed not in m:
            sys.exit(f"Add {needed} to every locales/*.json for the game '{game['title']}'")
    fact = lambda label_key, value: (f'<div><dt data-i18n="{label_key}">{escape(m[label_key])}</dt><dd>{value}</dd></div>')
    tba = f'<span data-i18n="studio.game.tba">{escape(m["studio.game.tba"])}</span>'
    platforms = ", ".join(escape(p) for p in game.get("platforms", [])) or tba
    facts = (fact("studio.game.facts.status", status_pill("studio.status", game["status"], m))
             + fact("studio.game.facts.developer", escape(STUDIO["name"]))
             + fact("studio.game.facts.platforms", platforms)
             + (fact("studio.game.facts.genre", escape(game["genre"])) if game.get("genre") else ""))
    shots = "".join(
        f'<a class="shot" href="{root}{escape(shot["src"])}" data-lightbox="{escape(game["slug"])}"'
        + (f' data-caption="{escape(shot["caption"])}"' if shot.get("caption") else "")
        + f'><img src="{root}{escape(shot.get("thumb") or shot["src"])}" alt="{escape(shot.get("caption", ""))}" loading="lazy"></a>'
        for shot in game.get("gallery", []))
    gallery = (
        f'<section class="block game-gallery" aria-labelledby="gallery-heading">'
        + block_head(2, "gallery-heading", "studio.game.gallery", m["studio.game.gallery"])
        + (f'<div class="shot-grid" data-reveal>{shots}</div>' if shots else
           f'<div class="empty-note empty-frame" data-reveal><span class="mecu-mark" aria-hidden="true"></span>'
           f'<p data-i18n="studio.game.galleryEmpty">{escape(m["studio.game.galleryEmpty"])}</p></div>')
        + '</section>'
    )
    number = 3
    trailer = ""
    if game.get("trailer"):
        attr = "data-embed" if re.match(r"https://(www\.youtube(-nocookie)?\.com|player\.vimeo\.com)/", game["trailer"]) else "data-video"
        source = game["trailer"] if attr == "data-embed" else root + game["trailer"]
        trailer = (
            '<section class="block game-trailer" aria-labelledby="trailer-heading">'
            + block_head(number, "trailer-heading", "studio.game.trailer", m["studio.game.trailer"])
            + f'<button class="trailer" type="button" data-reveal {attr}="{escape(source)}" data-title="{escape(game["title"])}">'
            f'<span class="game-cover">{game_cover(game, root)}</span><span class="trailer-play">{PLAY}'
            f'<span data-i18n="media.playTrailer">{escape(m["media.playTrailer"])}</span></span></button></section>'
        )
        number += 1
    links = "".join(
        f'<a class="btn" href="{escape(link["url"])}" {EXTERNAL}>{escape(link["label"])}{ARROW}{NEW_TAB}</a>'
        for link in game.get("links", []))
    store = ""
    if links:
        store = ('<section class="block game-get" aria-labelledby="get-heading">'
                 + block_head(number, "get-heading", "studio.game.get", m["studio.game.get"])
                 + f'<div class="page-actions" data-reveal>{links}</div></section>')
        number += 1
    related = update_rows([u for u in STUDIO.get("updates", []) if u.get("game") == game["slug"]], m, root)
    news = ""
    if related:
        news = ('<section class="block updates" aria-labelledby="updates-heading">'
                + block_head(number, "updates-heading", "studio.game.updates", m["studio.game.updates"])
                + f'<div class="update-list">{related}</div></section>')
    main = (
        '<header class="page-hero game-hero">'
        f'<a class="back-link" data-reveal href="../../#games">{ARROW}<span data-i18n="studio.game.back">{escape(m["studio.game.back"])}</span></a>'
        f'<h1 class="page-title" data-split>{words(game["title"])}</h1>'
        f'<p class="page-summary" data-reveal data-i18n="{key}.tagline">{escape(m[f"{key}.tagline"])}</p></header>'
        # Without real cover art the title above already says it all; skip the stand-in.
        + (f'<figure class="page-figure game-cover" data-reveal>{game_cover(game, root)}</figure>' if game.get("cover") else "")
        + 
        '<div class="sections"><section class="block game-body" aria-labelledby="game-about">'
        + block_head(1, "game-about", "studio.game.about", m["studio.game.about"])
        + f'<div class="game-about"><p class="about-lead" data-reveal data-i18n="{key}.summary">{escape(m[f"{key}.summary"])}</p>'
        f'<dl class="facts" data-reveal>{facts}</dl></div></section>{gallery}{trailer}{store}{news}</div>'
    )
    return subpage(
        f'{STUDIO["path"]}/games/{game["slug"]}', brand="mecu", title=f'{game["title"]} | {STUDIO["name"]}',
        description=m[f"{key}.summary"], nav=studio_nav(m, "../../"), main=main, footer=studio_footer(m, root),
        i18n=i18n_block(locales, order, keep=STUDIO_KEYS), locales=locales, order=order,
        og_image=game.get("cover") or "images/mecu/og-card.jpg",
        extra_css=("studio.css", "media.css"), extra_js=("media.js",))


# ───────── Share pages, QR, sitemap ─────────

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
            f'<body style="background:#0a0a0b;color:#fff;font-family:system-ui"><a href="{target}">{title}</a></body></html>\n',
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


def sitemap(urls):
    body = "".join(f"<url><loc>{escape(url)}</loc></url>" for url in urls)
    (ROOT / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>\n',
        encoding="utf-8", newline="\n")


def load_locales():
    locales = {}
    for path in sorted((ROOT / "locales").glob("*.json")):
        locales[path.stem] = json.loads(path.read_text(encoding="utf-8-sig"))
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


def main():
    locales = load_locales()
    base = SITE.get("site_url", "").rstrip("/") + "/"
    order = [c for c in LANGUAGE_ORDER if c in locales] + sorted(set(locales) - set(LANGUAGE_ORDER))
    m = locales[DEFAULT_LANGUAGE]["messages"]
    groups = {i: (release_card(i, title, links) if i == 0 else link_group(i, title, links, reveal=i != 3))
              for i, (title, links) in enumerate(SITE["groups"])}
    extra = "".join(v for i, v in groups.items() if i > 3)
    # Page order: music, about (+ Instagram and socials), projects, contact (+ more links).
    number = 1
    sections = music_section(number, m, groups)
    number += 1
    sections += about_section(number, m, groups.get(2, ""))
    projects = projects_section(number + 1, m)
    if projects:
        number += 1
    more = groups.get(3, "") + extra
    contact = contact_section(number + 1, m, f'<div class="contact-links" data-reveal>{more}</div>' if more else "")
    sections += projects + contact

    tracks = [{**t, "artist": t.get("artist", SITE["name"]), "slug": slugify(t["title"])} for t in SITE["tracks"]]
    for track in tracks:
        track["share"] = base + "s/" + track["slug"] + "/"
    roles = [(f"about.role.{i}", m[f"about.role.{i}"]) for i in range(3)]
    person = {"@context": "https://schema.org", "@type": "Person", "name": SITE["name"], "url": base,
              "sameAs": [url for _title, links in SITE["groups"][1:] for _label, url, _icon in links if url]}
    # The Instagram styles and the story viewer load only when the page uses them.
    shown = bool(SITE_IG and (SITE_IG["posts"] or SITE_IG["highlights"]))
    viewer = bool(shown and instagram.has_viewer(SITE_IG))
    styles = (["instagram.css"] if shown else []) + (["media.css"] if viewer else [])
    scripts = (["media.js"] if viewer else []) + (["instagram.js"] if shown else [])
    fill("index.html", {
        "__SECTIONS__": sections,
        "__NAV__": home_nav(m, bool(projects), bool(contact_form())),
        "__MARQUEE__": marquee(roles + [("", "ECU"), ("", STUDIO["name"])]),
        "__ANALYTICS__": analytics_tag(),
        "__LANGUAGE_OPTIONS__": language_options(locales, order),
        "__TRACK_DATA__": script_json({"name": SITE["name"], "site": base, "tracks": tracks}),
        "__I18N_DATA__": i18n_block(locales, order, skip=HOME_SKIP + (() if viewer else VIEWER_KEYS)),
        "__EXTRA_STYLES__": "".join(f'<link rel="stylesheet" href="assets/css/{name}">' for name in styles),
        "__EXTRA_SCRIPTS__": "".join(f'<script src="assets/js/{name}" defer></script>' for name in scripts),
        "__DATA__": (f'<script id="instagram-data" type="application/json">'
                     f'{script_json(instagram.viewer_data(SITE_IG, ""))}</script>' if viewer else ""),
        "__JSON_LD__": script_json(person),
        "__FIRST_COVER__": escape(tracks[0]["cover"]) if tracks else "",
        "__FIRST_TITLE__": escape(tracks[0]["title"]) if tracks else "",
        "__DESCRIPTION__": escape(m["meta.description"].replace("{name}", SITE["name"])),
        "__TAGLINE__": escape(SITE["tagline"]),
        "__TITLE_WORDS__": words(SITE["name"]),
        "__STUDIO_PATH__": escape(STUDIO["path"]),
        "__STUDIO_NAME__": escape(STUDIO["name"]),
        "__SITE_URL__": escape(base),
        "__YEAR__": YEAR,
        "__NAME__": escape(SITE["name"]),
    }, "index.html")

    # Drop pages of projects that no longer have one.
    slugs = {project_slug(p) for p in SITE.get("projects", []) if p.get("page")}
    folder = ROOT / "projects"
    if folder.exists():
        for old in folder.iterdir():
            if old.is_dir() and old.name not in slugs:
                shutil.rmtree(old, ignore_errors=True)
        if not any(folder.iterdir()):
            folder.rmdir()
    urls = [base]
    urls += [project_page(p, locales, order) for p in SITE.get("projects", []) if p.get("page")]
    urls.append(studio_home(locales, order))
    urls += [game_page(game, locales, order) for game in STUDIO["games"]]
    share_pages(tracks, base)
    qr_code(base)
    sitemap(urls)
    print(f"built {len(urls)} pages: {len(SITE['groups'])} link groups, {len(tracks)} tracks, {len(order)} languages,"
          f" {len(STUDIO['games'])} games, {len(STUDIO.get('updates', []))} updates,"
          f" Instagram {len(SITE_IG['posts']) if SITE_IG else 0} + {len(STUDIO_IG['posts'])} posts,"
          f" countdown {'on' if (SITE.get('upcoming') or {}).get('enabled') else 'off'},"
          f" analytics {'on' if analytics_tag() else 'off'}, contact {'on' if contact_form() else 'off'}")


if __name__ == "__main__":
    main()
