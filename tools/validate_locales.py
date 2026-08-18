#!/usr/bin/env python3
"""Validate the static EN-at-root and ES-under-/es/ site layout.

Usage:
    python tools/validate_locales.py [BUILD_ROOT]

BUILD_ROOT defaults to the repository root containing this script.  The
validator uses only the Python standard library so it can also run in a clean
CI environment.
"""

from __future__ import annotations

import argparse
import collections
import json
import posixpath
import re
import sys
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit
from xml.etree import ElementTree


ORIGIN = "https://portroyale285.es"
EXPECTED_ASSET_VERSION = "20260818-langbar1"
FILENAMES = (
    "index.html",
    "guest-guide.html",
    "tenerife-guide.html",
    "about-tenerife-guide.html",
    "africa-si-occidentul-tenerife.html",
    "editorial-vara-2026.html",
    "jurnal-de-tenerife-vara-2026.html",
    "la-recova-tenerife.html",
)
REGIONAL_LANGUAGE = {"en": "en-GB", "es": "es-ES"}
OG_LOCALE = {"en": "en_GB", "es": "es_ES"}
VOID_ELEMENTS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
IGNORED_SCHEMES = {"data", "javascript", "mailto", "tel", "sms", "blob"}
CSS_URL_RE = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE | re.DOTALL)
AUTO_REDIRECT_PATTERNS = {
    "browser-language detection": re.compile(
        r"\bnavigator\s*\.\s*languages?\b", re.IGNORECASE
    ),
    "automatic location replacement": re.compile(
        r"\b(?:(?:window|document)\s*\.\s*)?location\s*\.\s*"
        r"(?:replace|assign)\s*\(",
        re.IGNORECASE,
    ),
    "automatic location assignment": re.compile(
        r"\b(?:window|document)\s*\.\s*location(?:\s*\.\s*href)?\s*=",
        re.IGNORECASE,
    ),
    "GeoIP locale selection": re.compile(r"\bgeo\s*[-_]?ip\b", re.IGNORECASE),
    "legacy saved language": re.compile(
        r"\bportroyale285_language\b", re.IGNORECASE
    ),
}


@dataclass(frozen=True)
class PageSpec:
    language: str
    filename: str
    relative_file: str
    public_url: str
    pair_key: str


def build_specs() -> list[PageSpec]:
    specs: list[PageSpec] = []
    for filename in FILENAMES:
        en_url = f"{ORIGIN}/" if filename == "index.html" else f"{ORIGIN}/{filename}"
        es_url = (
            f"{ORIGIN}/es/"
            if filename == "index.html"
            else f"{ORIGIN}/es/{filename}"
        )
        specs.append(PageSpec("en", filename, filename, en_url, filename))
        specs.append(PageSpec("es", filename, f"es/{filename}", es_url, filename))
    return specs


SPECS = build_specs()
SPEC_BY_URL = {spec.public_url: spec for spec in SPECS}
EXPECTED_URLS = set(SPEC_BY_URL)


def normalise_space(value: str) -> str:
    return " ".join(value.split())


def class_tokens(attributes: dict[str, str]) -> set[str]:
    return set(attributes.get("class", "").split())


@dataclass
class Element:
    tag: str
    attributes: dict[str, str]
    in_language_switcher: bool
    text_parts: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return normalise_space("".join(self.text_parts))


class DocumentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.elements: list[Element] = []
        self.stack: list[Element] = []

    def _start(self, tag: str, attrs: list[tuple[str, str | None]], push: bool) -> None:
        tag = tag.lower()
        attributes = {key.lower(): value or "" for key, value in attrs}
        parent_switcher = bool(self.stack and self.stack[-1].in_language_switcher)
        own_switcher = tag == "nav" and "lang-switch" in class_tokens(attributes)
        element = Element(tag, attributes, parent_switcher or own_switcher)
        self.elements.append(element)
        if push and tag not in VOID_ELEMENTS:
            self.stack.append(element)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._start(tag, attrs, True)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._start(tag, attrs, False)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data: str) -> None:
        for element in self.stack:
            element.text_parts.append(data)


