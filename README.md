# ECU Music & Links

A static artist page with a playlist, audio player, discography, and social links,
in the ECUSYSTEM style: dark glass, gold/blue/red accents, and Apple-style motion
(intro with the ECU blades, staged reveals, 3D release card, magnetic button,
cursor light, conic borders, and spark bursts on links). Every animation turns
off for visitors who ask for reduced motion.

## Edit and preview

1. Edit `site.json` for your name, tagline, links, and playlist.
2. Run `py build.py` to regenerate `index.html`.
3. Run `py serve.py`, then open http://localhost:8000.

The preview server supports HTTP byte ranges so songs can seek correctly.

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
- **More from ECU**: the Discord tile appears once its URL is filled in (use an
  invite that never expires).

Always on: song sharing (each song gets a preview page in `s/<song>/`, and
`?song=<slug>` opens the page with that song ready), a full-screen visualizer,
a QR code for `site_url` (`images/qr.svg`, regenerated when `segno` is
installed), light/dark mode, and the installable app (`manifest.webmanifest`,
`sw.js`). When you publish changes to CSS or JS, raise `CACHE` in `sw.js`
(`ecu-links-v3`, …) so installed copies refresh.

## Project structure

- `site.json`: profile and playlist configuration.
- `templates/index.html`: page markup and build placeholders.
- `assets/css/site.css`: active page styles.
- `assets/js/player.js`: playback, timeline, playlist, discography cards, and visualizer.
- `assets/js/motion.js`: intro, reveals, parallax, tilt, magnetic button, and sparks.
- `assets/js/features.js`: countdown, sharing and song links, QR sheet, theme,
  contact form, app install, and the full-screen visualizer.
- `s/`: generated share pages, one per song.
- `manifest.webmanifest`, `sw.js`: installable app and offline shell.
- `assets/js/i18n.js`: language selection, browser detection, saved preference,
  text bindings, and localized plural counts.
- `locales/`: AI-translated English, Spanish, Portuguese (Brazil), French,
  German, Italian, and Arabic catalogs.
- `assets/fonts/`: bundled Sora and Manrope fonts; licenses in `OFL.txt`.
- `audio/`: original MP3 files.
- `images/`: profile photo (the page loads the light `profile-320/640` copies;
  `profile.jpg` is the 10 MB original), covers, favicon, share card, and brand
  icons (Simple Icons, CC0). The build inlines the icons so they can glow in each
  platform's color (set in `BRAND` inside `build.py`).
- `build.py`: standard-library static page generator.
- `serve.py`: local preview server with audio range support.
- `index.html`: generated deployment entry point.
- `archive/style.css`: older unused stylesheet, kept for reference.
- `archive/v1/`: the previous (purple) version of the page, kept as a backup.

## Publish

Deploy `index.html`, `assets/`, `audio/`, `images/`, and `.nojekyll` together.
GitHub Pages can serve these static files directly. Rebuild after changing
configuration or template markup; CSS and JavaScript edits are loaded directly.

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
checks translations, persistence, player state, seeking, and mobile layouts.
Set `BROWSER_EXECUTABLE` if your browser lives at another path. On a machine
without Chrome or Edge, run `py -m playwright install chromium` first.
