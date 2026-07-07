from __future__ import annotations

import json
import re
import uuid
from bs4 import BeautifulSoup, NavigableString, Tag


_WP_IMAGE_CLASS_RE = re.compile(r"wp-image-(\d+)")

_YELLOW = {"bg": "#fffbf0", "border": "#ffcf3b"}  # Info Box Jaune
_BLUE = {"bg": "#e8f2ff", "border": "#157dfe"}    # Info Box Bleue


def _block_attrs(d: dict) -> str:
    """JSON d'attributs de bloc : accents litteraux, tags HTML echappes en \\u003c (format AdvGB)."""
    s = json.dumps(d, ensure_ascii=False, separators=(",", ":"))
    return s.replace("<", "\\u003c").replace(">", "\\u003e")


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
    # Bloc custom Superprof : on emet superprof/quote-block (PAS le wp:quote natif,
    # sinon Gutenberg signale un contenu invalide vu la classe wp-block-superprof-quote-block).
    if "wp-block-superprof-quote-block" in classes:
        p = tag.find("p")
        cite = tag.find("cite")
        quote = _render_inner(p).strip() if p is not None else ""
        citation = _render_inner(cite).strip() if cite is not None else ""
        attrs = _block_attrs({"quote": quote, "citation": citation})
        return (
            f"<!-- wp:superprof/quote-block {attrs} -->\n"
            f'<blockquote class="wp-block-superprof-quote-block"><p>{quote}</p><cite>{citation}</cite></blockquote>\n'
            "<!-- /wp:superprof/quote-block -->"
        )
    if "wp-block-quote" not in classes:
        classes.append("wp-block-quote")
    class_attr = " ".join(classes)
    return (
        "<!-- wp:quote -->\n"
        f'<blockquote class="{class_attr}">{_render_inner(tag)}</blockquote>\n'
        "<!-- /wp:quote -->"
    )


def _infobox(tag: Tag) -> str:
    """div.wp-block-advgb-infobox brut -> bloc AdvGB single-line avec commentaire.

    Couleur deduite du suffixe de classe (001/jaune -> jaune, 002/bleu -> bleue)."""
    suffix = ""
    for c in tag.get("class", []) or []:
        if c.startswith("advgb-infobox-") and c != "advgb-infobox-wrapper":
            suffix = c[len("advgb-infobox-"):]
    s = suffix.lower()
    col = _YELLOW if ("jaune" in s or s.endswith("001")) else _BLUE
    title_tag = tag.find(class_="advgb-infobox-title")
    text_tag = tag.find(class_="advgb-infobox-text")
    title = _render_inner(title_tag).strip() if title_tag is not None else ""
    text = _render_inner(text_tag).strip() if text_tag is not None else ""
    new_id = f"advgb-infobox-{uuid.uuid4()}"
    attrs = _block_attrs({
        "blockIDX": new_id,
        "containerBorderWidth": 2,
        "containerBackground": col["bg"],
        "containerBorderBackground": col["border"],
        "iconBackground": col["bg"],
        "iconColor": col["border"],
        "title": title,
        "titleHtmlTag": "div",
        "text": text,
        "changed": True,
    })
    markup = (
        f'<div class="wp-block-advgb-infobox advgb-infobox-wrapper has-text-align-center {new_id}">'
        f'<div class="advgb-infobox-wrap"><div class="advgb-infobox-icon-container">'
        f'<div class="advgb-infobox-icon-inner-container"><i class="material-icons-outlined">beenhere</i></div></div>'
        f'<div class="advgb-infobox-textcontent"><div class="advgb-infobox-title">{title}</div>'
        f'<p class="advgb-infobox-text">{text}</p></div></div></div>'
    )
    return f"<!-- wp:advgb/infobox {attrs} -->\n{markup}\n<!-- /wp:advgb/infobox -->"


def _count_up(tag: Tag) -> str:
    """div.wp-block-advgb-count-up brut -> bloc AdvGB single-line avec commentaire."""
    header_tag = tag.find(class_="advgb-count-up-header")
    num_tag = tag.find(class_="advgb-counter-number")
    counter_tag = tag.find(class_="advgb-counter")
    desc_tag = tag.find(class_="advgb-count-up-desc")
    header = _render_inner(header_tag).strip() if header_tag is not None else ""
    num = _render_inner(num_tag).strip() if num_tag is not None else ""
    desc = _render_inner(desc_tag).strip() if desc_tag is not None else ""
    color = "#157dfe"
    if counter_tag is not None:
        m = re.search(r"color:\s*(#[0-9a-fA-F]+)", counter_tag.get("style", "") or "")
        if m:
            color = m.group(1)
    new_id = f"count-up-{uuid.uuid4()}"
    attrs = _block_attrs({
        "id": new_id,
        "headerText": header,
        "countUpNumber": num,
        "countUpNumberColor": color,
        "descText": desc,
        "changed": True,
    })
    markup = (
        f'<div class="wp-block-advgb-count-up advgb-count-up {new_id}" style="display:flex">'
        f'<div class="advgb-count-up-columns-one"><h4 class="advgb-count-up-header">{header}</h4>'
        f'<div class="advgb-counter" style="color:{color};font-size:55px">'
        f'<span class="advgb-counter-number">{num}</span></div>'
        f'<p class="advgb-count-up-desc">{desc}</p></div></div>'
    )
    return f"<!-- wp:advgb/count-up {attrs} -->\n{markup}\n<!-- /wp:advgb/count-up -->"


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


