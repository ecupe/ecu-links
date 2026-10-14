# ECU Music & Links
# Run: py build.py
# Then: py serve.py
# Open: http://localhost:8000
# Python uses only its standard library. Music and cover files are in this project.
from pathlib import Path
from html import escape
from urllib.parse import quote
import json
import re

ROOT = Path(__file__).resolve().parent

# Edit site.json for profile, links, and playlist settings.
CONFIG = json.loads((ROOT / "site.json").read_text(encoding="utf-8"))
NAME = CONFIG["name"]
TAGLINE = CONFIG["tagline"]
GROUPS = CONFIG["groups"]
TRACKS = CONFIG["tracks"]
ICON_SOURCES = {path.name: "images/icons/" + path.name for path in (ROOT / "images/icons").glob("*.svg")}
PAGE_TEMPLATE = (ROOT / "templates/index.html").read_text(encoding="utf-8")


def script_json(value):
    """Serialize data safely inside a script element, including custom names."""
    return json.dumps(value, ensure_ascii=False).replace("<", "\\u003c").replace("&", "\\u0026")


def language_data():
    catalogs = {}
    for path in sorted((ROOT / "locales").glob("*.json")):
        code = path.stem.lower().replace("_", "-")
        if not re.fullmatch(r"[a-z]{2,3}(?:-[a-z0-9]{2,8})*", code):
            raise ValueError(f"Use a language-code filename for {path.name}")
        if code in catalogs:
            raise ValueError(f"Duplicate language catalog: {code}")
        catalog = json.loads(path.read_text(encoding="utf-8"))
        if catalog.get("dir") not in {"ltr", "rtl"}:
            raise ValueError(f"Invalid text direction in {path.name}")
        if not isinstance(catalog.get("name"), str) or not catalog["name"].strip():
            raise ValueError(f"Missing native language name in {path.name}")
        catalogs[code] = catalog
    if "en" not in catalogs:
        raise ValueError("The English source catalog locales/en.json is required.")
    source = catalogs["en"]["messages"]
    for code, catalog in catalogs.items():
        messages = catalog["messages"]
        if messages.keys() != source.keys():
            raise ValueError(f"{code}: translation keys must match locales/en.json")
        for key, message in messages.items():
            if not isinstance(message, str) or not message.strip():
                raise ValueError(f"{code}: empty or invalid translation for {key}")
            tokens = set(re.findall(r"\{\w+\}", message))
            if tokens != set(re.findall(r"\{\w+\}", source[key])):
                raise ValueError(f"{code}: interpolation tokens do not match for {key}")
    # Custom English content stays editable through the existing site config.
    source["content.tagline"] = TAGLINE
    for index, (heading, _) in enumerate(GROUPS):
        key = f"content.group.{index}"
        source[key] = heading
        for code, catalog in catalogs.items():
            if key not in catalog["messages"]:
                print(f"Translation needed: {code} / {key}; using {heading!r}")
                catalog["messages"][key] = heading
    order = ["en", "es", "pt", "fr", "de", "it", "ar"]
    codes = [code for code in order if code in catalogs]
    codes += [code for code in catalogs if code not in codes]
    options = "".join(
        '<option value="' + escape(code, quote=True) + '" lang="' + escape(code, quote=True)
        + '">' + escape(catalogs[code]["name"]) + '</option>' for code in codes
    )
    return {"name": NAME, "defaultLanguage": "en", "locales": catalogs}, options

# PAGE GENERATION
ARROW = '<svg class="link-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 17 17 7M7 7h10v10"/></svg>'

def safe_asset_uri(relative_path):
    return quote(Path(relative_path).as_posix(), safe="/")

def profile_markup():
    image_folder = ROOT / "images"
    candidates = []
    if image_folder.exists():
        candidates = sorted(
            item for item in image_folder.iterdir()
            if item.is_file() and item.stem.lower() == "profile"
            and item.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
        )
    if candidates:
        path = candidates[0].relative_to(ROOT).as_posix()
        return '<img class="profile-photo" src="' + escape(safe_asset_uri(path), quote=True) + '" alt="' + escape(NAME, quote=True) + '" width="110" height="110">'
    initials = "".join(word[0] for word in NAME.split()[:2])
    return '<span class="profile-photo avatar-initials" aria-label="' + escape(NAME, quote=True) + '">' + escape(initials) + '</span>'

