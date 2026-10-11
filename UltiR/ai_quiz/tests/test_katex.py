"""KaTeX is shipped with the module: the files are the released ones, they are served by the tool, and no page
points at any other host."""

import hashlib
import re
from pathlib import Path

import pytest

from .conftest import BASE

MODULE_DIR = Path(__file__).resolve().parents[1]
KATEX = MODULE_DIR / "static" / "vendor" / "katex"
ASSETS = f"{BASE}/assets"

# SHA-256 of the files of the npm package katex 0.19.0, as copied on 2026-10-10.
RELEASED = {
    "katex.min.js": "103a53763cc033bba8d175bf3f0ba597c3505c9b6747dd3f2c7bc2a6bfcc8ae7",
    "katex.min.css": "d4ab5b8ee16989b070cdb0ea24bd6ad48fc8df1b787f280f29d3ae4f959f2c00",
    "LICENSE": "766ccc1f306c885aa45542a9846bbd0a505b27a0374f146778171c2254ce18e3",
}
FONTS = sorted(p.name for p in (KATEX / "fonts").glob("*"))


def test_the_shipped_files_are_the_released_ones_unchanged():
    assert {name: hashlib.sha256((KATEX / name).read_bytes()).hexdigest() for name in RELEASED} == RELEASED
    assert 'version:"0.19.0"' in (KATEX / "katex.min.js").read_text(encoding="utf-8")


def test_the_licence_is_shipped_and_served(client):
    response = client.get(f"{ASSETS}/vendor/katex/LICENSE")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "The MIT License" in response.text and "Khan Academy" in response.text