def _sources_group(tag: Tag) -> str:
    """Bloc Sources brut (group > group.block-sources > h2 + ol.references) -> commentaires Gutenberg."""
    inner = tag.find(class_="wp-block-wp-sp-gutenberg-blocks-block-sources")
    src = inner if inner is not None else tag
    h2 = src.find("h2")
    ol = src.find("ol")
    h2_text = _render_inner(h2).strip() if h2 is not None else "Sources"
    items = []
    if ol is not None:
        for li in ol.find_all("li", recursive=False):
            items.append(
                f"<!-- wp:list-item -->\n<li>{_render_inner(li).strip()}</li>\n<!-- /wp:list-item -->"
            )
    items_html = "\n\n".join(items)
    list_block = (
        '<!-- wp:list {"ordered":true,"className":"references"} -->\n'
        f'<ol class="wp-block-list references">{items_html}</ol>\n'
        "<!-- /wp:list -->"
    )
    return (
        "<!-- wp:group -->\n"
        '<div class="wp-block-group"><!-- wp:group {"className":"wp-block-wp-sp-gutenberg-blocks-block-sources"} -->\n'
        '<div class="wp-block-group wp-block-wp-sp-gutenberg-blocks-block-sources"><!-- wp:heading -->\n'
        f'<h2 class="wp-block-heading">{h2_text}</h2>\n'
        "<!-- /wp:heading -->\n\n"
        f"{list_block}</div>\n"
        "<!-- /wp:group --></div>\n"
        "<!-- /wp:group -->"
    )


def _timeline(tag: Tag) -> str:
    """div.wp-block-superprof-timeline-block brut -> commentaires Gutenberg.

    Enveloppe le wrapper avec <!-- wp:superprof/timeline-block --> et chaque ligne
    avec <!-- wp:timeline/timeline-container {itemDate,itemTitle,itemDescription,isLast} -->.
    """
    rows = tag.find_all("div", class_="wp-block-timeline-timeline-container")
    n = len(rows)
    containers = []
    for i, row in enumerate(rows):
        date_tag = row.find(class_="timeline-date-item")
        title_tag = row.find(class_="timeline-title")
        desc_tag = row.find(class_="timeline-description")
        date = _render_inner(date_tag).strip() if date_tag is not None else ""
        title = _render_inner(title_tag).strip() if title_tag is not None else ""
        desc = _render_inner(desc_tag).strip() if desc_tag is not None else ""
        attrs = _block_attrs({
            "itemDate": date,
            "itemTitle": title,
            "itemDescription": desc,
            "isLast": i == n - 1,
        })
        containers.append(
            f"<!-- wp:timeline/timeline-container {attrs} -->\n"
            '<div class="wp-block-timeline-timeline-container timeline-row">\n'
            '<div class="timeline-dot" style="background-color:#ff6363"></div>\n'
            '<div class="timeline-date">\n'
            f'<p class="timeline-date-item" style="color:#ff6363;font-size:18px;text-align:left">{date}</p>\n'
            "</div>\n"
            '<div class="timeline-details">\n'
            f'<p class="timeline-title" style="color:#888888;font-size:18px">{title}</p>\n'
            f'<p class="timeline-description" style="color:#888888;font-size:16px">{desc}</p>\n'
            "</div>\n"
            "</div>\n"
            "<!-- /wp:timeline/timeline-container -->"
        )
    return (
        "<!-- wp:superprof/timeline-block -->\n"
        '<div class="wp-block-superprof-timeline-block timeline medium">\n'
        + "\n".join(containers)
        + "\n</div>\n"
        "<!-- /wp:superprof/timeline-block -->"
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
        if "wp-block-advgb-infobox" in classes:
            return _infobox(tag)
        if "wp-block-advgb-count-up" in classes:
            return _count_up(tag)
        if "wp-block-superprof-timeline-block" in classes:
            return _timeline(tag)
        if "wp-block-group" in classes and tag.find(class_="wp-block-wp-sp-gutenberg-blocks-block-sources") is not None:
            return _sources_group(tag)
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
