"""
Build the clickable SVG diagrams used by the Anatomy Explorer.

Downloads the open-licensed source art from Wikimedia Commons, tags every
shape that belongs to a structure in ../catalog.json with

    data-s="<structure id>"   data-side="R" | "L" | "M" | "auto"

(patient's side; "auto" is resolved in the browser from the shape's
position relative to the figure's midline) and writes four files to
../static/svg/:

    muscles_anterior.svg   muscles_posterior.svg
    bones_anterior.svg     bones_posterior.svg

Sources (attribution is shown on the app's info page):
  - "Muscles front and back.svg" — OpenStax & Nefronus, CC BY-SA 4.0
  - "Human skeleton front en.svg" / "Human skeleton back en.svg" —
    Mariana Ruiz Villarreal (LadyofHats), public domain

Usage:  python UltiR/anatomy/tools/build_svgs.py
Sources are cached in tools/_src/. If the download fails (e.g. a local
certificate problem), save the three files there by hand under the names
given in SOURCES.
To add a structure: add it to catalog.json, then map its shapes below.
"""

import copy
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

from lxml import etree

TOOLS_DIR = Path(__file__).parent
APP_DIR = TOOLS_DIR.parent
CACHE_DIR = TOOLS_DIR / "_src"
OUT_DIR = APP_DIR / "static" / "svg"

SOURCES = {
    "muscles": ("https://upload.wikimedia.org/wikipedia/commons/e/ef/Muscles_front_and_back.svg",
                "muscles_front_and_back.svg"),
    "skel_front": ("https://upload.wikimedia.org/wikipedia/commons/c/ca/Human_skeleton_front_en.svg",
                   "human_skeleton_front_en.svg"),
    "skel_back": ("https://upload.wikimedia.org/wikipedia/commons/4/4e/Human_skeleton_back_en.svg",
                  "human_skeleton_back_en.svg"),
}
# The back skeleton has no ids, so its bones are mapped by <g> position.
# If Commons serves a new revision these indices may no longer match.
SKEL_BACK_SHA256 = "a8d722849589fdcde4e1810ec0adff598e5cfc5fd4c7c439170b4a1a2a216163"

SVG = "http://www.w3.org/2000/svg"
XLINK = "http://www.w3.org/1999/xlink"
DROP_NS = ("http://www.inkscape.org/namespaces/inkscape",
           "http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd")
SHAPES = {f"{{{SVG}}}{t}" for t in ("path", "polygon", "polyline", "ellipse", "circle", "rect")}

# ── Muscle mapping (OpenStax figure) ──────────────────────────────────────────
# Only the patient's right half of each figure is drawn; the left half is a
# mirrored <use>. Shapes are therefore tagged R and their mirror copies L.
MUSCLE_PATHS = {
    "frontalis": ["path1245"], "occipitalis": ["path1191"], "temporalis": ["path1274"],
    "orbicularis_oculi": ["path1172", "path1202"], "orbicularis_oris": ["path1476"],
    "zygomaticus_major": ["path1419"], "masseter": ["path1326"], "nasalis": ["path1612"],
    "sternocleidomastoid": ["path919", "path1238"], "sternohyoid": ["path1751"],
    "splenius_capitis": ["path1327"], "trapezius": ["path1211", "path1268"],
    "pectoralis_major": ["path847"], "serratus_anterior": ["path968"],
    "rectus_abdominis": ["path970", "path974", "path978", "path1012"],
    "external_oblique": ["path950"], "latissimus_dorsi": ["path2220"],
    "infraspinatus": ["path2085"], "teres_major": ["path2163"], "rhomboid_major": ["path2115"],
    "deltoid": ["path861", "path1452"], "biceps_brachii": ["path881"], "brachialis": ["path948"],
    "triceps_brachii": ["path1542", "path1513"], "brachioradialis": ["path908"],
    "pronator_teres": ["path928"], "flexor_carpi_radialis": ["path998"],
    "palmaris_longus": ["path1065"], "flexor_carpi_ulnaris": ["path1080"],
    "flexor_digitorum_superficialis": ["path1109"], "extensor_digitorum": ["path1725"],
    "extensor_carpi_ulnaris": ["path1697"],
    "thenar": ["path1115", "path1129", "path1101", "path1047", "path1017"],
    "hypothenar": ["path1200", "path1257", "path1228", "path1186"],
    "gluteus_maximus": ["path2744"], "gluteus_medius": ["path2024"],
    "rectus_femoris": ["path1366"], "sartorius": ["path1337"], "adductors": ["path1440"],
    "gracilis": ["path2990"], "vastus_lateralis": ["path2962"], "biceps_femoris": ["path2803"],
    "semitendinosus": ["path2900"], "semimembranosus": ["path2931"],
    "gastrocnemius": ["path1734", "path3075", "path3022"], "soleus": ["path3254", "path3216"],
    "tibialis_anterior": ["path1790"], "extensor_digitorum_longus": ["path1848"],
    "fibularis_longus": ["path1887"],
}
# path1554 is one shape lying under rectus femoris; its visible lateral part is
# vastus lateralis and its medial part vastus medialis. Split it at the centre
# of rectus femoris (x in the path's local coordinates).
VASTI_PATH, VASTI_SPLIT_X = "path1554", 38.5
# path861 (deltoid) also fills the clavicular part of pectoralis major; the
# stroke path879 is the deltopectoral border. Split path861 along that curve:
# the polygon below closes the curve around the lateral (deltoid) side.
DELTOID_PATH, DELTOPECTORAL_LINE = "path861", "path879"
DELTOID_SIDE_TAIL = [(47, -215), (47, -230), (-30, -230), (-30, -150), (13, -150), (13, -170)]

