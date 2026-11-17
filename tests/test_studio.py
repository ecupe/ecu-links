"""Checks for the redesigned pages (personal home, MECU Interactive studio, game page) and the Instagram system.

Run with: py -m unittest discover -s tests -v   (needs playwright, see test_i18n.py).
"""
from functools import partial
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from threading import Thread
import unittest

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from serve import RangeHandler
import instagram
from test_i18n import LANGUAGES, QuietRangeHandler

HOME = ""
STUDIO = "mecu-interactive/"
GAME = "mecu-interactive/games/wanderbud/"
PAGES = (HOME, STUDIO, GAME)
WIDTHS = (300, 320, 375, 768, 1280)
REEL = "https://www.instagram.com/reel/Dfty3cTs7NK/"


class StudioBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), partial(QuietRangeHandler, directory=str(ROOT))
        )
        cls.server_thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}/"
        cls.playwright = sync_playwright().start()
        candidates = [
            os.environ.get("BROWSER_EXECUTABLE", ""),
            "C:/Program Files/Google/Chrome/Application/chrome.exe",
            "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
        ]
        executable = next((p for p in candidates if p and Path(p).is_file()), None)
        cls.browser = cls.playwright.chromium.launch(executable_path=executable, headless=True)
        # Same trick as test_i18n: contexts start past both intros; raw_context does not.
        cls.raw_context = cls.browser.new_context

        def past_intro(**options):
            context = cls.raw_context(**options)
            context.add_init_script("try { sessionStorage.setItem('ecu-intro', '1');"
                                    " sessionStorage.setItem('mecu-intro', '1') } catch (e) {}")
            return context
        cls.browser.new_context = past_intro

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join()

    def setUp(self):
        self.contexts = []

    def tearDown(self):
        for context in self.contexts:
            context.unroute_all(behavior="ignoreErrors")
            context.close()

    def make_context(self, raw=False, **options):
        options.setdefault("locale", "en-US")
        options.setdefault("viewport", {"width": 1280, "height": 900})
        context = (self.raw_context if raw else self.browser.new_context)(**options)
        self.contexts.append(context)
        return context

    def open(self, path, context=None, **options):
        """Open a page and wait until motion.js is running. Returns (page, errors)."""
        page = (context or self.make_context(**options)).new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(f"pageerror: {error}"))
        page.on("console", lambda m: errors.append(f"console: {m.text}") if m.type == "error" else None)
        page.on("response", lambda r: errors.append(f"{r.status} {r.url}")
                if r.status >= 400 and r.url.startswith(self.url) else None)
        page.on("requestfailed", lambda r: errors.append(f"failed {r.url}")
                if r.url.startswith(self.url) and "ERR_ABORTED" not in (r.failure or "") else None)
        page.goto(self.url + path)
        page.wait_for_function("document.documentElement.classList.contains('is-ready') && window.SiteI18n")
        return page, errors

    # a. clean loads -------------------------------------------------------
    def test_pages_load_without_errors(self):
        for path in PAGES:
            with self.subTest(page=path or "home"):
                page, errors = self.open(path)
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(300)
                self.assertEqual(errors, [])

    # b. links ---------------------------------------------------------------
    def test_internal_links_resolve_and_hashes_have_targets(self):
        for path in PAGES:
            with self.subTest(page=path or "home"):
                context = self.make_context()
                page, _ = self.open(path, context)
                links = page.evaluate("""() => [...document.querySelectorAll('a[href]')].map(a => ({
                    raw: a.getAttribute('href'), href: a.href, target: a.target,
                    rel: a.rel, text: a.textContent.trim().slice(0, 30)}))""")
                self.assertTrue(links)
                for link in links:
                    raw = link["raw"]
                    if raw.startswith(("mailto:", "tel:")):
                        continue
                    if raw.startswith("#"):
                        if raw not in ("#", "#top"):
                            self.assertTrue(page.evaluate("id => !!document.getElementById(id)", raw[1:]),
                                            f"no element for {raw}")
                        continue
                    if not link["href"].startswith(self.url):
                        if link["target"] == "_blank":
                            self.assertIn("noopener", link["rel"], link["href"])
                        continue
                    target = link["href"].split("#")[0]
                    status = context.request.get(target).status
                    self.assertEqual(status, 200, f"{raw} -> {status}")
                    if "#" in link["href"]:
                        # Hash links to other pages must point at an element that exists there.
                        fragment = link["href"].split("#", 1)[1]
                        if fragment and fragment != "top":
                            html = context.request.get(target).text()
                            self.assertIn(f'id="{fragment}"', html, f"{raw} has no target")

    # c. languages -------------------------------------------------------------
    def check_language(self, page, language):
        page.select_option("#language-select", language)
        html = page.locator("html")
        self.assertEqual(html.get_attribute("lang"), language)
        self.assertEqual(html.get_attribute("dir"), "rtl" if language == "ar" else "ltr")
        raw_keys = page.evaluate("""() => [...document.querySelectorAll('[data-i18n]')]
            .filter(e => e.textContent.trim() === e.dataset.i18n).map(e => e.dataset.i18n)""")
        self.assertEqual(raw_keys, [])

    def test_all_languages_on_studio_and_game_pages(self):
        checks = {
            STUDIO: (("#games-heading", "studio.games.heading"), ("#about-heading", "studio.about.heading"),
                     ("#updates-heading", "studio.updates.heading"), ("#instagram-heading", "studio.ig.heading")),
            GAME: (("#game-about", "studio.game.about"), ("#gallery-heading", "studio.game.gallery"),
                   (".back-link span", "studio.game.back")),
        }
        for path, pairs in checks.items():
            page, _ = self.open(path)
            for language in LANGUAGES:
                with self.subTest(page=path, language=language):
                    self.check_language(page, language)
                    for selector, key in pairs:
                        self.assertEqual(page.locator(selector).first.text_content().strip(),
                                         page.evaluate("key => SiteI18n.t(key)", key), selector)
                    self.assertEqual(page.title(), page.evaluate("document.title"))
                    self.assertTrue(page.title().strip())
                    if language != "en":
                        self.assertNotEqual(page.locator(pairs[0][0]).text_content(),
                                            self.english(path, pairs[0][0]))
                    self.assertEqual(page.locator("h1").text_content().strip(),
                                     "MECU Interactive" if path == STUDIO else "Wanderbud")

    def english(self, path, selector):
        if not hasattr(self, "_english"):
            self._english = {}
        key = (path, selector)
        if key not in self._english:
            page, _ = self.open(path)
            self._english[key] = page.locator(selector).first.text_content()
        return self._english[key]

    def test_no_horizontal_overflow_in_every_language_and_width(self):
        for path in (HOME, STUDIO, GAME):
            page, _ = self.open(path)
            for language in LANGUAGES:
                page.select_option("#language-select", language)
                for width in WIDTHS:
                    with self.subTest(page=path, language=language, width=width):
                        page.set_viewport_size({"width": width, "height": 800})
                        page.wait_for_timeout(60)
                        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), width)

    # d. intro film --------------------------------------------------------------
    def intro_page(self, path=STUDIO, **options):
        context = self.make_context(raw=True, **options)
        # Stall the film so a codec-less browser cannot fire "error" and end the intro early.
        context.route("**/*.mp4", lambda route: None)
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(self.url + path)
        return page, errors

    def test_intro_film_plays_once_and_can_be_skipped(self):
        for how in ("skip", "escape"):
            with self.subTest(how=how):
                page, errors = self.intro_page()
                page.wait_for_selector("#studio-intro", state="visible")
                self.assertTrue(page.evaluate("document.documentElement.classList.contains('intro-pending')"))
                if how == "skip":
                    page.click("#studio-intro-skip")
                else:
                    page.keyboard.press("Escape")
                page.wait_for_selector("#studio-intro", state="hidden")
                self.assertFalse(page.evaluate("document.documentElement.classList.contains('intro-pending')"))
                self.assertEqual(page.evaluate("sessionStorage.getItem('mecu-intro')"), "1")
                self.assertTrue(page.locator(".s-hero h1").is_visible())
                page.reload()
                page.wait_for_function("document.documentElement.classList.contains('is-ready')")
                self.assertFalse(page.locator("#studio-intro").is_visible())
                self.assertFalse(page.evaluate("document.documentElement.classList.contains('intro-pending')"))
                self.assertEqual(errors, [])

    def test_intro_film_skipped_for_reduced_motion_and_hash_links(self):
        for name, path, options in (("reduced motion", STUDIO, {"reduced_motion": "reduce"}),
                                    ("hash", STUDIO + "#games", {})):
            with self.subTest(case=name):
                page, _ = self.intro_page(path, **options)
                page.wait_for_function("document.documentElement.classList.contains('is-ready')")
                page.wait_for_timeout(400)
                self.assertFalse(page.locator("#studio-intro").is_visible())
                self.assertFalse(page.evaluate("document.documentElement.classList.contains('intro-pending')"))

    # e/f. story viewer and lightbox ---------------------------------------------
    def test_story_viewer(self):
        page, errors = self.open(STUDIO)
        buttons = page.locator(".hl[data-highlight]")
        self.assertEqual(buttons.count(), 2)
        first = buttons.first
        first.scroll_into_view_if_needed()
        first.click()
        dialog = page.locator("dialog.story[open]")
        dialog.wait_for()
        self.assertGreaterEqual(page.locator("dialog.story .story__bars").first.evaluate("e => e.children.length"), 1)
        title = page.locator(".story__title").text_content()
        page.keyboard.press("ArrowRight")
        page.wait_for_function("t => document.querySelector('.story__title').textContent !== t", arg=title)
        page.keyboard.press("ArrowRight")  # second slide of the second highlight
        self.assertEqual(page.locator("dialog.story .story__bars").evaluate("e => e.children.length"), 2)
        page.keyboard.press("ArrowLeft")
        page.keyboard.press("ArrowLeft")
        page.wait_for_function("t => document.querySelector('.story__title').textContent === t", arg=title)
        page.keyboard.press("Escape")
        page.wait_for_selector("dialog.story[open]", state="detached")
        # The dialog's close event runs cleanup a tick after [open] goes away.
        page.wait_for_function("document.activeElement && document.activeElement.matches('.hl[data-highlight]')")
        self.assertTrue(first.evaluate("e => e === document.activeElement"))
        # Nothing keeps playing behind the closed viewer.
        page.wait_for_function("""() => [...document.querySelectorAll('dialog.story video')]
            .every(v => v.paused || !v.getAttribute('src'))""")
        self.assertTrue(page.evaluate("""() => [...document.querySelectorAll('dialog.story video')]
            .every(v => v.paused || !v.getAttribute('src'))"""))
        self.assertFalse(page.evaluate("document.documentElement.classList.contains('media-open')"))
        self.assertEqual(errors, [])

    def test_story_viewer_via_api_and_close_button(self):
        page, _ = self.open(STUDIO)
        self.assertTrue(page.evaluate("window.SiteMedia.openHighlight(1)"))
        page.wait_for_selector("dialog.story[open]")
        page.click(".story__close")
        page.wait_for_selector("dialog.story[open]", state="detached")

    def test_lightbox_from_update_video(self):
        page, errors = self.open(STUDIO)
        button = page.locator(".update [data-video]")
        button.scroll_into_view_if_needed()
        button.click()
        page.wait_for_selector("dialog.lightbox[open]")
        self.assertEqual(page.locator("dialog.lightbox video").count(), 1)
        page.keyboard.press("Escape")
        page.wait_for_selector("dialog.lightbox[open]", state="detached")
        page.wait_for_function("document.querySelectorAll('dialog.lightbox video').length === 0")
        self.assertEqual(page.locator("dialog.lightbox video").count(), 0)
        self.assertTrue(button.evaluate("e => e === document.activeElement"))
        self.assertEqual(errors, [])

    def test_studio_home_content_and_links(self):
        page, _ = self.open(STUDIO)
        self.assertEqual(page.locator(".s-hero h1").text_content().strip(), "MECU Interactive")
        hrefs = page.locator("#main-nav .nav-link").evaluate_all("l => l.map(a => a.getAttribute('href'))")
        for anchor in ("#games", "#about", "#updates", "#instagram"):
            self.assertIn(anchor, hrefs)
        self.assertEqual(page.locator(".game-card").first.get_attribute("href"), "games/wanderbud/")
        self.assertGreaterEqual(page.locator(".update").count(), 1)
        self.assertEqual(page.locator(".update [data-video]").count(), 1)
        self.assertEqual(page.locator(".update a[href*='instagram.com']").count(), 1)
        posts = page.locator(".ig-post")
        self.assertGreaterEqual(posts.count(), 1)
        self.assertEqual(posts.first.get_attribute("href"), REEL)
        self.assertEqual(posts.first.get_attribute("target"), "_blank")
        self.assertIn("noopener", posts.first.get_attribute("rel"))
        self.assertEqual(page.locator("a.footer-link", has_text="Mateo Amendano").evaluate("a => a.href"), self.url)
        self.assertEqual(page.locator("a.footer-link", has_text="Mateo Amendano").get_attribute("href"), "../")

    def test_game_page(self):
        page, _ = self.open(GAME)
        self.assertEqual(page.locator("h1").text_content().strip(), "Wanderbud")
        self.assertTrue(page.locator(".status").first.is_visible())
        self.assertEqual(page.locator(".back-link").evaluate("a => a.href"), self.url + STUDIO + "#games")
        for anchor in ("games", "about", "updates", "instagram"):
            self.assertIn(self.url + STUDIO + "#" + anchor,
                          page.locator("#main-nav .nav-link").evaluate_all("l => l.map(a => a.href)"))
        self.assertTrue(page.locator(".empty-note").is_visible())
        self.assertEqual(page.locator("a.footer-link", has_text="Mateo Amendano").evaluate("a => a.href"), self.url)
        self.assertEqual(page.locator("a.brand, .brand").first.evaluate("a => a.href"), self.url + STUDIO)

    def test_personal_home_projects_about_nav_and_sitemap(self):
        page, _ = self.open(HOME)
        self.assertEqual(page.locator(".project-row").count(), 0)
        link = page.locator("#projects .feature-list .teaser a.teaser-link")
        self.assertEqual(link.count(), 1)
        self.assertEqual(link.get_attribute("href"), "mecu-interactive/")
        self.assertEqual(page.locator(".teaser-link").count(), 1)
        identity = page.locator("#about .identity > li")
        self.assertEqual(identity.count(), 3)
        for i in range(3):
            self.assertEqual(identity.nth(i).locator("h3").count(), 1)
            self.assertEqual(identity.nth(i).locator("p").count(), 1)
        out = page.locator("#main-nav .nav-out")
        self.assertGreaterEqual(out.count(), 1)
        for y in range(0, page.evaluate("document.body.scrollHeight"), 500):
            page.evaluate("y => window.scrollTo(0, y)", y)
            page.wait_for_timeout(80)
            self.assertEqual(out.evaluate_all("l => l.map(a => a.getAttribute('aria-current'))"),
                             [None] * out.count())
        sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r"<loc>", sitemap)), 3)

    def test_personal_instagram_markup(self):
        page, _ = self.open(HOME)
        self.assertEqual(page.locator("#about #instagram.ig").count(), 1)
        self.assertEqual(page.locator("#instagram .ig-head h3").text_content().strip(), "Instagram")
        profile = page.locator("#instagram .ig-profile")
        self.assertEqual(profile.get_attribute("href"), "https://www.instagram.com/mateoamendano/")
        self.assertEqual(page.locator("#instagram .ig-head a.btn").get_attribute("href"),
                         "https://www.instagram.com/mateoamendano/")
        highlights = page.locator("#instagram .hl-rail a.hl")
        self.assertEqual(highlights.count(), 10)
        for i in range(10):
            item = highlights.nth(i)
            self.assertRegex(item.get_attribute("href"), r"^https://www\.instagram\.com/stories/highlights/\d+/$")
            self.assertEqual(item.get_attribute("target"), "_blank")
            self.assertIn("noopener", item.get_attribute("rel"))
        posts = page.locator("#instagram .ig-grid a.ig-post")
        self.assertEqual(posts.evaluate_all("l => l.map(a => a.getAttribute('href'))"),
                         ["https://www.instagram.com/p/DfyYojHjnRH/", "https://www.instagram.com/p/DfBrbNzjmMt/"])
        for i in range(2):
            self.assertEqual(posts.nth(i).get_attribute("data-type"), "carousel")
            self.assertEqual(posts.nth(i).locator(".ig-badge").count(), 1)
            self.assertEqual(posts.nth(i).locator("img").get_attribute("loading"), "lazy")
        self.assertEqual(page.locator("#instagram .ig-grid .ig-more").count(), 1)
        # No highlight on the home has slides, so it must not carry the story viewer.
        self.assertEqual(page.locator("#instagram-data").count(), 0)
        self.assertEqual(page.locator("script[src*='media.js'], link[href*='media.css']").count(), 0)
        self.assertEqual(page.evaluate("typeof window.SiteMedia"), "undefined")

    def test_studio_instagram_markup(self):
        page, _ = self.open(STUDIO)
        self.assertEqual(page.locator("script#instagram-data").count(), 1)
        self.assertEqual(page.locator("#studio-data").count(), 0)
        self.assertEqual(page.locator("#instagram button.hl[data-highlight]").count(), 2)
        self.assertEqual(page.locator("#instagram a.ig-post[data-type='reel']").count(), 1)
        self.assertEqual(page.locator("#instagram .hl .hl-title").all_text_contents(), ["Intro", "Brand"])

    # Brand-name hygiene ---------------------------------------------------------------
    def test_retired_names_are_gone_everywhere(self):
        files = [ROOT / "index.html", ROOT / "mecu-interactive" / "index.html",
                 ROOT / "mecu-interactive" / "games" / "wanderbud" / "index.html",
                 ROOT / "sitemap.xml", ROOT / "site.json", ROOT / "studio.json"]
        files += sorted((ROOT / "locales").glob("*.json")) + sorted((ROOT / "data").rglob("*.json"))
        for file in files:
            with self.subTest(file=file.relative_to(ROOT).as_posix()):
                self.assertTrue(file.is_file())
                self.assertNotIn("ecu" + "system", file.read_text(encoding="utf-8-sig").lower())
        for path in PAGES:
            with self.subTest(page=path or "home", text="ECU Links"):
                page, _ = self.open(path)
                self.assertNotIn("ECU Links", page.evaluate("document.title + ' ' + document.body.innerText"))
        self.assertFalse((ROOT / "projects").exists())

    # d. Instagram components in the browser -----------------------------------------------
    def settle_instagram(self, page):
        for item in page.locator("#instagram .ig-post, #instagram .hl").all():
            item.scroll_into_view_if_needed()
        page.wait_for_function("""() => [...document.querySelectorAll('#instagram .ig-post, #instagram .hl')]
            .every(e => e.classList.contains('is-loaded'))""", timeout=10000)

    def test_instagram_images_load_and_fit_at_desktop_and_mobile(self):
        for width in (1280, 375):
            with self.subTest(width=width):
                page, errors = self.open(HOME, viewport={"width": width, "height": 900})
                page.locator("#instagram").scroll_into_view_if_needed()
                self.settle_instagram(page)
                self.assertEqual(page.evaluate("""() => [...document.querySelectorAll('#instagram img')]
                    .filter(i => !i.naturalWidth).map(i => i.src)"""), [])
                self.assertEqual(page.locator("#instagram .is-error").count(), 0)
                self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), width)
                self.assertEqual(errors, [])

    def test_instagram_accessible_names(self):
        for path in (HOME, STUDIO):
            with self.subTest(page=path or "home"):
                page, _ = self.open(path)
                names = page.evaluate("""() => [...document.querySelectorAll('#instagram .ig-post, #instagram .hl')]
                    .map(e => (e.getAttribute('aria-label') || e.textContent).trim())""")
                self.assertGreaterEqual(len(names), 3)
                self.assertTrue(all(names), names)

    def test_highlight_rail_keyboard_navigation(self):
        page, _ = self.open(HOME)
        rail = page.locator("#instagram .hl-rail .hl")
        count = rail.count()
        active = "(i) => document.activeElement === document.querySelectorAll('#instagram .hl-rail .hl')[i]"
        rail.first.scroll_into_view_if_needed()
        rail.first.focus()
        page.keyboard.press("ArrowRight")
        self.assertTrue(page.evaluate(active, 1))
        page.keyboard.press("End")
        self.assertTrue(page.evaluate(active, count - 1))
        page.keyboard.press("Home")
        self.assertTrue(page.evaluate(active, 0))
        # Right-to-left: the arrows swap.
        page.select_option("#language-select", "ar")
        rail.first.focus()
        page.keyboard.press("ArrowLeft")
        self.assertTrue(page.evaluate(active, 1))
        page.keyboard.press("ArrowRight")
        self.assertTrue(page.evaluate(active, 0))

    def test_failed_post_image_gets_error_state_but_link_still_works(self):
        context = self.make_context()
        context.route("**/DfyYojHjnRH.jpg", lambda route: route.abort())
        page = context.new_page()
        page.goto(self.url)
        page.wait_for_function("document.documentElement.classList.contains('is-ready')")
        post = page.locator("#instagram a.ig-post").first
        post.scroll_into_view_if_needed()
        page.wait_for_function("document.querySelector('#instagram a.ig-post').classList.contains('is-error')")
        self.assertEqual(post.get_attribute("href"), "https://www.instagram.com/p/DfyYojHjnRH/")
        self.assertTrue(post.locator(".ig-text").is_visible())
        self.assertFalse(post.evaluate("e => e.classList.contains('is-loaded')"))
        # The neighbouring card is unaffected.
        page.locator("#instagram a.ig-post").nth(1).scroll_into_view_if_needed()
        page.wait_for_function("document.querySelectorAll('#instagram a.ig-post')[1].classList.contains('is-loaded')")

    # e. every language on the personal home --------------------------------------------------
    def test_all_languages_on_personal_home(self):
        page, _ = self.open(HOME)
        for language in LANGUAGES:
            with self.subTest(language=language):
                self.check_language(page, language)
                for width in WIDTHS:
                    page.set_viewport_size({"width": width, "height": 800})
                    page.wait_for_timeout(60)
                    self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), width, width)
                page.set_viewport_size({"width": 1280, "height": 900})

    # g. persistence across the two sites ----------------------------------------
    def test_theme_and_language_persist_between_home_and_studio(self):
        context = self.make_context()
        page, _ = self.open(HOME, context)
        page.select_option("#language-select", "es")
        page.click("#theme-toggle")
        self.assertEqual(page.locator("html").get_attribute("data-theme"), "light")
        self.assertEqual(page.evaluate("localStorage.getItem('ecu-theme')"), "light")
        self.assertEqual(page.evaluate("localStorage.getItem('ecu-links-language')"), "es")
        page.goto(self.url + STUDIO)
        page.wait_for_function("document.documentElement.classList.contains('is-ready')")
        self.assertEqual(page.locator("html").get_attribute("lang"), "es")
        self.assertEqual(page.locator("html").get_attribute("data-theme"), "light")
        self.assertEqual(page.locator("#games-heading").text_content(), page.evaluate("SiteI18n.t('studio.games.heading')"))
        page.select_option("#language-select", "fr")
        page.click("#theme-toggle")
        self.assertNotEqual(page.locator("html").get_attribute("data-theme"), "light")
        page.goto(self.url)
        page.wait_for_function("document.documentElement.classList.contains('is-ready')")
        self.assertEqual(page.locator("html").get_attribute("lang"), "fr")
        self.assertNotEqual(page.locator("html").get_attribute("data-theme"), "light")

    # h. reveal -------------------------------------------------------------------
    def test_reveal_with_and_without_reduced_motion(self):
        for path in PAGES:
            with self.subTest(page=path or "home", motion="reduce"):
                page, _ = self.open(path, reduced_motion="reduce")
                opacities = page.evaluate("""() => [...document.querySelectorAll('[data-reveal]')]
                    .map(e => getComputedStyle(e).opacity)""")
                self.assertTrue(opacities)
                self.assertEqual(set(opacities), {"1"})
            with self.subTest(page=path or "home", motion="full"):
                page, _ = self.open(path)
                for _ in range(40):
                    page.mouse.wheel(0, 700)
                    page.wait_for_timeout(60)
                page.wait_for_function("""() => [...document.querySelectorAll('[data-reveal]')]
                    .every(e => e.classList.contains('is-in'))""", timeout=8000)

    # i. mobile nav -----------------------------------------------------------------
    def test_mobile_navigation_on_studio_home(self):
        page, _ = self.open(STUDIO, viewport={"width": 375, "height": 800})
        toggle = page.locator("#nav-toggle")
        self.assertEqual(toggle.get_attribute("aria-expanded"), "false")
        toggle.click()
        self.assertEqual(toggle.get_attribute("aria-expanded"), "true")
        page.wait_for_timeout(500)
        links = page.locator("#main-nav .nav-link")
        for i in range(links.count()):
            box = links.nth(i).bounding_box()
            self.assertTrue(links.nth(i).is_visible())
            self.assertGreaterEqual(box["x"], 0)
            self.assertLessEqual(box["x"] + box["width"], 375)
        page.locator("#main-nav .nav-link[href='#about']").click()
        self.assertEqual(toggle.get_attribute("aria-expanded"), "false")
        toggle.click()
        self.assertEqual(toggle.get_attribute("aria-expanded"), "true")
        page.keyboard.press("Escape")
        self.assertEqual(toggle.get_attribute("aria-expanded"), "false")

    # j. accessibility basics ----------------------------------------------------------
    def test_accessibility_basics(self):
        for path in PAGES:
            with self.subTest(page=path or "home"):
                page, _ = self.open(path)
                self.assertEqual(page.locator("h1").count(), 1)
                self.assertEqual(page.evaluate("[...document.images].filter(i => !i.hasAttribute('alt')).map(i => i.src)"), [])
                unnamed = page.evaluate("""() => [...document.querySelectorAll('button, a[href], select, input:not([type=hidden]):not([aria-hidden=true])')]
                    .filter(e => !(e.textContent.trim() || e.getAttribute('aria-label') || e.getAttribute('title')
                        || e.getAttribute('aria-labelledby') || [...e.labels || []].length))
                    .map(e => e.outerHTML.slice(0, 120))""")
                self.assertEqual(unnamed, [])
                duplicates = page.evaluate("""() => { const seen = {}, dup = [];
                    document.querySelectorAll('[id]').forEach(e => { seen[e.id] ? dup.push(e.id) : seen[e.id] = 1 });
                    return dup }""")
                self.assertEqual(duplicates, [])


