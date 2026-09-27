from handler.install.auto_mode import capture
from handler.install.auto_mode.catalog import load_catalog, normalize
from handler.install.auto_mode.driver import (
    STATUS_NEEDS_MANUAL,
    STATUS_RUNNING,
    AutoModeDriver,
)
from handler.install.auto_mode.engine import ScreenMemory, plan_action, same_screen
from handler.install.auto_mode.matcher import Word, find_matches
from handler.install.auto_mode.ocr import parse_tsv, upscale_factor

CATALOG = load_catalog()


def line(text: str, x: int, y: int, line_no: int, word_w: int = 40) -> list[Word]:
    """One OCR line: words laid out left to right, 10px apart."""
    words = []
    for i, t in enumerate(text.split()):
        words.append(
            Word(t, x + i * (word_w + 10), y, word_w, 12, 90.0, (1, 1, line_no))
        )
    return words


def screen(*lines: list[Word]) -> list[Word]:
    return [w for ln in lines for w in ln]


class TestNormalize:
    def test_ignores_case_markers_and_mnemonic(self):
        assert normalize("&Next >") == "next"
        assert normalize("Avanti >") == "avanti"
        assert normalize("次へ(N)") == "次へ"


class TestCatalog:
    def test_extra_entries_are_appended(self):
        catalog = load_catalog(
            [{"category": "next", "labels": ["Advance"], "mnemonic": "p"}]
        )
        words = screen(line("Advance", 300, 400, 1))
        assert [m.entry.category for m in find_matches(words, catalog)] == ["next"]

    def test_invalid_extra_entries_are_ignored(self):
        catalog = load_catalog(
            [{"category": "bogus", "labels": ["x"]}, {"labels": ["y"]}]
        )
        assert len(catalog.buttons) == len(load_catalog().buttons)


class TestMatcher:
    def test_finds_next_button(self):
        matches = find_matches(screen(line("Next >", 300, 400, 1)), CATALOG)
        assert [m.entry.category for m in matches] == ["next"]

    def test_short_label_inside_body_text_is_not_a_button(self):
        body = line("Il programma si installera nella cartella", 20, 50, 1)
        assert find_matches(screen(body), CATALOG) == []

    def test_short_label_standing_alone_on_a_shared_line_matches(self):
        words = [
            Word("Back", 200, 400, 40, 12, 90, (1, 1, 1)),
            Word("Yes", 500, 400, 30, 12, 90, (1, 1, 1)),
        ]
        cats = [m.entry.category for m in find_matches(words, CATALOG)]
        assert cats == ["agree"]

    def test_short_deny_label_sharing_a_line_does_not_hide_neighbours(self):
        words = [
            Word("Back", 200, 400, 40, 12, 90, (1, 1, 1)),
            Word("Next", 300, 400, 40, 12, 90, (1, 1, 1)),
            Word("Cancel", 500, 400, 50, 12, 90, (1, 1, 1)),
        ]
        assert [m.entry.category for m in find_matches(words, CATALOG)] == ["next"]

    def test_deny_listed_line_is_dropped(self):
        assert (
            find_matches(
                screen(line("I do not accept the agreement", 20, 200, 1)), CATALOG
            )
            == []
        )

    def test_toggle_matches_with_stray_glyph_prefix(self):
        words = screen(line("O I accept the agreement", 20, 200, 1))
        (m,) = find_matches(words, CATALOG)
        assert m.entry.toggle

    def test_one_typo_tolerated_on_longer_label(self):
        assert find_matches(screen(line("Instal", 300, 400, 1)), CATALOG)
        assert find_matches(screen(line("Instalar", 300, 400, 1)), CATALOG)

    def test_cjk_split_into_characters(self):
        words = [
            Word("下", 300, 400, 12, 12, 90, (1, 1, 1)),
            Word("一", 312, 400, 12, 12, 90, (1, 1, 1)),
            Word("步", 324, 400, 12, 12, 90, (1, 1, 1)),
        ]
        assert [m.entry.category for m in find_matches(words, CATALOG)] == ["next"]

    def test_low_confidence_words_are_ignored(self):
        words = [Word("Next", 300, 400, 40, 12, 5.0, (1, 1, 1))]
        assert find_matches(words, CATALOG) == []