# ── Bone mapping, front skeleton (named groups; Right/Left = patient's side) ──
BONES_FRONT = {
    "Cranium": ("cranium", "M"), "g1297": ("cranium", "M"), "Mandible": ("mandible", "M"),
    "CervicalVertebrae": ("cervical_vertebrae", "M"), "ThoracicVertebrae": ("thoracic_vertebrae", "M"),
    "LumbarVertebrae": ("lumbar_vertebrae", "M"), "Sacrum": ("sacrum", "M"), "Coccyx": ("coccyx", "M"),
    "Sternum": ("sternum", "M"), "Manubrium": ("sternum", "M"), "g801": ("sternum", "M"),
    "g845": ("ribs", "auto"), "g1609": ("ribs", "auto"),
    "ClavicleRight": ("clavicle", "R"), "ClavicleLeft": ("clavicle", "L"),
    "Scapula": ("scapula", "auto"),
    "HumerusRight": ("humerus", "R"), "HumerusLeft": ("humerus", "L"),
    "RadiusRight": ("radius", "R"), "RadiusLeft": ("radius", "L"),
    "UlnaRight": ("ulna", "R"), "UlnaLeft": ("ulna", "L"),
    "CarpalsRight": ("carpals", "R"), "CarpalsLeft": ("carpals", "L"),
    "MetacarpalsRight": ("metacarpals", "R"), "MetacarpalsLeft": ("metacarpals", "L"),
    "PhalangesRight": ("phalanges_hand", "R"), "PhalangesLeft": ("phalanges_hand", "L"),
    "PelvicGirdle": ("hip_bone", "auto"), "g447": ("hip_bone", "auto"),
    "g3760": ("femur", "R"), "FemurLeft": ("femur", "L"),
    "PatellaRight": ("patella", "R"), "PatellaLeft": ("patella", "L"),
    "TibiaRight": ("tibia", "R"), "TibiaLeft": ("tibia", "L"),
    "FibulaRight": ("fibula", "R"), "FibulaLeft": ("fibula", "L"),
    "TarsalsRight": ("tarsals", "R"), "TarsalsLeft": ("tarsals", "L"),
    "MetatarsalsRight": ("metatarsals", "R"), "MetatarsalsLeft": ("metatarsals", "L"),
    "PhalangesFootRight": ("phalanges_foot", "R"), "PhalangesFootLeft": ("phalanges_foot", "L"),
}
FRONT_DROP = ("layer1", "layer4")  # labels, background

