#!/usr/bin/env python3
"""Build static English and Spanish pages from the legacy bilingual HTML.

The source is always read from a Git revision so the transformation is
repeatable even after the generated files have replaced the working copies.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit

from lxml import etree, html


ORIGIN = "https://portroyale285.es"
BUILD_VERSION = "20260817-locale1"
SOURCE_COMMIT = "6d22c8f69fc581ec5a83de648a447988696f6791"


@dataclass(frozen=True)
class PagePair:
    source: str
    en_path: str
    es_path: str

    @property
    def en_url(self) -> str:
        return ORIGIN + self.en_path

    @property
    def es_url(self) -> str:
        return ORIGIN + self.es_path

    @property
    def es_file(self) -> str:
        if self.es_path == "/es/":
            return "es/index.html"
        return self.es_path.lstrip("/")


PAIRS = (
    PagePair("index.html", "/", "/es/"),
    PagePair("guest-guide.html", "/guest-guide.html", "/es/guest-guide.html"),
    PagePair("tenerife-guide.html", "/tenerife-guide.html", "/es/tenerife-guide.html"),
    PagePair(
        "africa-si-occidentul-tenerife.html",
        "/africa-si-occidentul-tenerife.html",
        "/es/africa-si-occidentul-tenerife.html",
    ),
    PagePair(
        "editorial-vara-2026.html",
        "/editorial-vara-2026.html",
        "/es/editorial-vara-2026.html",
    ),
    PagePair(
        "jurnal-de-tenerife-vara-2026.html",
        "/jurnal-de-tenerife-vara-2026.html",
        "/es/jurnal-de-tenerife-vara-2026.html",
    ),
    PagePair(
        "la-recova-tenerife.html",
        "/la-recova-tenerife.html",
        "/es/la-recova-tenerife.html",
    ),
)

PAIR_BY_SOURCE = {pair.source: pair for pair in PAIRS}
PAIR_BY_EN_PATH = {pair.en_path: pair for pair in PAIRS}
PAIR_BY_EN_PATH["/index.html"] = PAIRS[0]

CLASS_TOKEN = "contains(concat(' ', normalize-space(@class), ' '), ' {token} ')"
CSS_URL_RE = re.compile(r"url\(\s*([\"']?)([^\"')]+)\1\s*\)", re.IGNORECASE)
SVG_BLOCK_RE = re.compile(r"<svg\b.*?</svg>", re.IGNORECASE | re.DOTALL)
SVG_PLACEHOLDER_RE = re.compile(
    r'<locale-svg-placeholder\s+data-index="(\d+)"\s*></locale-svg-placeholder>',
    re.IGNORECASE,
)


def class_xpath(token: str) -> str:
    return CLASS_TOKEN.format(token=token)


def git_source(repo: Path, git_executable: str, source_ref: str, name: str) -> str:
    result = subprocess.run(
        [git_executable, "show", f"{source_ref}:{name}"],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.decode("utf-8-sig")


def parse_document(source: str) -> etree._Element:
    parser = html.HTMLParser(encoding="utf-8", remove_comments=False)
    return html.document_fromstring(source, parser=parser)


def protect_svg_blocks(source: str) -> tuple[str, list[str]]:
    """Protect inline SVG because lxml's HTML serializer lowercases SVG attributes."""
    blocks: list[str] = []

    def replace(match: re.Match[str]) -> str:
        index = len(blocks)
        blocks.append(match.group(0))
        return f'<locale-svg-placeholder data-index="{index}"></locale-svg-placeholder>'

    return SVG_BLOCK_RE.sub(replace, source), blocks


def restore_svg_blocks(source: str, blocks: list[str]) -> str:
    restored: set[int] = set()

    def replace(match: re.Match[str]) -> str:
        index = int(match.group(1))
        restored.add(index)
        return blocks[index]

    output = SVG_PLACEHOLDER_RE.sub(replace, source)
    if restored != set(range(len(blocks))):
        missing = sorted(set(range(len(blocks))) - restored)
        raise RuntimeError(f"Failed to restore protected SVG blocks: {missing}")
    return output


def remove_element(element: etree._Element) -> None:
    parent = element.getparent()
    if parent is None:
        return
    previous = element.getprevious()
    tail = element.tail
    parent.remove(element)
    if tail:
        if previous is not None:
            previous.tail = (previous.tail or "") + tail
        else:
            parent.text = (parent.text or "") + tail


