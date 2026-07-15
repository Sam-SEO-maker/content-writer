from scripts.utils.gutenberg_formatter import to_gutenberg


def test_paragraph():
    out = to_gutenberg("<p>Hello</p>")
    assert "<!-- wp:paragraph -->" in out
    assert "<!-- /wp:paragraph -->" in out


def test_h2():
    out = to_gutenberg("<h2>Titre</h2>")
    assert "<!-- wp:heading -->" in out
    assert 'class="wp-block-heading"' in out


def test_h3_level():
    out = to_gutenberg("<h3>Sub</h3>")
    assert '{"level":3}' in out


def test_ul():
    out = to_gutenberg("<ul><li>a</li><li>b</li></ul>")
    assert "<!-- wp:list -->" in out
    assert out.count("<!-- wp:list-item -->") == 2


def test_img_with_id():
    out = to_gutenberg('<img class="wp-image-123" src="x.jpg"/>')
    assert '"id":123' in out
    assert 'class="wp-image-123"' in out
    assert "<figure" in out


def test_img_without_id():
    out = to_gutenberg('<img src="x.jpg"/>')
    assert "<!-- wp:image" in out
    assert '"id":' not in out


def test_pros_cons():
    html = (
        '<div class="pros-cons">'
        '<div class="cons"><h3>Les -</h3><ul><li>x</li></ul></div>'
        '<div class="pros"><h3>Les +</h3><ul><li>y</li></ul></div>'
        '</div>'
    )
    out = to_gutenberg(html)
    assert "pros-cons-wrapper" in out
    assert "cons-block" in out
    assert "pros-block" in out


def test_table():
    out = to_gutenberg("<table><tr><td>x</td></tr></table>")
    assert "<!-- wp:table -->" in out


def test_blockquote():
    out = to_gutenberg("<blockquote>x</blockquote>")
    assert "<!-- wp:quote -->" in out


def test_nbsp_preserved():
    out = to_gutenberg("<p>a&nbsp;: b</p>")
    # L'espace insécable est préservé (entité &nbsp; OU caractère U+00A0 équivalent).
    assert "&nbsp;" in out or "\xa0" in out
