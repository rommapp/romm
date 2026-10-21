import pytest

from handler.metadata.summary import normalize_summary


@pytest.mark.parametrize(
    ("summary", "expected"),
    [
        (None, ""),
        ("", ""),
        ("   ", "   "),
        (
            " Plain text.\n\n  Keep indentation.\n",
            " Plain text.\n\n  Keep indentation.\n",
        ),
        ("2 < 3 and 5 > 4; x<y", "2 < 3 and 5 > 4; x<y"),
        ("Explore if a<b and c>d.", "Explore if a<b and c>d."),
        (
            "Explore if a<b and c>d. <em>Enjoy!</em>",
            "Explore if a<b and c>d. Enjoy!",
        ),
        (
            "<p>Explore if a<b and c>d.</p>",
            "Explore if a<b and c>d.",
        ),
        (
            "Explore if x<script and y>z. <em>Enjoy!</em>",
            "Explore if x<script and y>z. Enjoy!",
        ),
        ("Press <player> to start", "Press <player> to start"),
        ("<p>First.</p><p>Second.</p>", "First.\nSecond."),
        ("<p>First.</p>\n<p>Second.</p>", "First.\nSecond."),
        ("<p>First.</p>\n  <p>Second.</p>", "First.\nSecond."),
        ("<p>First.</p>  <p>Second.</p>", "First.\nSecond."),
        ("<p>First.</p>\n\t<p>Second.</p>", "First.\nSecond."),
        (
            "<ul>\n  <li>One</li>\n  <li>Two</li>\n</ul>",
            "One\nTwo",
        ),
        ("<p>First.</p>\n\n<p>Second.</p>", "First.\n\nSecond."),
        ("Text\n<p>Second.</p>", "Text\nSecond."),
        ("<div>First<div>Second</div>Third</div>", "First\nSecond\nThird"),
        ("<table><tr><td>One</td><td>Two</td></tr></table>", "One\nTwo"),
        ("<h2>Games</h2><ul><li>One</li><li>Two</li></ul>", "Games\nOne\nTwo"),
        ("One<br>Two<BR/>Three<br />Four", "One\nTwo\nThree\nFour"),
        ("One<br><br>Two", "One\n\nTwo"),
        (
            "A <b>bold <em>game</em></b> and a <a href='url'>link</a>.",
            "A bold game and a link.",
        ),
        ("Sonic &amp; Knuckles &#38; &#x26; friends", "Sonic & Knuckles & & friends"),
        ("&lt;b&gt;literal&lt;/b&gt; &amp;lt;3", "<b>literal</b> &lt;3"),
        ("<p>2 &lt; 3 &amp; 5 &gt; 4</p>", "2 < 3 & 5 > 4"),
        ("<p>First<p>Second <b>unfinished", "First\nSecond unfinished"),
        ("Text with an incomplete <tag", "Text with an incomplete <tag"),
        ("<b>Text</b> with an incomplete <tag", "Text with an incomplete <tag"),
        ("Use <PLAYER> and </PLAYER>", "Use <PLAYER> and </PLAYER>"),
        ("<p>Use <PLAYER> and </PLAYER></p>", "Use <PLAYER> and </PLAYER>"),
        (
            "<p>Use <Player> and </Player  >.</p>",
            "Use <Player> and </Player  >.",
        ),
        ("<p>A <mark>great</mark> game.</p>", "A great game."),
        ("<p>super<wbr>star</p>", "superstar"),
        ("<p><ruby>漢<rt>kan</rt></ruby></p>", "漢kan"),
        ("<p>super<wbr/>star</p>", "superstar"),
        (
            "<p><dfn>Play</dfn> <time datetime='2000'>now</time>.</p>",
            "Play now.",
        ),
        (
            "<section><dialog open>First.</dialog><form>Second.</form></section>",
            "First.\nSecond.",
        ),
        ("<p hidden>Text</p><video controls>Trailer</video>", "Text\nTrailer"),
        ("<p>A <b class='highlight'>great</b> game.</p>", "A great game."),
        ("<p>Use &lt;player&gt;.</p>", "Use <player>."),
        ("<script/>Visible<style/> text", "Visible text"),
        ("<p>Text<!-- hidden --></p>", "Text"),
        (
            "<p>Text</p><script>ignore <b>this</b></script><style>p {color:red}</style>",
            "Text",
        ),
        ("<p></p><br/>", ""),
    ],
)
def test_normalize_summary(summary: str | None, expected: str):
    assert normalize_summary(summary) == expected


@pytest.mark.parametrize("line_ending", ["\n", "\r\n", "\r"])
@pytest.mark.parametrize(
    ("summary", "expected"),
    [
        ("<p>First.</p>\n  <p>Second.</p>", "First.\nSecond."),
        ("First.\n<p>Second.</p>", "First.\nSecond."),
        ("<p>First.</p>\n\n  <p>Second.</p>", "First.\n\nSecond."),
        ("<ul>\n  <li>One</li>\n  <li>Two</li>\n</ul>", "One\nTwo"),
        (
            " Plain text.\n\n  Keep indentation.\n",
            " Plain text.\n\n  Keep indentation.\n",
        ),
    ],
)
def test_normalize_summary_preserves_line_endings(
    summary: str, expected: str, line_ending: str
):
    assert normalize_summary(summary.replace("\n", line_ending)) == expected.replace(
        "\n", line_ending
    )