# ── Bone mapping, back skeleton (index of <g> in document order) ──────────────
# Posterior view: the viewer's left is the patient's left. Applied in order,
# so later (deeper) groups override earlier ones.
_LUMBAR = [151, 153, 155, 158, 162]
_THORACIC = [165, 169, 173, 175, 177, 178, 180, 182, 184, 186, 189, 192]
BONES_BACK = [
    (96, "cranium", "M"), (97, "mandible", "M"), (101, "mandible", "M"), (102, "mandible", "M"),
    (150, "cervical_vertebrae", "M"),
    *[(g, "lumbar_vertebrae", "M") for g in _LUMBAR],
    *[(g, "thoracic_vertebrae", "M") for g in _THORACIC],
    (148, "sacrum", "M"), (94, "coccyx", "M"),
    (108, "ribs", "auto"), (109, "clavicle", "auto"), (138, "scapula", "auto"),
    (202, "hip_bone", "auto"),
    (5, "humerus", "L"), (50, "humerus", "R"),
    (46, "ulna", "L"), (47, "radius", "L"), (52, "radius", "R"), (54, "ulna", "R"),
    (6, "phalanges_hand", "L"), (25, "carpals", "L"),
    *[(g, "metacarpals", "L") for g in (17, 18, 39, 41, 44)],
    (56, "phalanges_hand", "R"),
    *[(g, "carpals", "R") for g in (57, 58, 59, 61, 73, 74, 75, 76)],
    *[(g, "metacarpals", "R") for g in (80, 81, 82, 83, 84)],
    (87, "femur", "L"), (90, "femur", "R"),
    (204, "tibia", "L"), (207, "fibula", "L"), (208, "tibia", "R"), (211, "fibula", "R"),
    (212, "phalanges_foot", "R"), (219, "tarsals", "R"),
    (224, "phalanges_foot", "L"), (231, "tarsals", "L"),
]
BACK_KEEP_G = 3  # the skeleton group; everything else at root level is labels

# viewBox per output, in the source's root user units (centred on the midline)
VIEWBOX = {
    "muscles_anterior": None, "muscles_posterior": None,
    "bones_anterior": None, "bones_posterior": None,
}
VIEWBOX_FILE = TOOLS_DIR / "viewboxes.json"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fetch(key: str) -> Path:
    url, name = SOURCES[key]
    CACHE_DIR.mkdir(exist_ok=True)
    path = CACHE_DIR / name
    if not path.exists():
        req = urllib.request.Request(url, headers={"User-Agent": "UltiR-anatomy-build/1.0"})
        path.write_bytes(urllib.request.urlopen(req, timeout=60).read())
    return path


def _parse(key: str) -> etree._ElementTree:
    return etree.parse(str(_fetch(key)), etree.XMLParser(huge_tree=True, remove_comments=True))


def _clean(root):
    """Drop editor metadata and namespaced attributes."""
    for el in list(root.iter()):
        if not isinstance(el.tag, str):
            continue
        q = etree.QName(el)
        if q.namespace in DROP_NS or q.localname in ("metadata", "title"):
            el.getparent().remove(el)
            continue
        for attr in list(el.attrib):
            if etree.QName(attr).namespace in DROP_NS:
                del el.attrib[attr]


def _round_coords(root, digits: int):
    num = re.compile(r"-?\d+\.\d{%d,}" % (digits + 1))
    fmt = lambda m: f"{float(m.group()):.{digits}f}".rstrip("0").rstrip(".")
    for el in root.iter():
        if isinstance(el.tag, str):
            for attr in ("d", "points", "transform"):
                if attr in el.attrib:
                    el.attrib[attr] = num.sub(fmt, el.attrib[attr])


def _cubic_points(d: str, steps: int = 12) -> list:
    """Sample a path made of one relative moveto and relative cubic curves."""
    nums = [float(n) for n in re.findall(r"-?\d*\.?\d+(?:e-?\d+)?", d)]
    x, y = nums[0], nums[1]
    pts = [(x, y)]
    for k in range(2, len(nums), 6):
        c1x, c1y, c2x, c2y, ex, ey = (nums[k + i] + (x if i % 2 == 0 else y) for i in range(6))
        for t in range(1, steps + 1):
            t /= steps
            mt = 1 - t
            pts.append((mt**3 * x + 3 * mt**2 * t * c1x + 3 * mt * t**2 * c2x + t**3 * ex,
                        mt**3 * y + 3 * mt**2 * t * c1y + 3 * mt * t**2 * c2y + t**3 * ey))
        x, y = ex, ey
    return pts


