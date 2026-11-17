# Mateo Amendano · ECU + MECU Interactive

A static site with two identities that share one design system:

- **The personal site** (`/`): an editorial portfolio with a playlist and audio player,
  discography, an About section with Instagram highlights and posts, projects, and contact.
  Dark ink and warm paper, big type, and the gold, blue and red ECU accents.
- **MECU Interactive** (`/mecu-interactive/`): the game studio. Black and bone (the logo's own
  colours), with games, studio info, development updates, and an Instagram section.

Motion is purposeful and optional. The personal site opens by itself: the logo draws in and a
cover lifts while the name rises (under two seconds, once per visit; it never takes input, and
the first scroll, key or press ends it). The studio plays a short logo film once per visit.
Then: letter-by-letter titles, scroll reveals, and cross-fades between pages. Every animation
turns off for visitors who ask for reduced motion.

## Edit and preview

1. Edit `site.json` (personal site), `studio.json` (MECU Interactive), or a file in
   `data/instagram/` (posts and highlights).
2. Run `py build.py` to regenerate every page.
3. Run `py serve.py`, then open http://localhost:8000.

The preview server supports HTTP byte ranges so songs and videos can seek correctly.

## Pages the build writes

| Page | Source |
| --- | --- |
| `index.html` | `templates/index.html` + `site.json` |
| `projects/<slug>/index.html` | each project in `site.json` that has a `page` block (none at the moment) |
| `mecu-interactive/index.html` | `templates/page.html` + `studio.json` |
| `mecu-interactive/games/<slug>/index.html` | each game in `studio.json` |
| `s/<song>/index.html` | one share page per track |
| `sitemap.xml` | every page above |

The generated pages are committed, because GitHub Pages serves the repository as it is.

## MECU Interactive (`studio.json`)

Text lives in the locale files so it can be translated; `studio.json` holds structure, media
paths (relative to the site root), and links.

- **Add a game**: add an entry to `games` (`slug`, `title`, and `status`: `dev`, `prototype`,
  `announced` or `released`), then add `studio.game.<slug>.tagline` and
  `studio.game.<slug>.summary` to every `locales/*.json`. Optional: `cover` (a 16:9 image;
  until there is one the card shows a typographic cover), `genre`, `platforms` (a list),
  `trailer` (a YouTube or Vimeo embed URL, or a local video path), `gallery` (a list of
  `{src, thumb, caption}`), and `links` (a list of `{label, url}` for stores or downloads).
  Sections with nothing in them stay hidden.