class TestPlanner:
    def test_license_page_selects_radio_before_next(self):
        words = screen(
            line("License Agreement", 20, 20, 1),
            line("I accept the agreement", 20, 200, 2),
            line("Next >", 400, 400, 3),
        )
        action, _ = plan_action(words, CATALOG, ScreenMemory())
        assert action.match.entry.toggle and action.kind == "click"

    def test_agree_buttons_only_used_on_license_pages(self):
        words = screen(line("Welcome", 20, 20, 1), line("Yes", 500, 400, 2))
        assert plan_action(words, CATALOG, ScreenMemory())[0] is None
        words = screen(line("License Agreement", 20, 20, 1), line("Yes", 500, 400, 2))
        action, _ = plan_action(words, CATALOG, ScreenMemory())
        assert action.match.entry.category == "agree"

    def test_click_then_mnemonic_then_next_candidate(self):
        words = screen(
            line("License Agreement", 20, 20, 1),
            line("Next >", 400, 400, 2),
            line("Yes", 500, 400, 3),
        )
        memory = ScreenMemory()
        kinds = []
        for _ in range(3):
            action, _ = plan_action(words, CATALOG, memory)
            kinds.append((action.match.entry.category, action.kind))
            memory.attempts[action.memory_key] = (
                memory.attempts.get(action.memory_key, 0) + 1
            )
        assert kinds == [("next", "click"), ("next", "key"), ("agree", "click")]

    def test_exhausted_buttons_yield_nothing(self):
        words = screen(line("Next >", 400, 400, 1))
        memory = ScreenMemory(attempts={"next:next": 2})
        assert plan_action(words, CATALOG, memory)[0] is None

    def test_install_beats_next_and_finish_beats_next(self):
        words = screen(line("Install", 400, 400, 1), line("Next", 500, 400, 2))
        action, _ = plan_action(words, CATALOG, ScreenMemory())
        assert action.match.entry.category == "install"

    def test_same_screen_tolerates_small_changes(self):
        a = frozenset({"a", "b", "c", "d", "e"})
        assert same_screen(a, frozenset({"a", "b", "c", "d", "e", "f"}))
        assert not same_screen(a, frozenset({"x", "y", "z"}))


class Harness:
    def __init__(self, screens):
        self.screens = list(screens)
        self.now = 0.0
        self.acted = []
        self.reports = []
        self.driver = AutoModeDriver(
            catalog=CATALOG,
            observe=lambda: (
                self.screens[0] if len(self.screens) == 1 else self.screens.pop(0)
            ),
            act=self.acted.append,
            enabled=lambda: True,
            progress=lambda: 0,
            report=lambda s, d: self.reports.append((s, d)),
            stuck_seconds=30,
            clock=lambda: self.now,
        )


class TestDriver:
    def test_clicks_reports_and_flags_stuck_when_nothing_matches(self):
        h = Harness(
            [
                screen(line("Next >", 400, 400, 1)),
                screen(line("Installing files please wait", 20, 20, 1)),
            ]
        )
        assert h.driver.tick() is True
        assert h.reports[-1][0] == STATUS_RUNNING
        h.now = 10
        assert h.driver.tick() is False
        h.now = 50
        h.driver.tick()
        assert h.reports[-1][0] == STATUS_NEEDS_MANUAL

    def test_recovers_from_needs_manual_when_a_button_appears(self):
        busy = screen(line("Installing files please wait", 20, 20, 1))
        h = Harness([busy, busy, screen(line("Finish", 400, 400, 1))])
        h.driver.tick()
        h.now = 40
        h.driver.tick()
        assert h.reports[-1][0] == STATUS_NEEDS_MANUAL
        h.now = 41
        assert h.driver.tick() is True
        assert h.reports[-1][0] == STATUS_RUNNING

    def test_file_growth_counts_as_progress_not_stuck(self):
        h = Harness([screen(line("Installing files please wait", 20, 20, 1))])
        counter = iter(range(100))
        h.driver.progress = lambda: next(counter)
        for t in (0, 20, 40, 60):
            h.now = t
            h.driver.tick()
        assert all(s != STATUS_NEEDS_MANUAL for s, _ in h.reports)

    def test_disabled_does_nothing(self):
        h = Harness([screen(line("Next", 400, 400, 1))])
        h.driver.enabled = lambda: False
        assert h.driver.tick() is False
        assert h.acted == []

    def test_disabled_next_gets_click_then_key_then_gives_up(self):
        h = Harness([screen(line("Next >", 400, 400, 1))])
        results = []
        for t in range(4):
            h.now = t
            results.append(h.driver.tick())
        assert results == [True, True, False, False]
        assert [a.kind for a in h.acted] == ["click", "key"]