@dataclass
class PageDocument:
    spec: PageSpec
    path: Path
    source: str
    parser: DocumentParser

    def elements(self, tag: str | None = None) -> list[Element]:
        if tag is None:
            return self.parser.elements
        return [element for element in self.parser.elements if element.tag == tag]


def parse_html(path: Path, spec: PageSpec) -> PageDocument:
    source = path.read_text(encoding="utf-8")
    parser = DocumentParser()
    parser.feed(source)
    parser.close()
    return PageDocument(spec, path, source, parser)


def canonicalise_public_url(value: str) -> str:
    split = urlsplit(value)
    scheme = split.scheme.lower()
    netloc = split.netloc.lower()
    path = posixpath.normpath(unquote(split.path or "/"))
    if split.path.endswith("/") and path != "/":
        path += "/"
    if path == "/index.html":
        path = "/"
    elif path == "/es/index.html":
        path = "/es/"
    return urlunsplit((scheme, netloc, path, "", ""))


def resolved_public_url(base_url: str, reference: str) -> str | None:
    reference = reference.strip()
    if not reference:
        return canonicalise_public_url(base_url)
    split = urlsplit(reference)
    if split.scheme.lower() in IGNORED_SCHEMES:
        return None
    return canonicalise_public_url(urljoin(base_url, reference))


def target_path(root: Path, public_url: str) -> Path | None:
    split = urlsplit(public_url)
    if split.netloc.lower() != urlsplit(ORIGIN).netloc.lower():
        return None
    url_path = unquote(split.path)
    if "\\" in url_path:
        return root / "__INVALID_BACKSLASH_URL__"
    if url_path.endswith("/"):
        url_path += "index.html"
    relative = url_path.lstrip("/")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return root / "__REFERENCE_ESCAPES_ROOT__"
    return candidate


def add_error(errors: list[str], page: str, message: str) -> None:
    errors.append(f"{page}: {message}")


def meta_values(document: PageDocument, key: str, value: str) -> list[str]:
    result = []
    for element in document.elements("meta"):
        if element.attributes.get(key, "").lower() == value.lower():
            result.append(element.attributes.get("content", "").strip())
    return result


def rel_contains(element: Element, value: str) -> bool:
    return value.lower() in element.attributes.get("rel", "").lower().split()


def alternate_map(document: PageDocument) -> dict[str, list[str]]:
    result: dict[str, list[str]] = collections.defaultdict(list)
    for element in document.elements("link"):
        if rel_contains(element, "alternate") and element.attributes.get("hreflang"):
            result[element.attributes["hreflang"].lower()].append(
                element.attributes.get("href", "").strip()
            )
    return dict(result)


def pair_urls(filename: str) -> dict[str, str]:
    pair = [spec for spec in SPECS if spec.filename == filename]
    return {spec.language: spec.public_url for spec in pair}


def selector_links(document: PageDocument) -> tuple[list[Element], list[Element], int]:
    switcher_count = sum(
        element.tag == "nav" and "lang-switch" in class_tokens(element.attributes)
        for element in document.elements()
    )
    anchors = [
        element
        for element in document.elements("a")
        if element.in_language_switcher
    ]
    buttons = [
        element
        for element in document.elements("button")
        if element.in_language_switcher
    ]
    return anchors, buttons, switcher_count


