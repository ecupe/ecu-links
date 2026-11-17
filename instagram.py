"""Instagram components and their data (standard library only).

Instagram offers no way to load a public feed or Story Highlights into a static page, so each
account is a hand-kept data file: data/instagram/<handle>.json. The components below turn that
file into markup; the page design never has to change when posts or highlights do.

    account = instagram.load("mateoamendano")
    instagram.highlights(account, root, messages)   # InstagramHighlights (rail of InstagramHighlight)
    instagram.gallery(account, root, messages)      # InstagramGallery (grid of InstagramPostCard)
    instagram.viewer_data(account, root)            # slides for the story viewer (assets/js/media.js)

load() checks every entry. A broken one (bad link, missing image, unknown type) is left out with
a note in the build output, so one mistake in the data can never break the page.

Run `py instagram.py` to check every data file without building.
"""
from html import escape
import json
import re

from ui import ARROW, EXTERNAL, NEW_TAB, PLAY, ROOT, STACK, icon

DATA = ROOT / "data" / "instagram"
PROFILE_URL = re.compile(r"^https://www\.instagram\.com/[\w.]+/$")
POST_URL = re.compile(r"^https://www\.instagram\.com/(?:[\w.]+/)?(?:p|reel|tv)/[\w-]+/$")
HIGHLIGHT_URL = re.compile(r"^https://www\.instagram\.com/stories/highlights/\d+/$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
IMAGES = {".jpg", ".jpeg", ".png", ".webp", ".avif"}
VIDEOS = {".mp4", ".webm"}
POST_TYPES = ("image", "carousel", "reel")
BADGES = {"reel": (PLAY, "ig.reel", "Reel"), "carousel": (STACK, "ig.carousel", "Carousel")}


class Invalid(ValueError):
    """One entry of a data file cannot be used; the message says why."""


def local_file(path, kinds, what):
    """A path inside the site (never a link: Instagram's own image links expire)."""
    if not isinstance(path, str) or not path.strip():
        raise Invalid(f"{what} is missing")
    if re.match(r"^[a-z][a-z0-9+.-]*:|^//", path, re.I) or path.startswith(("/", "\\")) or ".." in path.replace("\\", "/").split("/"):
        raise Invalid(f"{what} must be a file inside the site, not '{path}'")
    file = ROOT / path
    if file.suffix.lower() not in kinds:
        raise Invalid(f"{what} '{path}' must be one of {', '.join(sorted(kinds))}")
    if not file.is_file():
        raise Invalid(f"{what} '{path}' does not exist")
    return path.replace("\\", "/")


def text(value, limit):
    return " ".join(str(value or "").split())[:limit]


def clean_post(raw):
    if not isinstance(raw, dict):
        raise Invalid("it is not an object")
    url = str(raw.get("url", "")).strip()
    if not POST_URL.match(url):
        raise Invalid(f"url '{url}' is not an Instagram post link (https://www.instagram.com/p/…/ or /reel/…/)")
    kind = raw.get("type", "image")
    if kind not in POST_TYPES:
        raise Invalid(f"type '{kind}' must be one of {', '.join(POST_TYPES)}")
    date = str(raw.get("date", "")).strip()
    if date and not DATE.match(date):
        raise Invalid(f"date '{date}' must look like 2026-11-15")
    return {
        "id": text(raw.get("id") or url.rstrip("/").rsplit("/", 1)[-1], 80),
        "url": url,
        "image": local_file(raw.get("image"), IMAGES, "image"),
        "type": kind,
        "caption": text(raw.get("caption"), 600),
        "alt": text(raw.get("alt"), 300),
        "lang": text(raw.get("lang"), 12),
        "date": date,
    }


def clean_slide(raw):
    if not isinstance(raw, dict):
        raise Invalid("a slide is not an object")
    kind = raw.get("type", "image")
    if kind not in ("image", "video"):
        raise Invalid(f"slide type '{kind}' must be image or video")
    slide = {"type": kind, "src": local_file(raw.get("src"), VIDEOS if kind == "video" else IMAGES, "slide file")}
    if raw.get("poster"):
        slide["poster"] = local_file(raw["poster"], IMAGES, "slide poster")
    if raw.get("alt"):
        slide["alt"] = text(raw["alt"], 300)
    return slide


def clean_highlight(raw, note):
    if not isinstance(raw, dict):
        raise Invalid("it is not an object")
    title = text(raw.get("title"), 60)
    if not title:
        raise Invalid("title is missing")
    url = str(raw.get("url", "")).strip()
    if url and not HIGHLIGHT_URL.match(url):
        raise Invalid(f"url '{url}' is not a highlight link (https://www.instagram.com/stories/highlights/<number>/)")
    slides = []
    for number, slide in enumerate(raw.get("slides") or [], 1):
        try:
            slides.append(clean_slide(slide))
        except Invalid as problem:
            note(f"highlight '{title}': slide {number} left out: {problem}")
    if not slides and not url:
        raise Invalid("it has no slides and no link, so there is nothing to open")
    return {
        "id": text(raw.get("id") or title, 80),
        "title": title,
        "cover": local_file(raw.get("cover"), IMAGES, "cover"),
        "url": url,
        "slides": slides,
    }


def arrange(entries):
    """Visible entries only: lowest `order` first, then newest date, then the order in the file."""
    newest = sorted(entries, key=lambda pair: pair[1].get("date", ""), reverse=True)

    def rank(pair):
        order = pair[0].get("order")
        return order if isinstance(order, (int, float)) and not isinstance(order, bool) else float("inf")
    return [item for _raw, item in sorted(newest, key=rank)]


def load(handle, quiet=False):
    """Read and check data/instagram/<handle>.json. Never raises for bad entries."""
    notes = []
    note = lambda message: notes.append(f"instagram/{handle}: {message}")
    account = {"handle": handle, "url": f"https://www.instagram.com/{handle}/", "posts": [], "highlights": []}
    path = DATA / f"{handle}.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(raw, dict):
            raise ValueError("the file must hold one object")
    except (OSError, ValueError) as problem:
        note(f"{path.name} could not be read, so nothing is shown: {problem}")
        raw = {}
    if raw.get("url"):
        if PROFILE_URL.match(str(raw["url"])):
            account["url"] = raw["url"]
        else:
            note(f"url '{raw['url']}' is not an Instagram profile link; using {account['url']}")
    for name, clean in (("posts", clean_post), ("highlights", lambda entry: clean_highlight(entry, note))):
        kept, seen = [], set()
        entries = raw.get(name) or []
        if not isinstance(entries, list):
            note(f"'{name}' must be a list")
            entries = []
        for number, entry in enumerate(entries, 1):
            label = f"{name[:-1]} {number}"
            try:
                item = clean(entry)
                if item["id"] in seen:
                    raise Invalid(f"id '{item['id']}' is used twice")
                seen.add(item["id"])
                if entry.get("visible", True) is not False:
                    kept.append((entry, item))
            except Invalid as problem:
                note(f"{label} left out: {problem}")
        account[name] = arrange(kept)
    account["notes"] = notes
    if not quiet:
        for message in notes:
            print("warning:", message)
    return account


# ───────── Components ─────────

def post_card(post, root, m):
    """InstagramPostCard: one tile that opens the original post."""
    badge = ""
    if post["type"] in BADGES:
        glyph, key, label = BADGES[post["type"]]
        badge = f'<span class="ig-badge">{glyph}<span data-i18n="{key}">{escape(m.get(key, label))}</span></span>'
    caption = (f'<span class="ig-text" dir="auto"{" lang=" + chr(34) + escape(post["lang"]) + chr(34) if post["lang"] else ""}>'
               f'{escape(post["caption"])}</span>' if post["caption"] else "")
    date = (f'<time class="ig-date" datetime="{post["date"]}">{post["date"].replace("-", ".")}</time>'
            if post["date"] else "")
    return (
        f'<li class="ig-item"><a class="ig-post" href="{escape(post["url"])}" {EXTERNAL} data-type="{post["type"]}" '
        f'data-goatcounter-click="ig-post-{escape(post["id"])}">'
        f'<span class="ig-media"><img src="{root}{escape(post["image"])}" alt="{escape(post["alt"] or post["caption"])}" '
        f'width="480" height="600" loading="lazy" decoding="async"></span>{badge}'
        f'<span class="ig-caption">{caption}{date}<span class="ig-open"><span data-i18n="ig.viewPost">'
        f'{escape(m["ig.viewPost"])}</span>{ARROW}</span></span>{NEW_TAB}</a></li>'
    )


def gallery(account, root, m):
    """InstagramGallery: the post grid, ending in a tile that leads to the profile."""
    cards = "".join(post_card(post, root, m) for post in account["posts"])
    return (
        f'<ul class="ig-grid">{cards}<li class="ig-item ig-more"><a class="ig-follow" href="{escape(account["url"])}" '
        f'{EXTERNAL} data-goatcounter-click="ig-profile-{escape(account["handle"])}">{icon("instagram.svg")}'
        f'<span class="ig-handle">@{escape(account["handle"])}</span>'
        f'<span data-i18n="ig.more">{escape(m["ig.more"])}</span>{NEW_TAB}</a></li></ul>'
    )


def highlight(item, index, root):
    """InstagramHighlight: a round cover and a title. With slides it opens the story viewer;
    with only a link it opens Instagram."""
    inner = (f'<span class="hl-ring"><span class="hl-cover"><img src="{root}{escape(item["cover"])}" alt="" width="150" height="150" '
             f'loading="lazy" decoding="async"></span></span><span class="hl-title" dir="auto">{escape(item["title"])}</span>')
    if item["slides"]:
        return f'<li><button class="hl" type="button" data-highlight="{index}">{inner}</button></li>'
    return (f'<li><a class="hl" href="{escape(item["url"])}" {EXTERNAL} '
            f'data-goatcounter-click="ig-highlight-{escape(item["id"])}">{inner}{NEW_TAB}</a></li>')


def highlights(account, root, m):
    """InstagramHighlights: the scrolling rail. Empty when the account has none."""
    if not account["highlights"]:
        return ""
    items = "".join(highlight(item, index, root) for index, item in enumerate(account["highlights"]))
    return f'<ul class="hl-rail" data-i18n-aria-label="ig.highlights" aria-label="{escape(m["ig.highlights"])}">{items}</ul>'


def follow_button(account, m):
    return (f'<a class="btn" href="{escape(account["url"])}" {EXTERNAL} data-goatcounter-click="ig-follow-{escape(account["handle"])}">'
            f'{icon("instagram.svg")}<span data-i18n="ig.follow">{escape(m["ig.follow"])}</span>{ARROW}{NEW_TAB}</a>')


def has_viewer(account):
    """True when at least one highlight plays in the story viewer (the page then loads media.js)."""
    return any(item["slides"] for item in account["highlights"])


def viewer_data(account, root):
    """InstagramViewer data: what assets/js/media.js reads from <script id="instagram-data">."""
    return {
        "instagram": account["url"],
        "highlights": [{
            "key": item["id"], "title": item["title"], "cover": root + item["cover"], "url": item["url"],
            "slides": [{**slide, "src": root + slide["src"],
                        **({"poster": root + slide["poster"]} if slide.get("poster") else {})}
                       for slide in item["slides"]],
        } for item in account["highlights"]],
    }


if __name__ == "__main__":
    for file in sorted(DATA.glob("*.json")):
        found = load(file.stem)
        print(f"{file.stem}: {len(found['posts'])} posts and {len(found['highlights'])} highlights shown,"
              f" {len(found['notes'])} problems")