def _split_with_clip(defs, el, keep_sid: str, other_sid: str, polygon: list, clip_id: str):
    """Clip el to polygon (tagged keep_sid) and add a copy clipped to the
    complement (tagged other_sid). Polygon is in el's local coordinates."""
    poly = "M " + " L ".join(f"{x:.3f},{y:.3f}" for x, y in polygon) + " Z"
    inside = etree.SubElement(defs, f"{{{SVG}}}clipPath", id=clip_id, clipPathUnits="userSpaceOnUse")
    etree.SubElement(inside, f"{{{SVG}}}path", d=poly)
    outside = etree.SubElement(defs, f"{{{SVG}}}clipPath", id=clip_id + "-not", clipPathUnits="userSpaceOnUse")
    etree.SubElement(outside, f"{{{SVG}}}path", d="M -1000,-1000 H 1000 V 1000 H -1000 Z " + poly,
                     **{"clip-rule": "evenodd"})
    other = copy.deepcopy(el)
    other.set("id", f"{el.get('id')}-{other_sid}")
    other.set("clip-path", f"url(#{clip_id}-not)")
    _tag(other, other_sid, "R")
    el.set("clip-path", f"url(#{clip_id})")
    _tag(el, keep_sid, "R")
    el.addnext(other)


def _tag(el, sid: str, side: str):
    """Tag a shape, or every shape inside a group."""
    targets = [el] if el.tag in SHAPES else [s for s in el.iter() if s.tag in SHAPES]
    for s in targets:
        s.set("data-s", sid)
        s.set("data-side", side)


def _expand_uses(root):
    """Replace every <use> outside <defs> with a real copy, so that each
    mirrored shape is its own element. Mirror copies get data-mirror."""
    ids = {el.get("id"): el for el in root.iter() if isinstance(el.tag, str) and el.get("id")}
    while True:
        uses = [u for u in root.iter(f"{{{SVG}}}use")
                if not any(etree.QName(a).localname in ("defs", "clipPath") for a in u.iterancestors())]
        if not uses:
            return
        for u in uses:
            ref = ids[(u.get(f"{{{XLINK}}}href") or u.get("href")).lstrip("#")]
            g = etree.Element(f"{{{SVG}}}g")
            transform = u.get("transform", "")
            x, y = float(u.get("x", 0)), float(u.get("y", 0))
            if x or y:
                transform += f" translate({x},{y})"
            if transform.strip():
                g.set("transform", transform.strip())
            if "matrix(-1" in transform.replace(" ", ""):
                g.set("data-mirror", "1")
            if u.get("style"):
                g.set("style", u.get("style"))
            clone = copy.deepcopy(ref)
            for el in clone.iter():
                if isinstance(el.tag, str) and "id" in el.attrib:
                    del el.attrib["id"]
            g.append(clone)
            u.getparent().replace(u, g)


def _resolve_mirror_sides(root):
    """Shapes tagged R inside an odd number of mirror groups become L."""
    for s in root.iter():
        if not isinstance(s.tag, str) or s.get("data-side") != "R":
            continue
        flips = sum(1 for a in s.iterancestors() if a.get("data-mirror") == "1")
        if flips % 2:
            s.set("data-side", "L")


def _finish(root, name: str, view: str, digits: int):
    for attr in ("width", "height"):
        root.attrib.pop(attr, None)
    vb = VIEWBOX.get(name)
    if vb:
        root.set("viewBox", " ".join(str(v) for v in vb))
    root.set("data-view", view)
    root.set("preserveAspectRatio", "xMidYMid meet")
    for el in root.iter():
        if isinstance(el.tag, str) and el.get("data-mirror"):
            del el.attrib["data-mirror"]
    _round_coords(root, digits)
    etree.cleanup_namespaces(root)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{name}.svg"
    out.write_bytes(etree.tostring(root, xml_declaration=False, encoding="utf-8"))
    tagged = {s.get("data-s") for s in root.iter() if isinstance(s.tag, str) and s.get("data-s")}
    print(f"  {out.name}: {out.stat().st_size // 1024} KB, {len(tagged)} structures")
    return tagged