def available_tracks():
    playlist = []
    for configured in TRACKS:
        if not (ROOT / configured["src"]).is_file():
            print("Missing audio:", configured["src"])
            continue
        track = dict(configured)
        track["artist"] = NAME
        track["src"] = safe_asset_uri(configured["src"])
        cover = configured.get("cover", "")
        track["cover"] = safe_asset_uri(cover) if cover and (ROOT / cover).is_file() else ""
        playlist.append(track)
    return playlist

def link_markup(label, url, icon_file):
    return (
        '<a class="link-button" href="' + escape(url, quote=True)
        + '" target="_blank" rel="noopener noreferrer">'
        + '<img class="link-icon" src="' + ICON_SOURCES[icon_file] + '" alt="" width="20" height="20">'
        + '<span class="link-label">' + escape(label) + '</span>'
        + ARROW + '<span class="sr-only" data-i18n="link.newTab">Opens in a new tab</span></a>'
    )

def section_markup(playlist):
    result = []
    for index, (heading, links) in enumerate(GROUPS):
        featured = index == 0
        content = []
        for label, url, icon_file in links:
            if featured and playlist:
                artwork = playlist[0].get("cover", "")
                image = '<img class="release-art" src="' + escape(artwork, quote=True) + '" alt="" width="94" height="94">' if artwork else ""
                content.append(
                    '<a class="release-link" href="' + escape(url, quote=True)
                    + '" target="_blank" rel="noopener noreferrer">' + image
                    + '<span class="release-copy"><span class="release-kicker" data-i18n="release.kicker">Latest release</span>'
                    + '<span class="release-title">' + escape(label) + '</span>'
                    + '<span class="release-cta"><img class="link-icon" src="' + ICON_SOURCES[icon_file]
                    + '" alt="" width="15" height="15"><span data-i18n="release.cta">Watch the lyric video</span>' + ARROW
                    + '</span></span><span class="sr-only" data-i18n="link.newTab">Opens in a new tab</span></a>'
                )
            else:
                content.append(link_markup(label, url, icon_file))
        result.append(
            '<section class="link-section glass' + (' featured' if featured else '') + '">'
            + '<h2 class="section-heading" data-i18n="content.group.' + str(index) + '">' + escape(heading) + '</h2>'
            + '<div class="link-list">' + "".join(content) + '</div></section>'
        )
    return "".join(result)

def main():
    (ROOT / "audio").mkdir(exist_ok=True)
    (ROOT / "images").mkdir(exist_ok=True)
    playlist = available_tracks()
    payload = script_json({"name": NAME, "tracks": playlist})
    translations, language_options = language_data()
    first = playlist[0] if playlist else {}
    replacements = {
        "__NAME__": escape(NAME),
        "__DESCRIPTION__": escape(NAME + " — music, socials, and contact links.", quote=True),
        "__TAGLINE__": escape(TAGLINE),
        "__PROFILE__": profile_markup(),
        "__SECTIONS__": section_markup(playlist),
        "__FIRST_COVER__": escape(first.get("cover", ""), quote=True),
        "__FIRST_TITLE__": escape(first.get("title", "Music player")),
        "__TRACK_DATA__": payload,
        "__I18N_DATA__": script_json(translations),
        "__LANGUAGE_OPTIONS__": language_options,
    }
    page = PAGE_TEMPLATE
    for token, value in replacements.items():
        page = page.replace(token, value)
    output = ROOT / "index.html"
    output.write_text(page, encoding="utf-8")
    print("Created:", output)
    print("Songs in the player:", len(playlist))
    print("Preview: py serve.py")
    print("Open: http://localhost:8000")

if __name__ == "__main__":
    main()
