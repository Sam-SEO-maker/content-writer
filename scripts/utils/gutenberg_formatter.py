from __future__ import annotations

import re
from bs4 import BeautifulSoup, NavigableString, Tag


_WP_IMAGE_CLASS_RE = re.compile(r"wp-image-(\d+)")


def _decode(tag: Tag) -> str:
    return tag.decode_contents(formatter="minimal")


def _render_inner(tag: Tag) -> str:
    return tag.decode_contents(formatter="minimal")


def _heading(tag: Tag) -> str:
    level = int(tag.name[1])
    classes = tag.get("class", []) or []
    if "wp-block-heading" not in classes:
        classes.append("wp-block-heading")
    class_attr = " ".join(classes)
    inner = _render_inner(tag)
    extra = ""
    for k, v in tag.attrs.items():
        if k in ("class",):
            continue
        extra += f' {k}="{v}"'
    open_comment = "<!-- wp:heading -->" if level == 2 else f'<!-- wp:heading {{"level":{level}}} -->'
    return (
        f'{open_comment}\n'
        f'<h{level} class="{class_attr}"{extra}>{inner}</h{level}>\n'
        f'<!-- /wp:heading -->'
    )


def _paragraph(tag: Tag) -> str:
    inner = _render_inner(tag)
    if not inner.strip():
        return ""
    attrs = ""
    for k, v in tag.attrs.items():
        if isinstance(v, list):
            v = " ".join(v)
        attrs += f' {k}="{v}"'
    return f"<!-- wp:paragraph -->\n<p{attrs}>{inner}</p>\n<!-- /wp:paragraph -->"


def _list(tag: Tag) -> str:
    ordered = tag.name == "ol"
    open_comment = "<!-- wp:list {\"ordered\":true} -->" if ordered else "<!-- wp:list -->"
    items = []
    for li in tag.find_all("li", recursive=False):
        items.append(
            "<!-- wp:list-item -->\n"
            f"<li>{_render_inner(li)}</li>\n"
            "<!-- /wp:list-item -->"
        )
    items_html = "\n".join(items)
    wrap = "ol" if ordered else "ul"
    return f"{open_comment}\n<{wrap}>{items_html}</{wrap}>\n<!-- /wp:list -->"


def _image(tag: Tag) -> str:
    # tag may be <figure> or <img>
    if tag.name == "figure":
        img = tag.find("img")
        figcaption = tag.find("figcaption")
    else:
        img = tag
        figcaption = None
    if img is None:
        return str(tag)

    img_classes = img.get("class", []) or []
    img_id = None
    for c in img_classes:
        m = _WP_IMAGE_CLASS_RE.match(c)
        if m:
            img_id = int(m.group(1))
            break
    if img_id is None and img.has_attr("data-wp-id"):
        try:
            img_id = int(img["data-wp-id"])
        except ValueError:
            img_id = None

    attrs_json_parts = []
    if img_id is not None:
        attrs_json_parts.append(f'"id":{img_id}')
    attrs_json_parts.append('"sizeSlug":"large"')
    attrs_json_parts.append('"linkDestination":"none"')
    attrs_json = "{" + ",".join(attrs_json_parts) + "}"

    src = img.get("src", "")
    alt = img.get("alt", "")
    img_class_attr = " ".join(img_classes) if img_classes else ""
    if img_id is not None and not any(_WP_IMAGE_CLASS_RE.match(c) for c in img_classes):
        img_class_attr = (img_class_attr + f" wp-image-{img_id}").strip()

    img_html = f'<img src="{src}" alt="{alt}"'
    if img_class_attr:
        img_html += f' class="{img_class_attr}"'
    img_html += "/>"

    caption_html = ""
    if figcaption is not None:
        caption_html = f'<figcaption class="wp-element-caption">{_render_inner(figcaption)}</figcaption>'

    return (
        f'<!-- wp:image {attrs_json} -->\n'
        f'<figure class="wp-block-image size-large">{img_html}{caption_html}</figure>\n'
        f'<!-- /wp:image -->'
    )


def _table(tag: Tag) -> str:
    return (
        "<!-- wp:table -->\n"
        f'<figure class="wp-block-table">{str(tag)}</figure>\n'
        "<!-- /wp:table -->"
    )


def _blockquote(tag: Tag) -> str:
    classes = tag.get("class", []) or []
    if "wp-block-quote" not in classes:
        classes.append("wp-block-quote")
    class_attr = " ".join(classes)
    return (
        "<!-- wp:quote -->\n"
        f'<blockquote class="{class_attr}">{_render_inner(tag)}</blockquote>\n'
        "<!-- /wp:quote -->"
    )


def _pros_cons(tag: Tag) -> str:
    cons = tag.find("div", class_="cons")
    pros = tag.find("div", class_="pros")

    def _column(col: Tag, css_class: str) -> str:
        if col is None:
            return ""
        inner_blocks = []
        for child in col.children:
            if isinstance(child, NavigableString):
                if str(child).strip():
                    inner_blocks.append(str(child))
                continue
            inner_blocks.append(_convert_element(child))
        inner_html = "\n".join(b for b in inner_blocks if b)
        return (
            f'<!-- wp:column {{"className":"{css_class}"}} -->\n'
            f'<div class="wp-block-column {css_class}">\n{inner_html}\n</div>\n'
            f'<!-- /wp:column -->'
        )

    cons_html = _column(cons, "cons-block")
    pros_html = _column(pros, "pros-block")

    return (
        '<!-- wp:columns {"className":"pros-cons-wrapper"} -->\n'
        '<div class="wp-block-columns pros-cons-wrapper">\n'
        f'{cons_html}\n{pros_html}\n'
        '</div>\n'
        '<!-- /wp:columns -->'
    )


def _convert_element(tag: Tag) -> str:
    name = tag.name
    if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
        return _heading(tag)
    if name == "p":
        return _paragraph(tag)
    if name in ("ul", "ol"):
        return _list(tag)
    if name == "img":
        return _image(tag)
    if name == "figure":
        if tag.find("img") is not None:
            return _image(tag)
        return str(tag)
    if name == "table":
        return _table(tag)
    if name == "blockquote":
        return _blockquote(tag)
    if name == "div":
        classes = tag.get("class", []) or []
        if "pros-cons" in classes:
            return _pros_cons(tag)
    return str(tag)


def to_gutenberg(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    root = soup.body if soup.body is not None else soup
    blocks = []
    for child in root.children:
        if isinstance(child, NavigableString):
            text = str(child)
            if text.strip():
                blocks.append(
                    f"<!-- wp:paragraph -->\n<p>{text.strip()}</p>\n<!-- /wp:paragraph -->"
                )
            continue
        if not isinstance(child, Tag):
            continue
        rendered = _convert_element(child)
        if rendered:
            blocks.append(rendered)
    return "\n\n".join(blocks)