class InstagramDataTests(unittest.TestCase):
    """instagram.load() and the components, against temporary data files (never the repo's data/)."""
    POST_IMAGE = "images/instagram/mateoamendano/DfyYojHjnRH.jpg"
    COVER = "images/instagram/mateoamendano/highlight-18250790356312765.jpg"
    MESSAGES = {"ig.viewPost": "View post", "ig.more": "More", "ig.highlights": "Highlights",
                "ig.follow": "Follow", "ig.reel": "Reel", "ig.carousel": "Carousel"}

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.original = instagram.DATA
        instagram.DATA = Path(self.temp.name)
        self.addCleanup(setattr, instagram, "DATA", self.original)
        for image in (self.POST_IMAGE, self.COVER):
            self.assertTrue((ROOT / image).is_file(), image)

    def write(self, handle, data):
        text = data if isinstance(data, str) else json.dumps(data)
        (Path(self.temp.name) / f"{handle}.json").write_text(text, encoding="utf-8")

    def post(self, ident, **extra):
        data = {"id": ident, "url": f"https://www.instagram.com/p/{ident}/", "image": self.POST_IMAGE,
                "type": "image", "caption": f"caption {ident}", "date": "2026-01-01"}
        data.update(extra)
        return data

    def highlight(self, ident, **extra):
        data = {"id": ident, "title": f"title {ident}", "cover": self.COVER,
                "url": f"https://www.instagram.com/stories/highlights/{ident}/", "slides": []}
        data.update(extra)
        return data

    def test_load_keeps_only_valid_visible_entries_and_notes_every_problem(self):
        self.write("mix", {
            "posts": [
                self.post("1"),
                self.post("2", url="https://example.com/p/2/"),
                self.post("3", image="http://example.com/a.jpg"),
                self.post("4", image="images/instagram/missing.jpg"),
                self.post("5", type="story"),
                self.post("6", date="15/11/2026"),
                self.post("1"),  # duplicate id
                self.post("7", visible=False),
                self.post("8"),
            ],
            "highlights": [
                self.highlight("11"),
                self.highlight("12", url="", slides=[]),  # nothing to open
                self.highlight("13", url="https://www.instagram.com/stories/x/"),
                self.highlight("14", slides=[{"type": "image", "src": "images/missing.jpg"}]),
                self.highlight("15", visible=False),
                self.highlight("16", slides=[{"type": "image", "src": self.POST_IMAGE}], url=""),
            ],
        })
        account = instagram.load("mix", quiet=True)
        self.assertEqual({p["id"] for p in account["posts"]}, {"1", "8"})
        self.assertEqual({h["id"] for h in account["highlights"]}, {"11", "14", "16"})
        self.assertEqual(len(account["notes"]), 9, account["notes"])  # 6 posts + 2 highlights + 1 slide
        self.assertEqual([h["slides"] for h in account["highlights"] if h["id"] == "14"], [[]])

    def test_load_survives_broken_files(self):
        self.write("badjson", "{ not json")
        self.write("notlist", {"posts": {"a": 1}, "highlights": "nope"})
        self.write("array", "[1, 2]")
        for handle, notes in (("badjson", 1), ("notlist", 2), ("array", 1), ("absent", 1)):
            with self.subTest(handle=handle):
                account = instagram.load(handle, quiet=True)
                self.assertEqual((account["posts"], account["highlights"]), ([], []))
                self.assertEqual(len(account["notes"]), notes, account["notes"])
                self.assertTrue(account["url"].endswith(f"/{handle}/"))

    def test_order_then_newest_date_then_file_order(self):
        posts = [self.post("a", date="2026-01-01"),
                 self.post("b", date="2026-03-01"),
                 self.post("c", date="2026-02-01", order=5),
                 self.post("d", date="2020-01-01", order=2),
                 self.post("e", date="2026-03-01")]
        self.write("order", {"posts": posts})
        ids = lambda: [p["id"] for p in instagram.load("order", quiet=True)["posts"]]
        self.assertEqual(ids(), ["d", "c", "b", "e", "a"])
        posts[3]["visible"] = False
        self.write("order", {"posts": posts})
        self.assertEqual(ids(), ["c", "b", "e", "a"])
        posts[0]["order"] = 1
        self.write("order", {"posts": posts})
        self.assertEqual(ids(), ["a", "c", "b", "e"])

    def test_components_follow_the_data(self):
        posts = [self.post("a", order=2), self.post("b", order=1)]
        self.write("comp", {"posts": posts, "highlights": [self.highlight("11"), self.highlight("12", order=1)]})
        render = lambda: instagram.load("comp", quiet=True)
        hrefs = lambda html: re.findall(r'class="ig-post" href="[^"]*/p/(\w+)/', html)
        self.assertEqual(hrefs(instagram.gallery(render(), "", self.MESSAGES)), ["b", "a"])
        titles = lambda html: re.findall(r'class="hl-title"[^>]*>([^<]*)<', html)
        self.assertEqual(titles(instagram.highlights(render(), "", self.MESSAGES)), ["title 12", "title 11"])
        posts[0]["visible"] = False
        self.write("comp", {"posts": posts, "highlights": [self.highlight("11", visible=False)]})
        self.assertEqual(hrefs(instagram.gallery(render(), "", self.MESSAGES)), ["b"])
        self.assertEqual(instagram.highlights(render(), "", self.MESSAGES), "")

    def test_a_third_post_makes_three_cards(self):
        self.write("three", {"posts": [self.post("a"), self.post("b")]})
        html = instagram.gallery(instagram.load("three", quiet=True), "", self.MESSAGES)
        self.assertEqual(html.count('class="ig-post"'), 2)
        self.write("three", {"posts": [self.post("a"), self.post("b"), self.post("c")]})
        html = instagram.gallery(instagram.load("three", quiet=True), "", self.MESSAGES)
        self.assertEqual(html.count('class="ig-post"'), 3)
        self.assertEqual(html.count("ig-more"), 1)

    def test_text_is_escaped(self):
        nasty = '<script>alert("x")</script> & \'q\''
        self.write("xss", {"posts": [self.post("a", caption=nasty, alt=nasty)],
                           "highlights": [self.highlight("11", title=nasty[:50])]})
        account = instagram.load("xss", quiet=True)
        for html in (instagram.post_card(account["posts"][0], "", self.MESSAGES),
                     instagram.highlight(account["highlights"][0], 0, ""),
                     instagram.gallery(account, "", self.MESSAGES),
                     instagram.highlights(account, "", self.MESSAGES)):
            self.assertNotIn("<script", html)
            self.assertIn("&lt;script&gt;", html)

    def test_repository_data_is_clean(self):
        instagram.DATA = self.original
        for file in sorted(self.original.glob("*.json")):
            with self.subTest(file=file.name):
                self.assertEqual(instagram.load(file.stem, quiet=True)["notes"], [])


if __name__ == "__main__":
    unittest.main()