def check_selector(document: PageDocument, errors: list[str]) -> None:
    name = document.spec.relative_file
    anchors, buttons, count = selector_links(document)
    expected_urls = pair_urls(document.spec.filename)
    if count != 1:
        add_error(errors, name, f"expected one nav.lang-switch, found {count}")
    if buttons:
        add_error(errors, name, "language selector contains button(s), not only real links")
    if len(anchors) != 2:
        add_error(errors, name, f"expected two language links, found {len(anchors)}")
        return

    found: dict[str, Element] = {}
    for anchor in anchors:
        language = anchor.attributes.get("hreflang", "").lower()
        if language not in {"en", "es"}:
            add_error(errors, name, f"selector link has invalid hreflang {language!r}")
            continue
        if language in found:
            add_error(errors, name, f"selector repeats {language!r}")
        found[language] = anchor
        actual_url = resolved_public_url(document.spec.public_url, anchor.attributes.get("href", ""))
        if actual_url != expected_urls[language]:
            add_error(
                errors,
                name,
                f"selector {language} link is {actual_url!r}, expected {expected_urls[language]!r}",
            )
        if anchor.attributes.get("lang", "").lower() != language:
            add_error(errors, name, f"selector {language} link must have lang={language!r}")
        if anchor.text.upper() != language.upper():
            add_error(errors, name, f"selector {language} label is {anchor.text!r}")

    if set(found) != {"en", "es"}:
        add_error(errors, name, f"selector languages are {sorted(found)}")
    current = [
        language
        for language, anchor in found.items()
        if anchor.attributes.get("aria-current", "").lower() == "page"
    ]
    if current != [document.spec.language]:
        add_error(
            errors,
            name,
            f"aria-current languages are {current}, expected [{document.spec.language!r}]",
        )
    for language, anchor in found.items():
        if language != document.spec.language and anchor.attributes.get("aria-current"):
            add_error(errors, name, f"inactive {language} selector link has aria-current")


def check_document_basics(document: PageDocument, errors: list[str]) -> None:
    spec = document.spec
    name = spec.relative_file
    html_elements = document.elements("html")
    languages = [element.attributes.get("lang", "").lower() for element in html_elements]
    if languages != [spec.language]:
        add_error(errors, name, f"html language is {languages}, expected [{spec.language!r}]")

    titles = [element.text for element in document.elements("title") if element.text]
    if len(titles) != 1:
        add_error(errors, name, f"expected one nonempty title, found {len(titles)}")
    descriptions = meta_values(document, "name", "description")
    if len(descriptions) != 1 or not descriptions[0]:
        add_error(errors, name, f"expected one nonempty meta description, found {descriptions}")
    h1s = [element.text for element in document.elements("h1")]
    if len(h1s) != 1 or not h1s[0]:
        add_error(errors, name, f"expected one nonempty H1, found {len(h1s)}")

    ids = [element.attributes["id"] for element in document.elements() if element.attributes.get("id")]
    duplicates = sorted(value for value, count in collections.Counter(ids).items() if count > 1)
    if duplicates:
        add_error(errors, name, f"duplicate IDs: {duplicates}")

    canonicals = [
        element.attributes.get("href", "").strip()
        for element in document.elements("link")
        if rel_contains(element, "canonical")
    ]
    if canonicals != [spec.public_url]:
        add_error(errors, name, f"canonical is {canonicals}, expected [{spec.public_url!r}]")

    expected_alternates = pair_urls(spec.filename)
    expected_alternates["x-default"] = expected_alternates["en"]
    actual_alternates = alternate_map(document)
    expected_wrapped = {key: [value] for key, value in expected_alternates.items()}
    if actual_alternates != expected_wrapped:
        add_error(
            errors,
            name,
            f"hreflang map is {actual_alternates}, expected {expected_wrapped}",
        )
    elif actual_alternates[spec.language][0] != spec.public_url:
        add_error(errors, name, "current-language hreflang is not self-referential")

    og_urls = meta_values(document, "property", "og:url")
    if og_urls != [spec.public_url]:
        add_error(errors, name, f"og:url is {og_urls}, expected [{spec.public_url!r}]")
    og_locales = meta_values(document, "property", "og:locale")
    if og_locales != [OG_LOCALE[spec.language]]:
        add_error(errors, name, f"og:locale is {og_locales}, expected {OG_LOCALE[spec.language]!r}")
    other_language = "es" if spec.language == "en" else "en"
    og_alternates = meta_values(document, "property", "og:locale:alternate")
    if og_alternates != [OG_LOCALE[other_language]]:
        add_error(
            errors,
            name,
            f"og:locale:alternate is {og_alternates}, expected {OG_LOCALE[other_language]!r}",
        )

    robots = ",".join(meta_values(document, "name", "robots")).lower()
    if "noindex" in robots:
        add_error(errors, name, "indexable locale page contains noindex")