@pytest.mark.parametrize("name, content_type", [
    ("math.js", "text/javascript"),
    ("vendor/katex/katex.min.js", "text/javascript"),
    ("vendor/katex/katex.min.css", "text/css"),
])
def test_the_formula_files_are_served_by_the_tool(client, name, content_type):
    response = client.get(f"{ASSETS}/{name}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(content_type)


def test_every_font_the_stylesheet_asks_for_first_is_shipped_and_served(client):
    css = (KATEX / "katex.min.css").read_text(encoding="utf-8")
    asked_first = sorted(set(re.findall(r"src:url\(fonts/([\w-]+\.woff2)\)", css)))

    assert len(FONTS) == 20 and asked_first == FONTS            # woff2 comes first in every list, and all are here
    for name in FONTS:
        response = client.get(f"{ASSETS}/vendor/katex/fonts/{name}")
        assert response.status_code == 200, name
        assert response.headers["content-type"] == "font/woff2"
        assert response.content[:4] == b"wOF2"


@pytest.mark.parametrize("name", [
    "vendor/katex/fonts/KaTeX_Main-Regular.woff",       # older formats are not shipped
    "vendor/katex/fonts/KaTeX_Main-Regular.ttf",
    "vendor/katex/README.md",
    "vendor/katex/fonts/",
    "vendor/katex/",
    "vendor/katex/fonts/../../../app.js/../../lti_provider.py",
    "vendor/katex/fonts/..%2F..%2F..%2F..%2Fconfig.py",
    "vendor/other/katex.min.js",
])
def test_nothing_else_under_the_vendor_folder_is_served(client, name):
    assert client.get(f"{ASSETS}/{name}").status_code == 404


def test_the_stylesheet_and_the_script_name_no_other_host_to_load_from():
    css = (KATEX / "katex.min.css").read_text(encoding="utf-8")

    assert not re.search(r"url\(\s*['\"]?(?:https?:)?//", css)
    assert "@import" not in css
    assert set(re.findall(r"url\(([^)]+)\)", css)) <= {f"fonts/{name[:-1]}{ext}" for name in FONTS for ext in ("2", "", "x")} | {
        f"fonts/{name[:-6]}.ttf" for name in FONTS}


@pytest.mark.parametrize("page", ["instructor.html", "student.html", "info.html"])
def test_a_page_loads_scripts_styles_and_fonts_from_the_tool_only(page):
    html = (MODULE_DIR / "static" / page).read_text(encoding="utf-8")

    addresses = re.findall(r"""(?:src|href)=["']([^"']+)["']""", html)
    assert addresses
    assert [a for a in addresses if not (a.startswith("/lti/ai-quiz/") or a.startswith("#"))] == []


@pytest.mark.parametrize("page", ["instructor.html", "student.html"])
def test_the_pages_that_show_questions_load_katex_before_the_page_script(page):
    html = (MODULE_DIR / "static" / page).read_text(encoding="utf-8")

    scripts = re.findall(r'<script src="/lti/ai-quiz/assets/([^"]+)"', html)
    assert scripts.index("vendor/katex/katex.min.js") < scripts.index("math.js") < len(scripts) - 1
    assert scripts.index("app.js") < scripts.index("math.js")
    assert "/lti/ai-quiz/assets/vendor/katex/katex.min.css" in html


def test_the_public_info_page_names_katex_and_links_to_the_licence_the_tool_serves(client):
    html = (MODULE_DIR / "static" / "info.html").read_text(encoding="utf-8")
    strings = client.get(f"{ASSETS}/strings.js").text

    link = re.search(r'<a href="([^"]+)" data-i18n="info_software_licence">', html)
    assert link and link.group(1) == "/lti/ai-quiz/assets/vendor/katex/LICENSE"
    assert client.get(link.group(1)).status_code == 200
    assert strings.count("KaTeX 0.19.0") == 2                  # said in both languages
    assert 'data-i18n="info_reading_text"' in html


# ── How KaTeX can put a style into the page ─────────────────────────────────
# math.js keeps the pages clean under a policy without inline styles by catching one thing while a
# formula is drawn: Element.setAttribute("style", ...). That is enough only as long as every style
# KaTeX writes outside an element's style object goes through that function. The checks below state
# what was true of KaTeX 0.19.0. After an update of the shipped files, a failure here means: look
# at how the new version writes styles before trusting math.js with it.

OTHER_WAYS_TO_WRITE_A_STYLE = [
    "setAttributeNS",               # an attribute set without Element.setAttribute
    "createAttribute", "setNamedItem",
    "innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "DOMParser", "createContextualFragment",   # markup
    'createElement("style")', "createElement('style')", "insertRule", "adoptedStyleSheets", "CSSStyleSheet",   # style sheets
    ".cssText", "attributeStyleMap",
]


def style_writes(script: str) -> dict:
    """What a KaTeX script does that matters to math.js: {"literal": n, "other": [names found]}."""
    return {
        "literal": len(re.findall(r"""\.setAttribute\(\s*["']style["']""", script)),
        "other": [way for way in OTHER_WAYS_TO_WRITE_A_STYLE if way in script],
    }


def test_katex_writes_style_attributes_only_in_the_ways_math_js_catches():
    script = (KATEX / "katex.min.js").read_text(encoding="utf-8")

    assert style_writes(script) == {"literal": 3, "other": []}
    # elements come from createElement and createElementNS and from nowhere else; attributes are set on them directly
    assert set(re.findall(r"createElement\(([^)]{1,12})\)", script)) == {'"span"', '"img"', "e"}
    assert len(re.findall(r"createElementNS\(", script)) == 5


@pytest.mark.parametrize("script, found", [
    ('n.setAttribute("style","border: 1px")', {"literal": 1, "other": []}),
    ("n.setAttribute( 'style', x)", {"literal": 1, "other": []}),
    ('n.setAttribute("width","3")', {"literal": 0, "other": []}),
    ('n.setAttributeNS(null,"style",x)', {"literal": 0, "other": ["setAttributeNS"]}),
    ('e.innerHTML="<span style=\\"color:red\\">"', {"literal": 0, "other": ["innerHTML"]}),
    ('e.insertAdjacentHTML("beforeend",m)', {"literal": 0, "other": ["insertAdjacentHTML"]}),
    ('const s=document.createElement("style");s.sheet.insertRule(r)', {"literal": 0, "other": ['createElement("style")', "insertRule"]}),
    ('e.style.cssText="width:1em"', {"literal": 0, "other": [".cssText"]}),
    ("const a=document.createAttribute('style');e.attributes.setNamedItem(a)", {"literal": 0, "other": ["createAttribute", "setNamedItem"]}),
    ("e.style.width=w", {"literal": 0, "other": []}),                   # through the style object: allowed by any policy
])
def test_the_check_on_katex_itself_finds_what_it_should(script, found):
    assert style_writes(script) == found


def test_math_js_draws_through_katex_render_and_never_through_markup():
    source = (MODULE_DIR / "static" / "math.js").read_text(encoding="utf-8")
    code = re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.DOTALL)        # without its comments

    assert code.count("katex.render(") == 1
    assert not [way for way in ("renderToString", "innerHTML", "outerHTML", "insertAdjacentHTML") if way in code]
    assert "trust: false" in code
    # the one browser function it replaces is put back in a `finally`, so also when drawing fails
    assert re.search(r"try\s*\{\s*draw\(\);\s*\}\s*finally\s*\{\s*Element\.prototype\.setAttribute = setAttribute;\s*\}", code)