def replace_text_content(element: etree._Element, value: str) -> None:
    for child in list(element):
        element.remove(child)
    element.text = value


def replace_inner_html(element: etree._Element, value: str) -> None:
    for child in list(element):
        element.remove(child)
    element.text = None
    previous: etree._Element | None = None
    for fragment in html.fragments_fromstring(value):
        if isinstance(fragment, str):
            if previous is None:
                element.text = (element.text or "") + fragment
            else:
                previous.tail = (previous.tail or "") + fragment
        else:
            element.append(fragment)
            previous = fragment


def translate_dom(document: etree._Element, locale: str) -> None:
    for element in document.xpath("//*[@data-es-html]"):
        if locale == "es":
            replace_inner_html(element, element.get("data-es-html") or "")

    for element in document.xpath("//*[@data-es]"):
        if locale == "es":
            replace_text_content(element, element.get("data-es") or "")

    for element in document.xpath("//*[@data-i18n-attributes]"):
        attributes = [
            name.strip()
            for name in (element.get("data-i18n-attributes") or "").split(",")
            if name.strip()
        ]
        if locale == "es":
            for attribute in attributes:
                translated = element.get(f"data-es-{attribute}")
                if translated is not None:
                    element.set(attribute, translated)

    for element in document.iter():
        for attribute in list(element.attrib):
            if (
                attribute == "data-es"
                or attribute == "data-es-html"
                or attribute == "data-i18n-attributes"
                or attribute.startswith("data-es-")
            ):
                del element.attrib[attribute]


def select_language_panel(document: etree._Element, locale: str) -> None:
    panels = document.xpath(f"//*[{class_xpath('language-panel')}]")
    for panel in panels:
        if panel.get("lang") != locale:
            remove_element(panel)
            continue

        classes = [name for name in (panel.get("class") or "").split() if name != "language-panel"]
        if classes:
            panel.set("class", " ".join(classes))
        elif "class" in panel.attrib:
            del panel.attrib["class"]
        panel.set("id", "article-content")
        for attribute in ("lang", "hidden", "aria-hidden"):
            panel.attrib.pop(attribute, None)


def rewrite_page_url(value: str, locale: str) -> str:
    if locale != "es":
        return value

    parsed = urlsplit(value)
    if parsed.scheme and parsed.netloc and f"{parsed.scheme}://{parsed.netloc}" != ORIGIN:
        return value

    path = parsed.path or "/"
    pair = PAIR_BY_EN_PATH.get(path)
    if pair is None:
        return value
    return urlunsplit((parsed.scheme, parsed.netloc, pair.es_path, parsed.query, parsed.fragment))


def rewrite_json_value(value: Any, locale: str) -> Any:
    if isinstance(value, dict):
        return {key: rewrite_json_value(item, locale) for key, item in value.items()}
    if isinstance(value, list):
        return [rewrite_json_value(item, locale) for item in value]
    if isinstance(value, str):
        rewritten = rewrite_page_url(value, locale)
        if locale == "en":
            rewritten = rewritten.replace("bilingual Tenerife Guide story", "Tenerife Guide story")
            rewritten = rewritten.replace("through a bilingual story", "through a story")
        else:
            rewritten = rewritten.replace("relato bilingüe de Tenerife Guide", "relato de Tenerife Guide")
            rewritten = rewritten.replace("a través de un relato bilingüe", "a través de un relato")
        return rewritten
    return value


def stabilize_jsonld_entity_urls(payload: Any) -> None:
    """Keep the site and publisher identities stable across locale pages.

    Page-specific URLs are localized to ``/es/``. The WebSite and publisher
    entities describe the same site/business in both languages, so their
    canonical identity remains the root URL.
    """
    if isinstance(payload, list):
        for item in payload:
            stabilize_jsonld_entity_urls(item)
        return
    if not isinstance(payload, dict):
        return

    publisher = payload.get("publisher")
    if isinstance(publisher, dict) and "url" in publisher:
        publisher["url"] = ORIGIN + "/"

    website = payload.get("isPartOf")
    if isinstance(website, dict):
        if "url" in website:
            website["url"] = ORIGIN + "/"
        if "@id" in website:
            website["@id"] = ORIGIN + "/#website"

    for item in payload.values():
        stabilize_jsonld_entity_urls(item)