class TestOcrParsing:
    def test_tsv_words_are_scaled_back_to_image_coordinates(self):
        tsv = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
        tsv += (
            f"5\t1\t2\t1\t3\t1\t{100 * 4}\t{50 * 4}\t{40 * 4}\t{12 * 4}\t91.5\tNext\n"
        )
        tsv += "4\t1\t2\t1\t3\t0\t0\t0\t10\t10\t-1\t\n"
        (w,) = parse_tsv(tsv, 4)
        assert (w.text, w.left, w.top, w.width, w.height, w.line_id) == (
            "Next",
            100,
            50,
            40,
            12,
            (2, 1, 3),
        )


def test_small_crops_get_more_magnification_than_full_screens():
    assert upscale_factor(417, 245) == 4
    assert upscale_factor(1024, 768) == 3
    assert upscale_factor(1920, 1080) == 2


class TestOcrNoise:
    def test_eula_checkbox_with_glyph_noise_and_pipe_for_i(self):
        words = [
            Word("|_|Yes,", 294, 468, 40, 12, 90, (1000, 0, 0)),
            Word("|", 338, 470, 4, 12, 90, (1000, 0, 0)),
            Word("have", 343, 469, 28, 12, 90, (1000, 0, 0)),
            Word("read", 375, 469, 26, 12, 90, (1000, 0, 0)),
            Word("and", 404, 469, 22, 12, 90, (1000, 0, 0)),
            Word("accept", 430, 470, 40, 12, 90, (1000, 0, 0)),
            Word("EULA", 473, 469, 30, 12, 90, (1000, 0, 0)),
        ]
        (m,) = find_matches(words, CATALOG)
        assert m.entry.toggle
        assert m.left == 294 and m.left + m.width == 503

    def test_install_read_with_trailing_dot(self):
        words = [Word("install.", 663, 459, 50, 12, 90, (1002, 0, 0))]
        assert [m.entry.category for m in find_matches(words, CATALOG)] == ["install"]


class TestKeyPromptsAndExit:
    def test_press_up_prompt_presses_the_up_key(self):
        words = screen(line("Press up to unlock the screen", 300, 300, 1))
        action, _ = plan_action(words, CATALOG, ScreenMemory())
        assert (action.kind, action.key, action.alt) == ("key", "Up", False)
        assert action.describe() == "key Up on 'Press up to unlock the screen' (key)"

    def test_key_prompt_is_tried_before_buttons(self):
        words = screen(
            line("Press up to unlock the screen", 300, 300, 1),
            line("Next", 400, 400, 2),
        )
        action, _ = plan_action(words, CATALOG, ScreenMemory())
        assert action.key == "Up"

    def test_exit_only_once_the_install_wrote_files(self):
        words = screen(line("Exit", 300, 400, 1))
        assert plan_action(words, CATALOG, ScreenMemory())[0] is None
        action, _ = plan_action(words, CATALOG, ScreenMemory(), installing=True)
        assert action.match.entry.category == "finish"

    def test_driver_treats_file_growth_as_installing(self):
        h = Harness([screen(line("Exit", 300, 400, 1))])
        assert h.driver.tick() is False
        h.driver.progress = lambda: 1000
        assert h.driver.tick() is True