# ── Builders ──────────────────────────────────────────────────────────────────

def build_muscles():
    tree = _parse("muscles")
    root = tree.getroot()
    _clean(root)
    byid = {el.get("id"): el for el in root.iter() if isinstance(el.tag, str) and el.get("id")}
    midline = {"orbicularis_oris", "nasalis"}
    for sid, pids in MUSCLE_PATHS.items():
        for pid in pids:
            _tag(byid[pid], sid, "M" if sid in midline else "R")

    defs = root.find(f"{{{SVG}}}defs")
    border = _cubic_points(byid[DELTOPECTORAL_LINE].get("d"))
    _split_with_clip(defs, byid[DELTOID_PATH], "deltoid", "pectoralis_major",
                     border + DELTOID_SIDE_TAIL, "clip-deltoid")

    # Split the combined vasti shape with two clip paths
    vasti = byid[VASTI_PATH]
    for sid, x0, x1 in (("vastus_lateralis", -1000, VASTI_SPLIT_X), ("vastus_medialis", VASTI_SPLIT_X, 1000)):
        cp = etree.SubElement(defs, f"{{{SVG}}}clipPath", id=f"clip-{sid}", clipPathUnits="userSpaceOnUse")
        etree.SubElement(cp, f"{{{SVG}}}rect", x=str(x0), y="-1000", width=str(x1 - x0), height="2000")
    medial = copy.deepcopy(vasti)
    medial.set("id", "vasti-medial")
    medial.set("clip-path", "url(#clip-vastus_medialis)")
    _tag(medial, "vastus_medialis", "R")
    vasti.set("clip-path", "url(#clip-vastus_lateralis)")
    _tag(vasti, "vastus_lateralis", "R")
    vasti.addnext(medial)

    _expand_uses(root)
    _resolve_mirror_sides(root)

    tagged = set()
    for view, drop in (("anterior", ("g3613", "path1379", "path1381")), ("posterior", ("g4116",))):
        r = copy.deepcopy(root)
        for el in list(r.iter()):
            if isinstance(el.tag, str) and el.get("id") in drop:
                el.getparent().remove(el)
        tagged |= _finish(r, f"muscles_{view}", view, 3)
    return tagged


def build_bones_front():
    root = _parse("skel_front").getroot()
    for el in list(root.iter()):
        if isinstance(el.tag, str) and el.get("id") in FRONT_DROP:
            el.getparent().remove(el)
    _clean(root)
    byid = {el.get("id"): el for el in root.iter() if isinstance(el.tag, str) and el.get("id")}
    for gid, (sid, side) in BONES_FRONT.items():
        _tag(byid[gid], sid, side)
    return _finish(root, "bones_anterior", "anterior", 2)


def build_bones_back():
    path = _fetch("skel_back")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if SKEL_BACK_SHA256 and digest != SKEL_BACK_SHA256:
        sys.exit(f"Back skeleton source changed (sha256 {digest}); re-check BONES_BACK indices.")
    root = _parse("skel_back").getroot()
    groups = [el for el in root.iter(f"{{{SVG}}}g")]
    for idx, sid, side in BONES_BACK:
        _tag(groups[idx], sid, side)
    keep = groups[BACK_KEEP_G]
    for child in list(root):
        if child is not keep and etree.QName(child).localname != "defs":
            root.remove(child)
    _clean(root)
    return _finish(root, "bones_posterior", "posterior", 2)


def main():
    if VIEWBOX_FILE.exists():
        VIEWBOX.update(json.loads(VIEWBOX_FILE.read_text()))
    catalog = json.loads((APP_DIR / "catalog.json").read_text(encoding="utf-8"))
    known = {s["id"] for s in catalog["structures"]}
    print("Building SVGs into", OUT_DIR)
    tagged = build_muscles() | build_bones_front() | build_bones_back()
    missing_in_catalog = tagged - known
    never_drawn = known - tagged
    if missing_in_catalog:
        print("  WARNING: tagged but not in catalog.json:", sorted(missing_in_catalog))
    if never_drawn:
        print("  WARNING: in catalog.json but not in any diagram:", sorted(never_drawn))


if __name__ == "__main__":
    main()