def select_jsonld(document: etree._Element, locale: str) -> None:
    for script in list(document.xpath("//script[@data-language-jsonld]")):
        if script.get("data-language-jsonld") != locale:
            remove_element(script)
            continue

        script.set("type", "application/ld+json")
        script.attrib.pop("data-language-jsonld", None)
        payload = json.loads(script.text or "{}")
        payload = rewrite_json_value(payload, locale)
        if isinstance(payload, dict):
            payload["inLanguage"] = "en-GB" if locale == "en" else "es-ES"
        stabilize_jsonld_entity_urls(payload)
        script.text = "\n" + json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def set_head_urls(document: etree._Element, pair: PagePair, locale: str) -> None:
    canonical_url = pair.en_url if locale == "en" else pair.es_url
    head = document.find("head")
    if head is None:
        raise ValueError(f"{pair.source}: missing head")

    canonicals = head.xpath(".//link[translate(@rel,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')='canonical']")
    if len(canonicals) != 1:
        raise ValueError(f"{pair.source}: expected one canonical, found {len(canonicals)}")
    canonical = canonicals[0]
    canonical.set("href", canonical_url)

    for alternate in list(head.xpath(".//link[@hreflang]")):
        remove_element(alternate)

    insert_at = head.index(canonical) + 1
    alternates = (
        ("en", pair.en_url),
        ("es", pair.es_url),
        ("x-default", pair.en_url),
    )
    for language, url in alternates:
        link = etree.Element("link")
        link.set("rel", "alternate")
        link.set("hreflang", language)
        link.set("href", url)
        head.insert(insert_at, link)
        insert_at += 1

    for meta in head.xpath(".//meta[@property='og:url']"):
        meta.set("content", canonical_url)


def replace_language_switcher(document: etree._Element, pair: PagePair, locale: str) -> None:
    switches = document.xpath(f"//*[{class_xpath('lang-switch')}]")
    if len(switches) != 1:
        raise ValueError(f"{pair.source}: expected one language switcher, found {len(switches)}")
    switch = switches[0]
    for child in list(switch):
        switch.remove(child)
    switch.text = None
    switch.set("aria-label", "Language selector" if locale == "en" else "Selector de idioma")

    choices = (
        ("en", "EN", pair.en_path, "English"),
        ("es", "ES", pair.es_path, "Español"),
    )
    for language, label, href, title in choices:
        anchor = etree.Element("a")
        anchor.set("href", href)
        anchor.set("hreflang", language)
        anchor.set("lang", language)
        anchor.set("title", title)
        anchor.set("aria-label", title)
        if language == locale:
            anchor.set("class", "active")
            anchor.set("aria-current", "page")
        anchor.text = label
        switch.append(anchor)


def simplify_guest_guide_spanish_cta(
    document: etree._Element,
    pair: PagePair,
    locale: str,
) -> None:
    """Keep the mobile Guest Guide footer action short and readable."""
    if pair.source != "guest-guide.html" or locale != "es":
        return

    buttons = document.xpath(
        "//a[@href='#restaurants' and "
        "contains(concat(' ', normalize-space(@class), ' '), ' gallery-btn ')]"
    )
    if len(buttons) != 1:
        raise ValueError(
            f"{pair.source}: expected one Spanish local-tips footer action, "
            f"found {len(buttons)}"
        )
    replace_text_content(buttons[0], "Consejos locales")


def is_external_or_special(value: str) -> bool:
    parsed = urlsplit(value)
    return bool(
        value.startswith(("#", "//"))
        or parsed.scheme in {"http", "https", "mailto", "tel", "data", "javascript"}
    )


def normalize_internal_href(value: str, locale: str) -> str:
    if locale != "es" or not value:
        return value
    if value.startswith("#"):
        return value

    parsed = urlsplit(value)
    if parsed.scheme in {"http", "https"}:
        if f"{parsed.scheme}://{parsed.netloc}" != ORIGIN:
            return value
        path = parsed.path or "/"
    elif parsed.scheme or value.startswith("//"):
        return value
    else:
        path = parsed.path

    normalized = "/" + path.lstrip("/") if path else "/"
    pair = PAIR_BY_EN_PATH.get(normalized)
    if pair is None:
        return value

    return urlunsplit(("", "", pair.es_path, parsed.query, parsed.fragment))


def rewrite_internal_links(document: etree._Element, locale: str) -> None:
    if locale != "es":
        return
    for anchor in document.xpath("//a[@href]"):
        # The switcher has already been written with the correct cross-locale links.
        parent = anchor.getparent()
        if parent is not None and "lang-switch" in (parent.get("class") or "").split():
            continue
        anchor.set("href", normalize_internal_href(anchor.get("href") or "", locale))