def check_legacy_locale_mechanisms(document: PageDocument, errors: list[str]) -> None:
    name = document.spec.relative_file
    for element in document.elements():
        attributes = element.attributes
        bad_attributes = sorted(
            key
            for key in attributes
            if key == "data-es"
            or key.startswith("data-es-")
            or key in {"data-i18n-attributes", "data-language-jsonld", "data-lang"}
        )
        if bad_attributes:
            add_error(
                errors,
                name,
                f"legacy locale attributes on <{element.tag}>: {bad_attributes}",
            )
        if "language-panel" in class_tokens(attributes):
            add_error(errors, name, "legacy .language-panel remains in the DOM")
        if attributes.get("id", "").lower() in {"article-en", "article-es"}:
            add_error(errors, name, f"legacy dual-panel ID remains: {attributes['id']}")
        if element.tag == "script" and "language-switcher.js" in attributes.get("src", "").lower():
            add_error(errors, name, "old assets/language-switcher.js is still referenced")
        if (
            element.tag == "script"
            and attributes.get("type", "").lower() == "application/json"
            and ("schema.org" in element.text or '"@context"' in element.text)
        ):
            add_error(errors, name, "inactive localized JSON-LD remains as application/json")


def check_static_markup_cleanup(document: PageDocument, errors: list[str]) -> None:
    name = document.spec.relative_file
    for tag in sorted(VOID_ELEMENTS):
        if re.search(rf"</{re.escape(tag)}\s*>", document.source, re.IGNORECASE):
            add_error(errors, name, f"forbidden closing tag for void element </{tag}>")

    stale_language_badge = re.compile(r"\bEN\s*\|\s*ES\b", re.IGNORECASE)
    for element in document.elements():
        if "guide-card-meta" in class_tokens(element.attributes) and stale_language_badge.search(element.text):
            add_error(errors, name, f"stale EN | ES label remains in guide card: {element.text!r}")
        category = element.attributes.get("data-category", "")
        if category and stale_language_badge.search(category):
            add_error(errors, name, f"stale EN | ES data-category remains: {category!r}")

    if document.spec.language == "es":
        english_categories = {"opening story", "travel journal", "places"}
        for element in document.elements():
            category = element.attributes.get("data-category", "").strip().lower()
            if category in english_categories:
                add_error(errors, name, f"Spanish data-category remains English: {category!r}")

    versioned_assets = {
        "assets/language-switcher.css",
        "assets/guide-shell.css",
        "assets/adaptive-nav.js",
    }
    for element in document.elements():
        reference = element.attributes.get("href") or element.attributes.get("src") or ""
        split = urlsplit(reference)
        if split.path.lstrip("/") not in versioned_assets:
            continue
        if split.query != f"v={EXPECTED_ASSET_VERSION}":
            add_error(
                errors,
                name,
                f"changed asset has stale cache version: {reference!r}",
            )


