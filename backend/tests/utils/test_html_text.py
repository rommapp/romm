import pytest

from utils.html_text import html_to_text


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, ""),
        ("", ""),
        ("  Plain summary.  ", "Plain summary."),
        ("Line one\nLine two", "Line one\nLine two"),
        ("Tom &quot;Big&quot; Jones &amp; co", 'Tom "Big" Jones & co'),
        ("<p>One.</p>\n<p>Two<br/>three</p>", "One.\n\nTwo\nthree"),
        ("<b>Bold</b> and <i>italic</i>", "Bold and italic"),
        ('<a href="https://x">link</a> text', "link text"),
        ("<ul><li>a</li><li>b</li></ul><p>after</p>", "• a\n• b\n\nafter"),
        ("<p>a</p><p></p><p></p><p>b</p>", "a\n\nb"),
        ("<script>alert(1)</script>Safe", "Safe"),
        ("Non&nbsp;breaking", "Non breaking"),
    ],
)
def test_html_to_text(value: str | None, expected: str):
    assert html_to_text(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "Press <Start> to begin",
        "1 < 2 and 3 > 2",
        "Enter <Your Name> here",
        "Ends with <unterminated",
    ],
)
def test_html_to_text_keeps_literal_angle_brackets(value: str):
    assert html_to_text(value) == value