- **Post an update**: add an entry to `updates` (`key`, `date` as `YYYY-MM-DD`, and `tag`:
  `announcement`, `devlog` or `media`), then add `studio.update.<key>.title` and `.body` to
  the locale files. Optional: `image`, `video`, `link`, and `game` (a game slug, which also
  lists the update on that game's page). Keep the newest first.
- **Intro film**: `intro.video` and `intro.poster`. Remove the `intro` block to turn it off.

`tools/make_mecu_assets.py` turns the logo files into the web assets in `images/mecu/`
(run it again if the logo changes).

## Instagram (`data/instagram/<handle>.json`)

Each account has one data file. `site.json` names the personal account (`"instagram":
"mateoamendano"`) and `studio.json` the studio's. The components in `instagram.py` turn the
file into the highlights rail and the post gallery, so adding, hiding or re-ordering content
never touches the design. After any change run `py build.py`.

```json
{
  "handle": "mateoamendano",
  "url": "https://www.instagram.com/mateoamendano/",
  "posts": [
    {"id": "DfyYojHjnRH", "url": "https://www.instagram.com/p/DfyYojHjnRH/",
     "image": "images/instagram/mateoamendano/DfyYojHjnRH.jpg", "type": "carousel",
     "caption": "14/11", "alt": "", "date": "2026-11-15", "order": 1, "visible": true}
  ],
  "highlights": [
    {"id": "18250790356312765", "title": "DS", "cover": "images/instagram/mateoamendano/highlight-18250790356312765.jpg",
     "url": "https://www.instagram.com/stories/highlights/18250790356312765/", "order": 1, "visible": true,
     "slides": [{"type": "image", "src": "images/instagram/mateoamendano/ds-1.jpg"},
                {"type": "video", "src": "media/ds-2.mp4", "poster": "images/instagram/mateoamendano/ds-2.jpg"}]}
  ]
}
```

| To… | Do this |
| --- | --- |
| Add a post | Save its picture under `images/instagram/<handle>/` and add an entry with the post's link. `type` is `image`, `carousel` or `reel`. |
| Hide a post or a highlight | Set `"visible": false`. Its data stays in the file. |
| Remove one | Delete its entry. |
| Change the order | Change `order` (lowest first). Entries without `order` follow, newest `date` first. |
| Add a highlight | Add an entry with a `title`, a `cover` picture and its Instagram `url`, or your own `slides`, or both. |
| Change a cover or title | Edit `cover` or `title`. |
| Change what a highlight plays | Edit its `slides`: your own images and videos, in order. |

- A highlight **with slides** opens in the built-in story viewer (keyboard, touch, Escape). If
  it also has a `url`, the viewer shows a "View on Instagram" link. A highlight **without
  slides** opens its `url` on Instagram.
- Pictures must be files in this site. Instagram's own image links expire, so the build refuses
  them.
- The build checks every entry. A broken one (bad link, missing file, unknown type, repeated
  `id`) is left out and reported as a `warning:` line, so a mistake never breaks the page.
  `py instagram.py` checks the data files without building.
- On the page, tiles show a loading sheen until the picture arrives and a quiet placeholder if
  it fails; the link keeps working either way.

### Why it is curated by hand, and how to automate it later

Instagram has no way to load a public feed or Story Highlights into a static page. Its Basic
Display API was shut down in December 2024. The current API (Instagram API with Instagram
Login) only serves an account's own posts, needs a professional account, a Meta developer app
and an access token that expires every 60 days, and exposes no highlights at all.

`tools/sync_instagram.py` is ready for the day that is set up: it reads the token from the
`IG_ACCESS_TOKEN` environment variable, saves the pictures locally and merges new posts into
the data file while keeping your `order`, `visible` and `alt`. Its merge has been tried with a
saved response; the live API call has not, because no token exists yet. Never commit a token.

## Features you switch on in `site.json`

Run `py build.py` after any change below, then publish.

- **Release countdown + pre-save**: fill `upcoming` (`title`, `release` as an ISO
  date with time zone, optional `cover`, `presave`, `listen`) and set
  `"enabled": true`. Before the date it shows a live countdown and the pre-save
  button; after it, "Out now" with the listen link (falls back to `presave`).
- **Visitor stats**: create a free site at goatcounter.com and put its code (the
  part before `.goatcounter.com`) in `analytics.goatcounter`. Every link already
  reports which one was clicked.
- **Contact form**: create a free form at formspree.io and put its ID (the part
  after `/f/`) in `contact.formspree`. Messages arrive in your email; the page
  never shows your address.
- **Projects**: each entry in `projects` (`name`, `url`, `key`, `tags`, `status`: `live`, `dev`
  or `new`, and optional `year` and `image`) appears in the Projects section, with its
  description in every `locales/*.json` as `project.<key>`. `"featured": true` gives it a full
  panel (with `"mark": "mecu"` for the eagle, or its `image`, and `cta` naming the button's
  message key); the others are rows whose image follows the cursor. A `page` block (`slug`,
  `features`, `stack`, `site`) gives a project its own page at `projects/<slug>/`, with
  `project.<key>.role`, `.summary` and `.f0` to `.fN` in the locale files. The section and its
  nav link disappear when the list is empty.
- **About**: the bio lives in the locale files (`about.lead`, `about.body`, and
  `about.role.0`–`2` with `about.role.N.body` for the "What I do" columns), so edit it in
  every language you care about. The Instagram part comes from `data/instagram/`.
- **More from ECU**: the Discord tile appears once its URL is filled in (use an
  invite that never expires).

Always on: song sharing (each song gets a preview page in `s/<song>/`, and
`?song=<slug>` opens the page with that song ready), a full-screen visualizer,
a QR code for `site_url` (`images/qr.svg`, regenerated when `segno` is
installed), light/dark mode, and the installable app (`manifest.webmanifest`,
`sw.js`).

## Project structure

- `site.json`: profile, links, playlist, and projects.
- `studio.json`: MECU Interactive games and updates.
- `data/instagram/<handle>.json`: posts and highlights of each Instagram account.
- `instagram.py`: the Instagram components and the checks on their data. `ui.py`: small
  HTML pieces shared with `build.py`.
- `templates/index.html`: the personal home page. `templates/page.html`: the shell every
  other page shares (top bar, footer, scripts).
- `assets/css/site.css`: the design system (tokens at the top) and every shared component.
  `assets/css/studio.css` re-tints the tokens for the studio and adds its components.
  `assets/css/instagram.css` styles the highlights rail and post gallery, and
  `assets/css/media.css` the story viewer and lightbox.
- `assets/js/player.js`: playback, timeline, playlist, and discography cards.
- `assets/js/motion.js`: opening, title and scroll reveals, project previews, tilt, and sparks.
- `assets/js/instagram.js`: loading and error states of Instagram tiles, arrow keys on the rail.
- `assets/js/features.js`: countdown, sharing and song links, QR sheet, theme, contact form,
  app install, and the full-screen visualizer.
- `assets/js/nav.js`: top navigation and the full-screen phone menu.
- `assets/js/media.js`: story viewer for highlights, image lightbox, video and trailer player.
- `assets/js/studio.js`: the studio intro film.
- `assets/js/i18n.js`: language selection, browser detection, saved preference, text
  bindings, and localized plural counts.
- `locales/`: AI-translated English, Spanish, Portuguese (Brazil), French, German, Italian,
  and Arabic catalogs. Each page ships only the messages it uses.
- `assets/fonts/`: bundled Sora and Manrope fonts; licenses in `OFL.txt`.
- `audio/`, `media/`: original MP3 files and videos.
- `images/`: profile photo (the page loads the light `profile-320/640` copies; `profile.jpg`
  is the 10 MB original), covers, favicon, share card, brand icons (Simple Icons, CC0),
  `images/instagram/` for post pictures and highlight covers, and `images/mecu/` for the studio.
- `build.py`: standard-library static site generator. `serve.py`: local preview server.
- `manifest.webmanifest`, `sw.js`: installable app and offline shell.
- `tools/`: helper scripts (logo assets, optional Instagram sync).
- `archive/`: earlier versions of the page, kept as backups.

## Publish

GitHub Pages serves the `main` branch as it is, so publishing is: run `py build.py`, commit
the sources and the generated pages together, and push to `main`. When you publish changes to
CSS or JS, raise `CACHE` in `sw.js` (`ecu-links-v9`, and so on) so installed copies refresh.

## Site languages

The language selector changes the complete interface immediately: headings,
tagline, release action, footer, playlist, player states and errors, screen
reader labels, page title, and description. Song titles, artist names, and
platform names retain their official spelling. Arabic switches page direction
to right-to-left; playback controls keep their familiar direction.

On a first visit, the site uses the first supported browser language, falling
back to English. An explicit selection is saved in browser storage and takes
priority on future visits. The site still works if storage is unavailable.

Translations are bundled at build time. Visitors do not make AI requests, and
no API key, backend, third-party translator script, or paid service is needed.
These translations were generated with AI during development, rather than
being generated live for visitors.

To update wording, edit the matching message in each `locales/*.json` file and
run `py build.py`. When changing the tagline or section headings in
`site.json`, update `content.tagline` and `content.group.N` in the catalogs too.
The build preserves custom English wording from `site.json` and checks that
catalog keys and interpolation tokens such as `{name}` match across languages.

To add a language, copy `locales/en.json` to a language-code filename, translate
every message, set its native `name` and `dir` (`ltr` or `rtl`), and rebuild.
The selector includes it automatically. For new interface text, add a message
key to every catalog and use `data-i18n="your.key"` on a text-only element,
or `data-i18n-aria-label="your.key"` for an accessible label. Dynamic player
text uses `SiteI18n.t(key, values)` and updates on `site:languagechange`.

## Browser checks

Install the optional development dependency with `py -m pip install playwright`,
then run `py -m unittest discover -s tests -v`. The suite uses installed Chrome
or Edge (or Playwright Chromium), starts its own temporary preview server, and
checks translations, persistence, player state, seeking, mobile layouts, and the studio,
game and project pages.
Set `BROWSER_EXECUTABLE` if your browser lives at another path. On a machine
without Chrome or Edge, run `py -m playwright install chromium` first.
