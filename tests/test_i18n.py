"""Browser integration checks: py -m unittest discover -s tests -v.

Install the development dependency with: py -m pip install playwright.
Uses installed Chrome/Edge, or Playwright Chromium if neither is present.
The preview server uses an ephemeral port and closes when the suite finishes.
"""
from functools import partial
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import sys
from threading import Thread
import unittest

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from serve import RangeHandler

LANGUAGES = ("en", "es", "pt", "fr", "de", "it", "ar")


class QuietRangeHandler(RangeHandler):
    def log_message(self, *_args):
        pass

    def copyfile(self, source, outputfile):
        # Navigating/closing a page cancels its speculative MP3 request.
        try:
            super().copyfile(source, outputfile)
        except (ConnectionError, BrokenPipeError):
            pass


class LocalizationBrowserTests(unittest.TestCase):
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
        cls.browser = cls.playwright.chromium.launch(
            executable_path=executable, headless=True
        )

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join()

    def setUp(self):
        self.context = self.browser.new_context(locale="en-US", viewport={"width": 1280, "height": 900})
        self.page = self.context.new_page()
        self.errors = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.goto(self.url)
        self.page.wait_for_function("window.SiteI18n && document.querySelector('#playlist-items').children.length === 4")
        # The player dock glides in once the visitor scrolls past the hero; pointer checks need it settled.
        self.page.wait_for_function("document.documentElement.classList.contains('is-ready')")
        self.page.evaluate("window.scrollTo(0, 400)")
        self.page.wait_for_function("document.documentElement.classList.contains('dock-on')"
                                    " && document.getElementById('player-dock').getAnimations().length === 0")

    def tearDown(self):
        self.context.close()
        self.assertEqual(self.errors, [], "Uncaught browser errors")

    def change(self, language):
        self.page.select_option("#language-select", language)
        self.assertEqual(self.page.locator("html").get_attribute("lang"), language)
        self.assertEqual(self.page.locator("html").get_attribute("dir"), "rtl" if language == "ar" else "ltr")

    def snapshot(self):
        return self.page.evaluate("""() => ({
            text: [...document.querySelectorAll('.eyebrow, .hero-subtitle, .section-heading, .release-kicker, .release-cta, .site-footer, #playlist-heading')].map(e => e.textContent.trim()),
            aria: [...document.querySelectorAll('#music-player, #play-button, #previous-button, #next-button, #seek, #mute-button, #volume, #queue-toggle, #close-queue, #language-select')].map(e => e.getAttribute('aria-label')),
            title: document.title,
            meta: document.querySelector('meta[name="description"]').content,
            urls: [...document.querySelectorAll('a[href]')].map(e => e.href),
            tracks: [...document.querySelectorAll('.queue-title')].map(e => e.textContent),
            artist: document.querySelector('h1').textContent,
            count: document.querySelector('#queue-count').textContent
        })""")

    def test_entire_site_and_accessibility_change_for_every_language(self):
        values = self.page.locator("#language-select option").evaluate_all("options => options.map(o => o.value)")
        self.assertEqual(values, list(LANGUAGES))
        english = self.snapshot()
        self.page.evaluate("window.languageEvents = 0; document.addEventListener('site:languagechange', () => languageEvents++)")
        for language in LANGUAGES[1:]:
            with self.subTest(language=language):
                self.change(language)
                localized = self.snapshot()
                self.assertTrue(all(localized["text"]))
                self.assertTrue(all(localized["aria"]))
                self.assertTrue(all(a != b for a, b in zip(english["text"], localized["text"])))
                self.assertTrue(all(a != b for a, b in zip(english["aria"], localized["aria"])))
                self.assertNotEqual(localized["title"], english["title"])
                self.assertNotEqual(localized["meta"], english["meta"])
                self.assertNotEqual(localized["count"], english["count"])
                for key in ("urls", "tracks", "artist"):
                    self.assertEqual(localized[key], english[key])
                self.assertTrue(self.page.locator("#language-status").text_content())
        self.assertEqual(self.page.evaluate("languageEvents"), 6)
        self.change("es")
        self.assertEqual(self.page.locator("#play-button").get_attribute("aria-label"), "Reproducir música")
        self.assertEqual(self.page.locator("#queue-count").text_content(), "4 canciones")
        self.page.reload()
        self.assertEqual(self.page.locator("html").get_attribute("lang"), "es")
        self.assertEqual(self.page.evaluate("localStorage.getItem('ecu-links-language')"), "es")

    def test_browser_detection_fallback_and_blocked_storage(self):
        for browser_locale, expected in (("es-MX", "es"), ("pt-BR", "pt"), ("ja-JP", "en")):
            with self.subTest(browser_locale=browser_locale):
                context = self.browser.new_context(locale=browser_locale)
                page = context.new_page()
                page.goto(self.url)
                self.assertEqual(page.locator("html").get_attribute("lang"), expected)
                context.close()
        self.page.evaluate("localStorage.setItem('ecu-links-language', 'unsupported')")
        self.page.reload()
        self.assertEqual(self.page.locator("html").get_attribute("lang"), "en")
        self.assertFalse(self.page.evaluate("SiteI18n.setLanguage('unsupported')"))
        self.context.add_init_script("Storage.prototype.getItem = Storage.prototype.setItem = () => { throw new Error('Storage blocked') }")
        self.page.reload()
        self.change("fr")
        self.assertEqual(self.page.locator("#language-select").input_value(), "fr")

    def test_language_switch_preserves_playback_and_seek(self):
        self.page.wait_for_function("document.querySelector('#music-audio').duration > 0 && !document.querySelector('#seek').disabled")
        self.page.evaluate("document.querySelector('#music-audio').muted = true")
        slider = self.page.locator("#seek").bounding_box()
        self.page.mouse.click(slider["x"] + slider["width"] * 0.6, slider["y"] + slider["height"] / 2)
        self.page.wait_for_function("document.querySelector('#music-audio').currentTime > document.querySelector('#music-audio').duration * 0.5")
        self.page.click("#play-button")
        self.page.wait_for_function("!document.querySelector('#music-audio').paused")
        original = self.page.evaluate("({src: document.querySelector('#music-audio').src, time: document.querySelector('#music-audio').currentTime, title: document.querySelector('#track-title').textContent})")
        self.page.click("#queue-toggle")
        for language in LANGUAGES:
            with self.subTest(language=language):
                self.change(language)
                media = self.page.evaluate("({src: document.querySelector('#music-audio').src, time: document.querySelector('#music-audio').currentTime, title: document.querySelector('#track-title').textContent, paused: document.querySelector('#music-audio').paused})")
                self.assertEqual(media["src"], original["src"])
                self.assertEqual(media["title"], original["title"])
                self.assertGreaterEqual(media["time"], original["time"] - 0.25)
                self.assertFalse(media["paused"])
                self.assertEqual(self.page.locator("#queue-toggle").get_attribute("aria-label"), self.page.evaluate("SiteI18n.t('player.closeQueue')"))
                self.assertEqual(self.page.locator("#play-button").get_attribute("aria-label"), self.page.evaluate("SiteI18n.t('player.pause')"))
                self.assertEqual(self.page.locator("#mute-button").get_attribute("aria-label"), self.page.evaluate("SiteI18n.t('player.unmute')"))
                self.assertIn(original["title"], self.page.locator(".queue-item").first.get_attribute("aria-label"))
        self.page.click("#play-button")

    def test_error_empty_and_plural_states(self):
        self.page.evaluate("document.querySelector('#music-audio').dispatchEvent(new Event('error'))")
        english_error = self.page.locator("#player-status").text_content()
        self.change("es")
        self.assertTrue(self.page.locator("#player-status").text_content())
        self.assertNotEqual(self.page.locator("#player-status").text_content(), english_error)
        for size in (0, 1):
            context = self.browser.new_context(locale="en-US")
            page = context.new_page()
            html = (ROOT / "index.html").read_text(encoding="utf-8")
            match = re.search(r'(<script id="track-data"[^>]*>)(.*?)(</script>)', html, re.S)
            data = json.loads(match[2])
            data["tracks"] = data["tracks"][:size]
            html = html[:match.start(2)] + json.dumps(data) + html[match.end(2):]
            page.route(self.url, lambda route: route.fulfill(status=200, content_type="text/html", body=html))
            page.goto(self.url)
            self.assertEqual(page.locator("#queue-count").text_content(), "0 songs" if size == 0 else "1 song")
            if size == 0:
                english_empty = page.locator("#player-status").text_content()
                page.select_option("#language-select", "ar")
                self.assertNotEqual(page.locator("#player-status").text_content(), english_empty)
                self.assertEqual(page.locator("#track-title").text_content(), page.evaluate("SiteI18n.t('player.heading')"))
                for selector in ("#play-button", "#previous-button", "#next-button", "#queue-toggle", "#seek"):
                    self.assertTrue(page.locator(selector).is_disabled())
            else:
                page.select_option("#language-select", "es")
                self.assertEqual(page.locator("#queue-count").text_content(), "1 canción")
            context.close()

    def test_discography_and_listen_button_drive_the_player(self):
        self.page.evaluate("document.querySelector('#music-audio').muted = true")
        cards = self.page.locator("#discography .track-card")
        self.assertEqual(cards.count(), 4)
        cards.nth(2).scroll_into_view_if_needed()
        cards.nth(2).click()
        self.page.wait_for_function("!document.querySelector('#music-audio').paused")
        self.assertEqual(self.page.locator("#track-title").text_content(), cards.nth(2).locator(".track-name").text_content())
        self.assertIn("is-current", cards.nth(2).get_attribute("class"))
        self.assertIn("is-playing", self.page.locator("html").get_attribute("class"))
        cards.nth(2).click()
        self.page.wait_for_function("document.querySelector('#music-audio').paused")
        self.page.evaluate("window.scrollTo(0, 0)")
        self.page.click("#hero-listen")
        self.page.wait_for_function("!document.querySelector('#music-audio').paused")
        self.change("de")
        self.assertIn("Millones", cards.nth(2).get_attribute("aria-label"))
        self.assertEqual(self.page.locator("#hero-listen").text_content().strip(), "Jetzt anhören")
        self.page.click("#play-button")

    def test_sections_reveal_on_scroll_and_without_motion(self):
        self.page.evaluate("document.querySelector('.site-footer-wrap').scrollIntoView()")
        self.page.wait_for_function("[...document.querySelectorAll('[data-reveal]')].every(e => e.classList.contains('is-in'))")
        context = self.browser.new_context(locale="en-US", reduced_motion="reduce")
        page = context.new_page()
        page.goto(self.url)
        page.wait_for_function("document.documentElement.classList.contains('is-ready')")
        hidden = page.evaluate("[...document.querySelectorAll('[data-reveal]')].filter(e => getComputedStyle(e).opacity !== '1').length")
        self.assertEqual(hidden, 0)
        self.assertEqual(page.locator("h1").text_content(), self.page.locator("h1").text_content())
        context.close()

    def test_theme_qr_share_and_song_links(self):
        self.page.click("#theme-toggle")
        self.assertEqual(self.page.locator("html").get_attribute("data-theme"), "light")
        self.page.reload()
        self.assertEqual(self.page.locator("html").get_attribute("data-theme"), "light")
        self.assertEqual(self.page.locator("#theme-toggle").get_attribute("aria-pressed"), "true")
        self.page.click("#theme-toggle")
        self.assertIsNone(self.page.locator("html").get_attribute("data-theme"))

        self.page.click("#qr-open")
        self.assertTrue(self.page.locator("#qr-dialog").evaluate("d => d.open"))
        self.page.keyboard.press("Escape")
        self.assertFalse(self.page.locator("#qr-dialog").evaluate("d => d.open"))

        self.context.grant_permissions(["clipboard-read", "clipboard-write"])
        self.page.locator(".track-item").nth(1).hover()
        self.page.locator(".track-share").nth(1).click()
        self.assertRegex(self.page.evaluate("navigator.clipboard.readText()"), r"/s/my-life/$")
        self.assertEqual(self.page.locator("#toast").text_content(), "Link copied")

        self.page.goto(self.url + "?song=millones-mas")
        self.page.wait_for_function("document.querySelector('#track-title').textContent === 'Millones Más'")
        self.assertTrue(self.page.locator("#music-audio").evaluate("a => a.paused"))
        share_page = (ROOT / "s" / "millones-mas" / "index.html").read_text(encoding="utf-8")
        self.assertIn("og:image", share_page)
        self.assertIn("?song=millones-mas", share_page)

    def test_visualizer_and_more_links(self):
        self.page.evaluate("document.querySelector('#music-audio').volume = 0.01")
        self.page.click("#play-button")
        self.page.wait_for_function("!document.querySelector('#music-audio').paused")
        self.page.click("#viz-open")
        self.assertTrue(self.page.locator("#viz-dialog").evaluate("d => d.open"))
        self.assertEqual(self.page.locator("#viz-title").text_content(), self.page.locator("#track-title").text_content())
        self.page.click('[data-viz="next"]')
        self.page.wait_for_function("document.querySelector('#viz-title').textContent === document.querySelector('#track-title').textContent && document.querySelector('#track-title').textContent === 'My Life'")
        self.page.click('[data-viz="play"]')
        self.page.wait_for_function("document.querySelector('#music-audio').paused")
        self.page.keyboard.press("Escape")
        self.assertFalse(self.page.locator("#viz-dialog").evaluate("d => d.open"))
        more = self.page.locator(".more .link-button")
        self.assertEqual([more.nth(i).text_content().split("Opens")[0].strip() for i in range(more.count())], ["GitHub", "Steam", "Discord · ECULAND"])

    def test_contact_form_reports_success_and_failure(self):
        form = self.page.locator("#contact-form")
        if not form.count():
            self.skipTest("contact form is off in site.json")
        self.assertTrue(form.get_attribute("action").startswith("https://formspree.io/f/"))
        # Formspree is faked here so tests never send real email.
        for status, key in ((200, "contact.sent"), (500, "contact.error")):
            with self.subTest(status=status):
                def reply(route, status=status):
                    route.fulfill(status=status, content_type="application/json", body="{}")
                self.page.route("https://formspree.io/**", lambda route: reply(route))
                form.scroll_into_view_if_needed()
                self.page.fill("#contact-form [name=name]", "Test")
                self.page.fill("#contact-form [name=email]", "test@example.com")
                self.page.fill("#contact-form [name=message]", "Hola")
                self.page.click("#contact-form button[type=submit]")
                expected = self.page.evaluate(f"SiteI18n.t('{key}')")
                self.page.wait_for_function(f"document.querySelector('#contact-status').textContent === {expected!r}")
                self.page.unroute("https://formspree.io/**")
        self.assertEqual(self.page.locator("#contact-form [name=message]").input_value(), "Hola")

    def test_countdown_flips_to_out_now(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        card = ('<section class="link-section glass upcoming" data-reveal data-release="{}">'
                '<div class="countdown" data-when="before"><b data-unit="days">00</b><b data-unit="hours">00</b>'
                '<b data-unit="minutes">00</b><b data-unit="seconds">00</b></div>'
                '<a class="upcoming-action presave" href="#p">p</a><a class="upcoming-action listen" href="#l">l</a></section>')
        for release, out in (("2999-01-01T00:00:00Z", False), ("2001-01-01T00:00:00Z", True)):
            with self.subTest(out=out):
                page = self.context.new_page()
                body = html.replace('<div id="links" class="sections-grid">', '<div id="links" class="sections-grid">' + card.format(release))
                def serve(route, body=body):
                    route.fulfill(status=200, content_type="text/html", body=body)
                page.route(self.url, lambda route: serve(route))
                page.goto(self.url)
                page.wait_for_function("window.ECUPlayer")
                self.assertEqual(page.locator(".upcoming").evaluate("e => e.classList.contains('is-out')"), out)
                if not out:
                    page.wait_for_function("document.querySelector('[data-unit=days]').textContent !== '00'")
                self.assertEqual(page.locator(".upcoming-action.listen").is_visible(), out)
                self.assertEqual(page.locator(".upcoming-action.presave").is_visible(), not out)
                page.close()

    def test_mobile_layout_all_languages_and_local_file(self):
        for width in (300, 320, 375, 768):
            self.page.set_viewport_size({"width": width, "height": 900})
            for language in LANGUAGES:
                with self.subTest(width=width, language=language):
                    self.change(language)
                    self.assertLessEqual(self.page.evaluate("document.documentElement.scrollWidth"), width)
                    for selector in (".language-control", ".site-shell", "#music-player", "#queue-toggle", ".player-controls"):
                        box = self.page.locator(selector).bounding_box()
                        self.assertGreaterEqual(box["x"], -1, selector)
                        self.assertLessEqual(box["x"] + box["width"], width + 1, selector)
        self.page.goto((ROOT / "index.html").as_uri())
        self.change("ar")
        self.assertEqual(self.page.locator("#language-select").input_value(), "ar")
        self.assertRegex(self.page.locator(".hero-subtitle").text_content(), r"[\u0600-\u06ff]")


if __name__ == "__main__":
    unittest.main(verbosity=2)
