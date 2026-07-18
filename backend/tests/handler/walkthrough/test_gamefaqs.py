import pytest

from handler.walkthrough import parse_gamefaqs_guide, validate_gamefaqs_url


def test_parse_extracts_title_author_and_pre_text():
    html = (
        "<html><head>"
        "<title>Chrono Trigger - FAQ/Walkthrough - GameFAQs</title>"
        '<meta name="author" content="John Doe">'
        '<meta property="og:title" content="Chrono Trigger FAQ">'
        "</head><body>"
        '<div id="faqtext"><pre>Line 1\nLine 2 &amp; more</pre></div>'
        "</body></html>"
    )
    guide = parse_gamefaqs_guide(html)
    assert guide["title"] == "Chrono Trigger FAQ"
    assert guide["author"] == "John Doe"
    assert guide["text"] == "Line 1\nLine 2 & more"


def test_parse_falls_back_to_title_tag_and_strips_suffix():
    html = (
        "<html><head><title>Some Guide - GameFAQs</title></head>"
        "<body><pre>body</pre></body></html>"
    )
    guide = parse_gamefaqs_guide(html)
    assert guide["title"] == "Some Guide"
    assert guide["text"] == "body"


def test_parse_no_guide_text_returns_empty():
    guide = parse_gamefaqs_guide("<html><body><p>nothing here</p></body></html>")
    assert guide["text"] == ""


@pytest.mark.parametrize(
    "url",
    [
        "http://gamefaqs.gamespot.com/x",  # not https
        "https://evil.example.com/x",  # wrong host
        "ftp://gamefaqs.com/x",  # wrong scheme
        "https://notgamefaqs.com/x",  # lookalike host
    ],
)
def test_validate_rejects_bad_urls(url):
    with pytest.raises(ValueError):
        validate_gamefaqs_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://gamefaqs.gamespot.com/snes/563538-chrono-trigger/faqs/1",
        "https://www.gamefaqs.com/snes/563538/faqs/1",
        "https://gamefaqs.com/snes/563538/faqs/1",
    ],
)
def test_validate_accepts_gamefaqs_urls(url):
    assert validate_gamefaqs_url(url) == url