class TestKeyFocus:
    # Real layout of the DODI "press up to unlock" splash under IceWM.
    WINDOWS = {
        "1": ("Frame", "0,63,800,448"),
        "2": ("Container", "0,63,800,448"),
        "3": ("Setup", "400,300,1,1"),
        "4": ("TaskBar", "0,574,800,26"),
        "5": ("WindowList", "100,100,600,300"),
    }

    def fake_xdotool(self, calls):
        def run(display, *args):
            calls.append(args)
            if args[-1] == "^IceStatus$":
                return ""
            if args[:3] == ("search", "--onlyvisible", "--name"):
                return " ".join(self.WINDOWS)
            if args[0] == "getwindowname":
                return self.WINDOWS[args[1]][0]
            if args[0] == "getwindowgeometry":
                x, y, w, h = self.WINDOWS[args[-1]][1].split(",")
                return f"X={x}\nY={y}\nWIDTH={w}\nHEIGHT={h}\n"
            return ""

        return run

    def test_main_window_ignores_tiny_helpers_taskbar_and_window_list(self):
        windows = [
            (wid, name, tuple(int(v) for v in rect.split(",")))
            for wid, (name, rect) in self.WINDOWS.items()
        ]
        assert capture.pick_main_window(windows) == (0, 63, 800, 448)
        assert capture.pick_main_window([("1", "Setup", (0, 0, 1, 1))]) is None

    @staticmethod
    def actions(calls):
        return [
            c
            for c in calls
            if c[0] in ("mousemove", "key") or c[:1] == ("windowfocus",)
        ]

    def test_bare_key_clicks_the_window_center_first(self, monkeypatch):
        calls = []
        monkeypatch.setattr(capture, "_xdotool", self.fake_xdotool(calls))
        monkeypatch.setattr(capture.time, "sleep", lambda s: None)
        capture.press_key(":1", "Up", alt=False)
        assert self.actions(calls) == [
            ("mousemove", "400", "287", "click", "1"),
            ("key", "--clearmodifiers", "Up"),
        ]

    def test_mnemonic_is_sent_without_an_extra_click(self, monkeypatch):
        calls = []
        monkeypatch.setattr(capture, "_xdotool", self.fake_xdotool(calls))
        monkeypatch.setattr(capture.time, "sleep", lambda s: None)
        capture.press_key(":1", "n")
        assert self.actions(calls) == [("key", "--clearmodifiers", "alt+n")]

    def test_a_window_move_left_by_a_stray_click_is_cancelled_first(self, monkeypatch):
        calls = []
        base = self.fake_xdotool(calls)

        def with_move_mode(display, *args):
            if args[0] == "search" and args[-1] == "^IceStatus$":
                calls.append(args)
                return "99" if not any(c[0] == "key" for c in calls) else ""
            return base(display, *args)

        monkeypatch.setattr(capture, "_xdotool", with_move_mode)
        monkeypatch.setattr(capture.time, "sleep", lambda s: None)
        capture.click(":1", 235, 236)
        assert self.actions(calls) == [
            ("key", "Escape"),
            ("mousemove", "235", "236", "click", "1"),
        ]


class TestFalsePositives:
    def test_page_title_is_not_a_button(self):
        title = Word("Install", 236, 89, 93, 46, 90, (1, 1, 1))
        assert find_matches([title], CATALOG) == []

    def test_button_sized_label_still_matches(self):
        button = Word("Install", 715, 470, 40, 14, 90, (1, 1, 1))
        assert [m.entry.category for m in find_matches([button], CATALOG)] == [
            "install"
        ]

    def test_exhausted_button_is_retried_after_a_while(self):
        h = Harness([screen(line("Next >", 400, 400, 1))])
        results = []
        for t in (0, 1, 2, 3, 26, 27, 28):
            h.now = t
            results.append(h.driver.tick())
        assert results == [True, True, False, False, False, True, True]

    def test_checkbox_toggle_is_never_retried_by_the_cooldown(self):
        words = screen(
            line("License Agreement", 20, 20, 1),
            line("I accept the agreement", 20, 200, 2),
        )
        h = Harness([words])
        results = []
        for t in (0, 1, 2, 30, 31):
            h.now = t
            results.append(h.driver.tick())
        assert results.count(True) == 2