def root_asset_path(value: str, repo: Path) -> str:
    if not value or is_external_or_special(value) or value.startswith("/"):
        return value
    parsed = urlsplit(value)
    if not parsed.path or parsed.path.endswith(".html"):
        return value
    candidate = (repo / parsed.path).resolve()
    try:
        candidate.relative_to(repo.resolve())
    except ValueError:
        return value
    if not candidate.exists():
        return value
    return urlunsplit(("", "", "/" + PurePosixPath(parsed.path).as_posix(), parsed.query, parsed.fragment))


def rewrite_srcset(value: str, repo: Path) -> str:
    rewritten: list[str] = []
    for candidate in value.split(","):
        parts = candidate.strip().split()
        if not parts:
            continue
        parts[0] = root_asset_path(parts[0], repo)
        rewritten.append(" ".join(parts))
    return ", ".join(rewritten)


def rewrite_css_urls(value: str, repo: Path) -> str:
    def replace(match: re.Match[str]) -> str:
        quote = match.group(1)
        url = match.group(2).strip()
        rewritten = root_asset_path(url, repo)
        return f"url({quote}{rewritten}{quote})"

    return CSS_URL_RE.sub(replace, value)


def normalize_spanish_assets(document: etree._Element, repo: Path, locale: str) -> None:
    if locale != "es":
        return

    for element in document.iter():
        for attribute in ("src", "poster"):
            if element.get(attribute):
                element.set(attribute, root_asset_path(element.get(attribute) or "", repo))
        if element.get("srcset"):
            element.set("srcset", rewrite_srcset(element.get("srcset") or "", repo))
        if element.get("style"):
            element.set("style", rewrite_css_urls(element.get("style") or "", repo))

    for element in document.xpath("//link[@href] | //script[@src]"):
        attribute = "href" if element.tag.lower() == "link" else "src"
        element.set(attribute, root_asset_path(element.get(attribute) or "", repo))

    for style in document.xpath("//style"):
        if style.text:
            style.text = rewrite_css_urls(style.text, repo)


def replace_runtime_asset(document: etree._Element) -> None:
    matches = [
        script
        for script in document.xpath("//script[@src]")
        if "assets/language-switcher.js" in (script.get("src") or "")
    ]
    if len(matches) != 1:
        raise ValueError(f"expected one language-switcher.js reference, found {len(matches)}")
    script = matches[0]
    script.set("src", f"/assets/adaptive-nav.js?v={BUILD_VERSION}")
    script.set("defer", "defer")


def version_changed_stylesheets(document: etree._Element) -> None:
    changed_stylesheets = {
        "assets/language-switcher.css",
        "assets/guide-shell.css",
    }
    for link in document.xpath("//link[@href]"):
        href = link.get("href") or ""
        parsed = urlsplit(href)
        if parsed.path.lstrip("/") not in changed_stylesheets:
            continue
        link.set(
            "href",
            urlunsplit((parsed.scheme, parsed.netloc, parsed.path, f"v={BUILD_VERSION}", parsed.fragment)),
        )


def remove_legacy_locale_markers(document: etree._Element) -> None:
    root = document
    for attribute in ("data-language", "data-language-ready"):
        root.attrib.pop(attribute, None)


def cleanup_locale_wording(document: etree._Element, locale: str) -> None:
    replacements = (
        (
            ("bilingual Tenerife Guide story", "Tenerife Guide story"),
            ("through a bilingual story", "through a story"),
            (" · EN | ES", ""),
            (" · en | es", ""),
        )
        if locale == "en"
        else (
            ("relato bilingüe de Tenerife Guide", "relato de Tenerife Guide"),
            ("a través de un relato bilingüe", "a través de un relato"),
            (" · EN | ES", ""),
            (" · en | es", ""),
        )
    )

    # These phrases describe the old dual-language implementation. Adjust
    # metadata only; editorial body copy remains byte-for-byte semantically
    # unchanged apart from selecting its existing EN or ES panel.
    head = document.find("head")
    for element in head.iter() if head is not None else ():
        if element.tag in {"script", "style"}:
            continue
        if element.text:
            for old, new in replacements:
                element.text = element.text.replace(old, new)
        for attribute, value in list(element.attrib.items()):
            if attribute in {"content", "data-category", "title", "aria-label"}:
                for old, new in replacements:
                    value = value.replace(old, new)
                element.set(attribute, value)

    # Card labels are interface metadata, not article copy. Once languages live
    # at separate URLs, advertising "EN | ES" on every card is stale.
    for meta in document.xpath(f"//*[{class_xpath('guide-card-meta')}]"):
        if meta.text:
            meta.text = re.sub(r"\s*\u00b7\s*EN\s*\|\s*ES\s*$", "", meta.text, flags=re.IGNORECASE)

    categories = {
        "opening story": "relato de apertura",
        "travel journal": "diario de viaje",
        "places": "lugares",
        "editorial": "editorial",
    }
    for card in document.xpath("//*[@data-category]"):
        category = re.sub(
            r"\s*\u00b7\s*en\s*\|\s*es\s*$",
            "",
            (card.get("data-category") or "").strip(),
            flags=re.IGNORECASE,
        ).strip().lower()
        card.set("data-category", categories.get(category, category) if locale == "es" else category)