def json_objects(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from json_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from json_objects(child)


def identity_url(value: Any) -> str | None:
    if isinstance(value, str):
        return canonicalise_public_url(value)
    if isinstance(value, dict) and isinstance(value.get("@id"), str):
        return canonicalise_public_url(value["@id"])
    return None


def check_jsonld(
    document: PageDocument,
    root: Path,
    errors: list[str],
    checked_references: set[tuple[str, str]],
) -> None:
    name = document.spec.relative_file
    scripts = [
        element
        for element in document.elements("script")
        if element.attributes.get("type", "").lower() == "application/ld+json"
    ]
    if len(scripts) != 1:
        add_error(errors, name, f"expected one active JSON-LD block, found {len(scripts)}")
        return
    try:
        payload = json.loads(scripts[0].text)
    except json.JSONDecodeError as exc:
        add_error(errors, name, f"invalid JSON-LD: {exc}")
        return

    objects = list(json_objects(payload))
    languages = [obj.get("inLanguage") for obj in objects if "inLanguage" in obj]
    expected_language = REGIONAL_LANGUAGE[document.spec.language]
    if not languages:
        add_error(errors, name, "JSON-LD has no inLanguage")
    elif any(language != expected_language for language in languages):
        add_error(errors, name, f"JSON-LD languages are {languages}, expected only {expected_language!r}")

    roots: list[dict[str, Any]]
    if isinstance(payload, dict) and isinstance(payload.get("@graph"), list):
        roots = [item for item in payload["@graph"] if isinstance(item, dict)]
    elif isinstance(payload, dict):
        roots = [payload]
    elif isinstance(payload, list):
        roots = [item for item in payload if isinstance(item, dict)]
    else:
        roots = []
    primary = [
        obj
        for obj in roots
        if obj.get("@type")
        in {"Article", "WebPage", "CollectionPage", "LodgingBusiness", "WebSite"}
    ]
    if not primary:
        add_error(errors, name, "JSON-LD has no recognizable primary page entity")
    identity_found = False
    for obj in primary:
        values: list[str] = []
        if "url" in obj and isinstance(obj["url"], str):
            values.append(canonicalise_public_url(obj["url"]))
        if "mainEntityOfPage" in obj:
            found = identity_url(obj["mainEntityOfPage"])
            if found:
                values.append(found)
        if "@id" in obj and isinstance(obj["@id"], str):
            values.append(canonicalise_public_url(obj["@id"]))
        if document.spec.public_url in values:
            identity_found = True
        wrong = [value for value in values if value != document.spec.public_url]
        if wrong:
            add_error(errors, name, f"primary JSON-LD page URL(s) do not match canonical: {wrong}")
    if not identity_found:
        add_error(errors, name, "JSON-LD primary entity does not identify the self canonical URL")

    expected_locale = document.spec.language
    for obj in objects:
        object_type = obj.get("@type")
        for key in ("url", "item", "mainEntityOfPage", "@id"):
            value = identity_url(obj.get(key))
            if not value:
                continue
            target_spec = SPEC_BY_URL.get(value)
            if (
                target_spec
                and target_spec.language != expected_locale
                and object_type not in {"Organization", "WebSite", "Person"}
            ):
                add_error(
                    errors,
                    name,
                    f"JSON-LD {object_type or 'entity'} {key} crosses locale to {value}",
                )

        for key in ("image", "logo", "thumbnailUrl", "contentUrl"):
            values = obj.get(key)
            if isinstance(values, str):
                values = [values]
            if not isinstance(values, list):
                continue
            for value in values:
                if isinstance(value, str):
                    check_local_reference(
                        root,
                        document,
                        value,
                        f"JSON-LD {key}",
                        errors,
                        checked_references,
                    )


def srcset_values(value: str) -> list[str]:
    if value.lstrip().lower().startswith("data:"):
        return []
    result = []
    for candidate in value.split(","):
        url = candidate.strip().split(maxsplit=1)[0] if candidate.strip() else ""
        if url:
            result.append(url)
    return result


def check_local_reference(
    root: Path,
    document: PageDocument,
    reference: str,
    context: str,
    errors: list[str],
    checked_references: set[tuple[str, str]],
) -> None:
    resolved = resolved_public_url(document.spec.public_url, reference)
    if resolved is None:
        return
    fragment = unquote(urlsplit(urljoin(document.spec.public_url, reference)).fragment)
    key = (document.spec.relative_file, f"{resolved}#{fragment}")
    if key in checked_references:
        return
    checked_references.add(key)
    split = urlsplit(resolved)
    if split.netloc.lower() != urlsplit(ORIGIN).netloc.lower():
        return
    target = target_path(root, resolved)
    if target is None or not target.exists():
        add_error(errors, document.spec.relative_file, f"missing local {context}: {reference!r}")
        return

    if fragment and target.suffix.lower() in {".html", ".htm"}:
        try:
            target_source = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            add_error(errors, document.spec.relative_file, f"non-UTF-8 HTML target: {reference!r}")
            return
        target_parser = DocumentParser()
        target_parser.feed(target_source)
        ids = {element.attributes.get("id") for element in target_parser.elements}
        if fragment not in ids:
            add_error(
                errors,
                document.spec.relative_file,
                f"missing fragment target {fragment!r} in {reference!r}",
            )


def check_references(
    root: Path,
    document: PageDocument,
    errors: list[str],
    checked_references: set[tuple[str, str]],
) -> None:
    for element in document.elements():
        for attribute in ("src", "href", "poster"):
            value = element.attributes.get(attribute)
            if value:
                check_local_reference(
                    root,
                    document,
                    value,
                    f"<{element.tag}> {attribute}",
                    errors,
                    checked_references,
                )
        for attribute in ("srcset", "imagesrcset"):
            for value in srcset_values(element.attributes.get(attribute, "")):
                check_local_reference(
                    root,
                    document,
                    value,
                    f"<{element.tag}> {attribute}",
                    errors,
                    checked_references,
                )
        style = element.attributes.get("style", "")
        for _, value in CSS_URL_RE.findall(style):
            if value and not value.startswith("#"):
                check_local_reference(
                    root,
                    document,
                    value,
                    f"<{element.tag}> style url()",
                    errors,
                    checked_references,
                )

    for style in document.elements("style"):
        for _, value in CSS_URL_RE.findall(style.text):
            if value and not value.startswith("#"):
                check_local_reference(
                    root,
                    document,
                    value,
                    "inline CSS url()",
                    errors,
                    checked_references,
                )

    for prop in ("og:image", "og:image:secure_url"):
        for value in meta_values(document, "property", prop):
            check_local_reference(
                root, document, value, prop, errors, checked_references
            )
    for value in meta_values(document, "name", "twitter:image"):
        check_local_reference(
            root, document, value, "twitter:image", errors, checked_references
        )


def check_images(document: PageDocument, errors: list[str]) -> None:
    for image in document.elements("img"):
        src = image.attributes.get("src", "")
        if not src:
            continue
        if "alt" not in image.attributes:
            add_error(errors, document.spec.relative_file, f"image has no alt attribute: {src!r}")
        if not image.attributes.get("width") or not image.attributes.get("height"):
            add_error(errors, document.spec.relative_file, f"image has no width/height: {src!r}")


def check_internal_links(document: PageDocument, errors: list[str]) -> None:
    for anchor in document.elements("a"):
        href = anchor.attributes.get("href", "")
        resolved = resolved_public_url(document.spec.public_url, href)
        if resolved is None:
            continue
        split = urlsplit(resolved)
        if split.netloc.lower() != urlsplit(ORIGIN).netloc.lower():
            continue
        target = SPEC_BY_URL.get(resolved)
        if (
            target
            and not anchor.in_language_switcher
            and target.language != document.spec.language
        ):
            add_error(
                errors,
                document.spec.relative_file,
                f"internal link escapes {document.spec.language.upper()} locale: {href!r}",
            )


def check_auto_redirects(document: PageDocument, errors: list[str]) -> None:
    for meta in document.elements("meta"):
        if meta.attributes.get("http-equiv", "").lower() == "refresh":
            add_error(errors, document.spec.relative_file, "meta refresh is forbidden on indexable pages")
    script_source = "\n".join(element.text for element in document.elements("script"))
    for label, pattern in AUTO_REDIRECT_PATTERNS.items():
        if pattern.search(script_source):
            add_error(errors, document.spec.relative_file, f"forbidden {label} pattern in script")


def resolved_image_sequence(document: PageDocument) -> list[str | None]:
    values = []
    for element in document.elements():
        if element.tag == "img" and element.attributes.get("src"):
            values.append(resolved_public_url(document.spec.public_url, element.attributes["src"]))
        elif element.tag == "source" and element.attributes.get("srcset"):
            values.extend(
                resolved_public_url(document.spec.public_url, value)
                for value in srcset_values(element.attributes["srcset"])
            )
    return values


def check_pair_parity(
    en_document: PageDocument,
    es_document: PageDocument,
    errors: list[str],
) -> dict[str, Any]:
    pair_name = en_document.spec.filename
    heading_tags = {"h1", "h2", "h3", "h4", "h5", "h6"}
    en_headings = [element.tag for element in en_document.elements() if element.tag in heading_tags]
    es_headings = [element.tag for element in es_document.elements() if element.tag in heading_tags]
    if en_headings != es_headings:
        add_error(errors, f"pair {pair_name}", "heading-level sequence differs between EN and ES")

    count_tags = ("section", "article", "picture", "img", "ul", "ol", "li")
    counts: dict[str, dict[str, int]] = {}
    for tag in count_tags:
        en_count = len(en_document.elements(tag))
        es_count = len(es_document.elements(tag))
        counts[tag] = {"en": en_count, "es": es_count}
        if en_count != es_count:
            add_error(
                errors,
                f"pair {pair_name}",
                f"<{tag}> count differs: EN={en_count}, ES={es_count}",
            )

    en_images = resolved_image_sequence(en_document)
    es_images = resolved_image_sequence(es_document)
    if en_images != es_images:
        add_error(errors, f"pair {pair_name}", "resolved body image/srcset sequence differs")

    en_anchors = [anchor for anchor in en_document.elements("a") if not anchor.in_language_switcher]
    es_anchors = [anchor for anchor in es_document.elements("a") if not anchor.in_language_switcher]
    if len(en_anchors) != len(es_anchors):
        add_error(
            errors,
            f"pair {pair_name}",
            f"non-selector link count differs: EN={len(en_anchors)}, ES={len(es_anchors)}",
        )
    return {"counts": counts, "headings": len(en_headings), "images": len(en_images)}


def check_css_files(root: Path, errors: list[str]) -> None:
    origin_host = urlsplit(ORIGIN).netloc.lower()
    for css_path in root.rglob("*.css"):
        try:
            css = css_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            add_error(errors, css_path.relative_to(root).as_posix(), "CSS is not UTF-8")
            continue
        relative = css_path.relative_to(root).as_posix()
        css_url = f"{ORIGIN}/{relative}"
        for _, value in CSS_URL_RE.findall(css):
            value = value.strip()
            if not value or value.startswith("#") or urlsplit(value).scheme.lower() in IGNORED_SCHEMES:
                continue
            resolved = canonicalise_public_url(urljoin(css_url, value))
            if urlsplit(resolved).netloc.lower() != origin_host:
                continue
            target = target_path(root, resolved)
            if target is None or not target.exists():
                add_error(errors, relative, f"missing CSS url() target: {value!r}")


def check_sitemap(root: Path, errors: list[str]) -> dict[str, Any]:
    path = root / "sitemap.xml"
    if not path.exists():
        return {"present": False}
    try:
        tree = ElementTree.parse(path)
    except ElementTree.ParseError as exc:
        add_error(errors, "sitemap.xml", f"invalid XML: {exc}")
        return {"present": True, "valid": False}
    locs = []
    for url_element in tree.getroot():
        if url_element.tag.rsplit("}", 1)[-1] != "url":
            continue
        direct_locs = [
            (child.text or "").strip()
            for child in url_element
            if child.tag.rsplit("}", 1)[-1] == "loc"
        ]
        locs.extend(direct_locs)
    duplicates = sorted(value for value, count in collections.Counter(locs).items() if count > 1)
    actual = set(locs)
    if duplicates:
        add_error(errors, "sitemap.xml", f"duplicate loc entries: {duplicates}")
    if actual != EXPECTED_URLS or len(locs) != len(EXPECTED_URLS):
        missing = sorted(EXPECTED_URLS - actual)
        extra = sorted(actual - EXPECTED_URLS)
        add_error(
            errors,
            "sitemap.xml",
            f"expected exactly {len(EXPECTED_URLS)} canonical locs; missing={missing}, extra={extra}, count={len(locs)}",
        )
    return {"present": True, "count": len(locs), "duplicates": duplicates}


def check_404(root: Path, errors: list[str]) -> dict[str, Any]:
    path = root / "404.html"
    if not path.exists():
        return {"present": False}
    spec = PageSpec("en", "404.html", "404.html", f"{ORIGIN}/404.html", "404.html")
    document = parse_html(path, spec)
    robots = ",".join(meta_values(document, "name", "robots")).lower()
    if "noindex" not in robots:
        add_error(errors, "404.html", "must contain a noindex robots directive")
    spanish_hrefs = {
        element.attributes.get("data-es-href", "")
        for element in document.elements("a")
        if element.attributes.get("data-es-href")
    }
    expected_spanish_hrefs = {
        "/es/",
        "/es/#stay",
        "/es/#gallery",
        "/es/#reviews",
        "/es/tenerife-guide.html",
    }
    if not expected_spanish_hrefs.issubset(spanish_hrefs):
        add_error(
            errors,
            "404.html",
            f"Spanish recovery links are incomplete: {sorted(spanish_hrefs)}",
        )

    switcher_scripts = [
        element.attributes.get("src", "")
        for element in document.elements("script")
        if "language-switcher.js" in element.attributes.get("src", "")
    ]
    if switcher_scripts != [f"/assets/language-switcher.js?v={EXPECTED_ASSET_VERSION}"]:
        add_error(errors, "404.html", f"404 language runtime version is {switcher_scripts}")

    runtime_path = root / "assets" / "language-switcher.js"
    runtime_source = runtime_path.read_text(encoding="utf-8") if runtime_path.exists() else ""
    if "window.location.pathname" not in runtime_source or '"/es/"' not in runtime_source:
        add_error(errors, "404.html", "language runtime does not infer Spanish from /es/ paths")

    return {
        "present": True,
        "noindex": "noindex" in robots,
        "spanish_recovery_links": len(spanish_hrefs),
        "path_aware": "window.location.pathname" in runtime_source,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="static build root (defaults to the repository root)",
    )
    args = parser.parse_args(argv)
    root = args.root.expanduser().resolve()
    errors: list[str] = []
    report: dict[str, Any] = {
        "root": str(root),
        "pages": {},
        "pairs": {},
    }

    if not root.is_dir():
        report["errors"] = [f"build root does not exist or is not a directory: {root}"]
        report["valid"] = False
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1

    documents: dict[tuple[str, str], PageDocument] = {}
    expected_es_files = {f"es/{filename}" for filename in FILENAMES}
    actual_es_files = {
        path.relative_to(root).as_posix()
        for path in (root / "es").rglob("*.html")
    } if (root / "es").is_dir() else set()
    unexpected_es_files = sorted(actual_es_files - expected_es_files)
    if unexpected_es_files:
        add_error(errors, "es/", f"unexpected locale HTML files: {unexpected_es_files}")
    for spec in SPECS:
        path = root / spec.relative_file
        if not path.is_file():
            add_error(errors, spec.relative_file, "required locale page is missing")
            continue
        try:
            document = parse_html(path, spec)
        except UnicodeDecodeError as exc:
            add_error(errors, spec.relative_file, f"page is not UTF-8: {exc}")
            continue
        documents[(spec.language, spec.filename)] = document
        before = len(errors)
        check_document_basics(document, errors)
        check_legacy_locale_mechanisms(document, errors)
        check_static_markup_cleanup(document, errors)
        check_selector(document, errors)
        check_internal_links(document, errors)
        check_auto_redirects(document, errors)
        check_images(document, errors)
        checked_references: set[tuple[str, str]] = set()
        check_references(root, document, errors, checked_references)
        check_jsonld(document, root, errors, checked_references)
        report["pages"][spec.relative_file] = {
            "language": spec.language,
            "canonical": spec.public_url,
            "h1_count": len(document.elements("h1")),
            "image_count": len(document.elements("img")),
            "errors": len(errors) - before,
        }

    for filename in FILENAMES:
        en_document = documents.get(("en", filename))
        es_document = documents.get(("es", filename))
        if en_document and es_document:
            report["pairs"][filename] = check_pair_parity(en_document, es_document, errors)

    check_css_files(root, errors)
    report["sitemap"] = check_sitemap(root, errors)
    report["not_found"] = check_404(root, errors)
    report["errors"] = errors
    report["error_count"] = len(errors)
    report["valid"] = not errors
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