def build_variant(source: str, pair: PagePair, locale: str, repo: Path) -> str:
    # The shared responsive CSS rule must follow the static document language.
    source = source.replace('html[data-language="es"]', 'html[lang="es"]')
    # Preserve page-local hero optimizations after the bilingual panel IDs are
    # replaced by one language-neutral ID in each static document.
    source = source.replace("#article-en", "#article-content")
    source = source.replace("#article-es", "#article-content")
    source = re.sub(
        r"(?m)^([ \t]*)#article-content \.hero,\s*\r?\n[ \t]*#article-content \.hero",
        r"\1#article-content .hero",
        source,
    )
    protected_source, svg_blocks = protect_svg_blocks(source)
    document = parse_document(protected_source)
    document.set("lang", locale)

    select_language_panel(document, locale)
    translate_dom(document, locale)
    simplify_guest_guide_spanish_cta(document, pair, locale)
    select_jsonld(document, locale)
    set_head_urls(document, pair, locale)
    replace_language_switcher(document, pair, locale)
    rewrite_internal_links(document, locale)
    normalize_spanish_assets(document, repo, locale)
    replace_runtime_asset(document)
    version_changed_stylesheets(document)
    cleanup_locale_wording(document, locale)
    remove_legacy_locale_markers(document)

    output = etree.tostring(
        document,
        encoding="unicode",
        method="html",
        pretty_print=False,
        doctype="<!DOCTYPE html>",
    )
    output = restore_svg_blocks(output, svg_blocks)
    # ``source`` is a void HTML element. lxml's HTML serializer can emit a
    # forbidden closing tag when a following ``img`` is present in ``picture``.
    output = re.sub(r"</source\s*>", "", output, flags=re.IGNORECASE)
    # Keep generated pages clean for ``git diff --check`` without changing
    # meaningful whitespace inside a line.
    output = re.sub(r"[ \t]+(?=\r?\n)", "", output)
    return output.rstrip() + "\n"


def parser_self_test() -> None:
    source = '<!DOCTYPE html><html><body><svg viewBox="0 0 10 10" preserveAspectRatio="xMidYMid"><path d="M0 0"></path></svg></body></html>'
    protected_source, svg_blocks = protect_svg_blocks(source)
    output = etree.tostring(
        parse_document(protected_source),
        encoding="unicode",
        method="html",
        doctype="<!DOCTYPE html>",
    )
    output = restore_svg_blocks(output, svg_blocks)
    if 'viewBox="0 0 10 10"' not in output:
        raise RuntimeError("SVG viewBox protection failed")
    if 'preserveAspectRatio="xMidYMid"' not in output:
        raise RuntimeError("SVG preserveAspectRatio protection failed")


def write_pages(repo: Path, output_root: Path, git_executable: str, source_ref: str) -> None:
    parser_self_test()
    sources = {
        pair.source: git_source(repo, git_executable, source_ref, pair.source)
        for pair in PAIRS
    }

    for pair in PAIRS:
        source = sources[pair.source]
        outputs = (
            (pair.source, build_variant(source, pair, "en", repo)),
            (pair.es_file, build_variant(source, pair, "es", repo)),
        )
        for relative_path, content in outputs:
            destination = output_root / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8", newline="\n")
            print(relative_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--git", default="git")
    parser.add_argument(
        "--source-ref",
        default=SOURCE_COMMIT,
        help="Git revision containing the legacy bilingual source pages",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo = args.repo.resolve()
    output_root = args.output_root.resolve()
    write_pages(repo, output_root, args.git, args.source_ref)


if __name__ == "__main__":
    main()
