"""Base-map tint for a frame: the Detuned house style rendered once, for every consumer to draw under its data.

Sea floor as a LINEAR gradient on the region's depth scale (shelf 0 to 1,300 m or ocean 0 to 7,000 m, by `bathymetry`
in regions.json); land as a LINEAR gradient too (0 to 2,000 m, since 2026-11-15; stepped classes before), cross-blended by
climate zone (Beck and others 2023 weights from the demo texture); both in the light and the dark theme. The stops are the
ones in preview/palette.js (tests keep them in step).

Writes data/out/<region>/regional_base_light.png and regional_base_dark.png (RGB, the regional LOD grid, the frame's
extent) and records them in manifest.json under "base". Consumers (Bedrock, source-to-sink, ds-sand-from-the-source, Sheet,
SubScout figures) draw that image with an identity transform, their data over it, then the hillshade; they never colour
Relief's bands or heights themselves.

Usage: uv run python scripts/base_tint.py <region> [<region> ...]
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]

# Mirrors preview/palette.js (ZPAL, DETUNED_SEA, DETUNED_OCEAN, LB, SB, OCEAN_SB). Change both together.
LB, LMAX = [0, 50, 150, 300, 600, 1000, 1500, 2000], 2000
SB, SMAX = [0, 20, 50, 100, 200, 500, 1000], 1300
OCEAN_SB, OCEAN_MAX = [0, 200, 1000, 2000, 3000, 4000, 5000, 6000, 7000], 7000
ZPAL = {
    "light": {
        "temperate": ["#d6e8b8", "#c6dea0", "#bad38f", "#cbcf92", "#d9c897", "#ccb8a0", "#d8d0c6", "#efece8"],
        "boreal": ["#a9c7a6", "#97bb98", "#8aae8c", "#93a98b", "#a8ad96", "#ccb8a0", "#d8d0c6", "#efece8"],
        "tundra": ["#e0e3dc", "#d6dad2", "#cdd1c9", "#c6c8c0", "#c4c0b6", "#ccb8a0", "#d8d0c6", "#efece8"],
        "arid": ["#efe2c2", "#e9d6ac", "#e1c695", "#d6b382", "#c9a077", "#ccb8a0", "#d8d0c6", "#efece8"],
    },
    "dark": {
        "temperate": ["#46572f", "#4c5d33", "#536237", "#5d633b", "#665f42", "#655d50", "#85807a", "#aaa6a1"],
        "boreal": ["#2c4232", "#304836", "#354d39", "#3f513e", "#4e5547", "#655d50", "#85807a", "#aaa6a1"],
        "tundra": ["#55595a", "#585b5b", "#5b5d5c", "#5e5e5b", "#615d57", "#655d50", "#85807a", "#aaa6a1"],
        "arid": ["#5e533c", "#665a3f", "#6c5c40", "#6e5a43", "#6a5747", "#655d50", "#85807a", "#aaa6a1"],
    },
}
DETUNED_SEA = {
    "light": ["#e8f0f2", "#cfe1e6", "#aacdd8", "#7eb0c5", "#5891ae", "#3a6d94", "#264b73", "#162b50"],
    "dark": ["#3a8aa2", "#2f7690", "#25647d", "#1c526b", "#144157", "#0e3045", "#092336", "#06172a"],
}
DETUNED_OCEAN = {
    "light": ["#e2f4f9", "#bfe2ed", "#83bddc", "#5c9acd", "#4579ba", "#355a9f", "#2a3e80", "#1e2763", "#131546"],
    "dark": ["#71b7c8", "#56a5bd", "#2c83aa", "#1d679c", "#154b8a", "#113375", "#101e5c", "#0a0b42", "#040027"],
}
ZONES = ["temperate", "boreal", "tundra", "arid"]

# Styles by height (2026-11-28, user decision: Terracotta is the default base in the light theme; Detuned is kept by name).
# Stops are [metres, colour]: land above sea level, sea in metres of water, one ramp for shelf and ocean alike. A stepped
# style gives a class the colour of its lower stop; a linear one runs between the stops in OKLab. `arid` replaces the land
# ramp where the climate is arid. `shade` is how the sky shade is laid on a ground: its strength on land and at sea (1 = the
# neutral shade as it is), and for a coloured shade the tones of slopes away from and towards the light and how far they go.
# Mirrored as STYLES in preview/palette.js (tests keep them in step). Change both together.
DEFAULT = "terracotta"
STYLES = {
    "terracotta": {
        "name": "Terracotta", "stepped": True,
        "land": [[0, "#b3bd74"], [60, "#cfd596"], [150, "#e6e2b8"], [300, "#f2dfc0"], [500, "#eec7a2"], [800, "#e0a380"], [1100, "#cd7f5e"], [1400, "#b55f43"], [1700, "#964734"], [2000, "#803b2d"], [2400, "#f7f3ee"]],
        "arid": [[0, "#f1d8b4"], [60, "#f3dcbc"], [150, "#f4dfc4"], [300, "#f2dfc0"], [500, "#eec7a2"], [800, "#e0a380"], [1100, "#cd7f5e"], [1400, "#b55f43"], [1700, "#964734"], [2000, "#803b2d"], [2400, "#f7f3ee"]],
        "sea": [[0, "#fcfbf7"], [40, "#f1f5f2"], [80, "#e2eeec"], [120, "#d0e4e5"], [200, "#b5d3da"], [350, "#8fbac8"], [600, "#6a9db3"], [1000, "#4a7f9b"], [1600, "#335f7e"], [2300, "#22445f"], [3200, "#18344c"], [4500, "#10263a"]],
        "shade": {"land": 1.25, "sea": 1.25},
    },
    "seabed": {
        "name": "Sea floor first", "stepped": False,
        "land": [[0, "#ebe8e2"]],
        "sea": [[0, "#f7faf8"], [30, "#e6f1ef"], [60, "#d3e7e6"], [90, "#bfdcdd"], [130, "#a6cdd2"], [200, "#88b9c4"], [350, "#6a9fb2"], [700, "#4a7d98"], [1500, "#2f587a"], [2700, "#1c3a5a"], [4500, "#112842"]],
        "shade": {"land": 0.6, "sea": 1.6},
    },
    "night": {
        "name": "Night chart", "stepped": False,
        "land": [[0, "#3b3a37"], [300, "#4a4743"], [800, "#665f55"], [1400, "#8d8271"], [2000, "#c2b7a3"]],
        "sea": [[0, "#3c5f70"], [50, "#2f4f61"], [120, "#254253"], [250, "#1b3445"], [600, "#132737"], [1500, "#0c1b29"], [2700, "#07121d"], [5000, "#040b13"]],
        "shade": {"land": 1.5, "sea": 1.5, "tint": ["#05090d", "#e8d9b8", 0.55]},
    },
    "shell": {
        "name": "Shell and slate", "stepped": False,
        "land": [[0, "#dfe6e2"], [100, "#cdd8d3"], [300, "#b4c4c1"], [600, "#98abb0"], [1000, "#7d8f9e"], [1500, "#66758c"], [1900, "#f4f5f7"]],
        "sea": [[0, "#fdf8f3"], [50, "#f7ebe4"], [100, "#f0dcd5"], [160, "#e6c9c4"], [300, "#d3aab0"], [700, "#b3889b"], [1500, "#8a6685"], [2700, "#5f4a6e"], [4500, "#44365a"]],
        "shade": {"land": 1.2, "sea": 1.2},
    },
    "air": {
        "name": "Mountain air", "stepped": False,
        "land": [[0, "#b7c8c6"], [100, "#c3d0c4"], [300, "#d3d8bf"], [600, "#e6debb"], [1000, "#f4e4bd"], [1500, "#f7dcc6"], [2000, "#fdf6ee"]],
        "sea": [[0, "#f3f6f7"], [60, "#e3ebef"], [130, "#cfdbe4"], [300, "#b0c3d4"], [800, "#869fbd"], [1600, "#62799f"], [2700, "#465781"], [4500, "#33416a"]],
        "shade": {"land": 1.5, "sea": 1.5, "tint": ["#4f4d85", "#fff4c8", 0.6]},
    },
}
SHADE_GAIN = 2.5  # slope stretch of the neutral shade (regional_shade.webp)
GROUND_CELL = 800.0  # metres: a finished ground is drawn at about this cell where the demo elevation is coarser (twice as fine at most)
_M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566], [0.0883024619, 0.2817188376, 0.6299787005]])
_M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468], [1.9779984951, -2.4285922050, 0.4505937099], [0.0259040371, 0.7827717662, -0.8086757660]])


def rgb(h: str) -> np.ndarray:
    return np.array([int(h[i : i + 2], 16) for i in (1, 3, 5)], dtype=np.float32)


def tune(h: str, sat: float, mix: float) -> np.ndarray:
    """palette.js `tune`: saturation towards the colour's own grey, then lifted (mix > 0) or sunk (mix < 0)."""
    c = rgb(h)
    y = 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    t = 255.0 if mix > 0 else 0.0
    g = y + (c - y) * sat
    return np.clip(g + (t - g) * abs(mix), 0, 255)


def linear_ramp(t: np.ndarray, breaks: list[float], cols: list[str], vmax: float) -> np.ndarray:
    """palette.js `at` + `rampAt`: piecewise-linear interpolation between the stops, t in 0..1."""
    pos = [b / vmax for b in breaks] + ([1.0] if len(cols) > len(breaks) else [])
    colours = np.stack([rgb(c) for c in cols])
    out = np.zeros(t.shape + (3,), dtype=np.float32)
    t = np.clip(t, 0, 1)
    for k in range(len(pos) - 1):
        t0, t1 = pos[k], pos[k + 1]
        m = (t >= t0) & (t <= t1) if k == len(pos) - 2 else (t >= t0) & (t < t1)
        f = ((t[m] - t0) / (t1 - t0 or 1))[:, None]
        out[m] = colours[k] * (1 - f) + colours[k + 1] * f
    return out


def land_stops(zone: str, theme: str) -> list[str]:
    """The zone ramp at half saturation, lifted (light) or sunk (dark): palette.js `tune(c, 0.5, ±0.08)`."""
    return ["#" + "".join(f"{round(v):02x}" for v in tune(c, 0.5, 0.08 if theme == "light" else -0.08)) for c in ZPAL[theme][zone]]


def linear_land(z: np.ndarray, weights: np.ndarray, theme: str) -> np.ndarray:
    """Land as a linear gradient, 0 to LMAX, on each climate zone's ramp (stops at LB), blended by the zone weights.
    The default since 2026-11-15; `stepped_land` is kept for the stepped option."""
    out = np.zeros(z.shape + (3,), dtype=np.float32)
    for zi, zone in enumerate(ZONES):
        out += weights[..., zi : zi + 1] * linear_ramp(z / LMAX, LB, land_stops(zone, theme), LMAX)
    return out


def stepped_land(z: np.ndarray, weights: np.ndarray, theme: str) -> np.ndarray:
    """Stepped height classes; each class colour is the zone ramps at half saturation, blended by the zone weights."""
    cls = np.clip(np.searchsorted(np.array(LB[1:], dtype=np.float32), z, side="right"), 0, len(LB) - 1)
    out = np.zeros(z.shape + (3,), dtype=np.float32)
    for zi, zone in enumerate(ZONES):
        cols = np.stack([tune(c, 0.5, 0.08 if theme == "light" else -0.08) for c in ZPAL[theme][zone]])
        out += weights[..., zi : zi + 1] * cols[cls]
    return out


def oklab(c: np.ndarray) -> np.ndarray:
    """sRGB (0 to 255) to OKLab."""
    c = np.asarray(c, dtype=np.float64) / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return np.cbrt(lin @ _M1.T) @ _M2.T


def from_oklab(lab: np.ndarray) -> np.ndarray:
    """OKLab to sRGB (0 to 255)."""
    lin = np.clip((lab @ np.linalg.inv(_M2).T) ** 3 @ np.linalg.inv(_M1).T, 0, 1)
    return np.where(lin <= 0.0031308, lin * 12.92, 1.055 * lin ** (1 / 2.4) - 0.055) * 255.0


def style_ramp(v: np.ndarray, stops: list, stepped: bool) -> np.ndarray:
    """The colour of `v` (metres) on a style's stops: the class of the lower stop where stepped, else between the stops in OKLab."""
    xs = np.array([s[0] for s in stops], dtype=np.float64)
    labs = np.stack([oklab(rgb(s[1])) for s in stops])
    if stepped:
        return np.stack([rgb(s[1]) for s in stops])[np.clip(np.searchsorted(xs, v, side="right") - 1, 0, len(xs) - 1)]
    return from_oklab(np.stack([np.interp(v, xs, labs[:, k]) for k in range(3)], axis=-1)).astype(np.float32)


def style_tint(z: np.ndarray, style: str, arid: np.ndarray | None = None) -> np.ndarray:
    """A style's flat tint of heights and depths `z` (metres, sea negative). `arid` is the weight of the arid zone, 0 to 1."""
    st = STYLES[style]
    land = style_ramp(np.maximum(z, 0), st["land"], st["stepped"])
    if arid is not None and "arid" in st and arid.any():
        land = land + (style_ramp(np.maximum(z, 0), st["arid"], st["stepped"]) - land) * np.clip(arid, 0, 1)[..., None]
    return np.where((z < 0)[..., None], style_ramp(np.maximum(-z, 0), st["sea"], st["stepped"]), land).astype(np.float32)


def soft_light(base: np.ndarray, shade: np.ndarray) -> np.ndarray:
    """One picture on another in soft light (the web's blend rule), both 0 to 1: mid grey leaves the base as it is."""
    d = np.where(base <= 0.25, ((16.0 * base - 12.0) * base + 4.0) * base, np.sqrt(base))
    return np.where(shade <= 0.5, base - (1.0 - 2.0 * shade) * base * (1.0 - base), base + (2.0 * shade - 1.0) * (d - base))


def shaded(tint: np.ndarray, shade: np.ndarray, z: np.ndarray, style: str) -> np.ndarray:
    """A style's finished ground: its tint (0 to 255) with the neutral shade (0 to 1, flat ground 0.5) laid on at the style's
    strength on land and at sea, in soft light or, for a coloured shade, towards its two tones."""
    sh = STYLES[style]["shade"]
    s = np.clip(0.5 + (shade - 0.5) * np.where(z < 0, sh["sea"], sh["land"]), 0, 1)[..., None]
    b = tint / 255.0
    if "tint" in sh:
        dark, light, amount = rgb(sh["tint"][0]) / 255.0, rgb(sh["tint"][1]) / 255.0, sh["tint"][2]
        t = (s - 0.5) * 2.0
        out = np.where(t < 0, b + (dark - b) * np.clip(-t, 0, 1) * amount, b + (light - b) * np.clip(t, 0, 1) * amount)
    else:
        out = soft_light(b, s)
    return np.clip(out * 255.0, 0, 255)


def style_key(style: str, zmin: float, zmax: float) -> dict:
    """What a consumer needs to draw the keys of a style: its stops within the frame's range of heights and depths."""
    st = STYLES[style]
    cut = lambda stops, top: [s for i, s in enumerate(stops) if i == 0 or stops[i][0] <= top]
    return {"name": st["name"], "stepped": st["stepped"], "land": cut(st["land"], zmax), "sea": cut(st["sea"], -zmin), "shade": st["shade"]}


def zone_weights(path: Path, shape: tuple[int, int]) -> np.ndarray:
    """Temperate, boreal, tundra weights from zones.png (R, G, B); arid is the remainder."""
    im = Image.open(path).convert("RGB").resize((shape[1], shape[0]), Image.BILINEAR)
    w = np.asarray(im, dtype=np.float32) / 255.0
    arid = np.clip(1.0 - w.sum(axis=-1), 0, 1)
    w = np.dstack([w, arid])
    s = w.sum(axis=-1, keepdims=True)
    s[s == 0] = 1
    return w / s


def elevation(demo: Path, shape: tuple[int, int]) -> np.ndarray:
    meta = json.loads((demo / "meta.json").read_text(encoding="utf-8"))
    base, step = meta["encoding"]["base"], meta["encoding"]["step"]
    a = np.asarray(Image.open(io.BytesIO((demo / "elev.webp").read_bytes())).convert("RGB")).astype("uint32")
    z = (base + ((a[..., 0] << 8) | a[..., 1]) * step).astype(np.float32)
    return np.asarray(Image.fromarray(z, "F").resize((shape[1], shape[0]), Image.BOX), dtype=np.float32)


def render(region: str) -> dict:
    out = ROOT / "data" / "out" / region
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    regions = json.loads((ROOT / "regions" / "regions.json").read_text(encoding="utf-8"))["regions"]
    bathy = next((r.get("bathymetry", "shelf") for r in regions if r["id"] == region), "shelf")
    h, w = manifest["lods"]["regional"]["shape"]
    z = elevation(out / "demo", (h, w))
    weights = zone_weights(out / "demo" / "zones.png", (h, w))
    sea = z < 0
    detuned = {}
    for theme in ("light", "dark"):
        if bathy == "ocean":
            s = linear_ramp(-z / OCEAN_MAX, OCEAN_SB, DETUNED_OCEAN[theme], OCEAN_MAX)
        else:
            s = linear_ramp(-z / SMAX, SB, DETUNED_SEA[theme], SMAX)
        land = linear_land(np.maximum(z, 0), weights, theme)
        detuned[theme] = np.where(sea[..., None], s, land)
    # The base of the light theme is the default style; the dark theme and the named `detuned` file keep Detuned.
    pictures = {"light": style_tint(z, DEFAULT, weights[..., 3]), "dark": detuned["dark"], "detuned": detuned["light"]}
    files = {}
    for key, img in pictures.items():
        name = f"regional_base_{key}.png"
        Image.fromarray(np.round(np.clip(img, 0, 255)).astype("uint8"), "RGB").save(out / name, optimize=True)
        files[key] = name
    # Web assets: the same tints as lossy WebP (about a fifth of the PNG), and the hillshade as a neutral WebP with flat
    # ground at mid grey and the slopes stretched, so a page composites it with soft-light as it is, without remapping.
    web = {}
    for theme, name in files.items():
        im = Image.open(out / name)
        wname = name.replace(".png", ".webp")
        im.save(out / wname, "WEBP", quality=85, method=6)
        web[theme] = wname
    hs = np.asarray(Image.open(out / "regional_hillshade.png").convert("L"), dtype=np.float32)
    flat = float(np.sin(np.radians(45)) * 255)
    neutral = np.clip(128 + (hs - flat) * SHADE_GAIN, 0, 255)
    Image.fromarray(np.round(neutral).astype("uint8"), "L").save(out / "regional_shade.webp", "WEBP", quality=80, method=6)
    meta = json.loads((out / "demo" / "meta.json").read_text(encoding="utf-8"))
    key = style_key(DEFAULT, meta["zmin"], meta["zmax"])
    manifest["base"] = {
        "regional": {"light": files["light"], "dark": files["dark"]},
        "webp": {"light": web["light"], "dark": web["dark"]},
        "detuned": {"light": files["detuned"], "webp": web["detuned"], "depth_scale": {"kind": bathy, "max_m": OCEAN_MAX if bathy == "ocean" else SMAX},
                    "note": "the light base until 2026-11-28: linear sea on the region's depth scale, linear land cross-blended by climate zone"},
        "shade": {"file": "regional_shade.webp", "flat": 128, "gain": SHADE_GAIN, "note": "the regional hillshade with flat ground at mid grey and slopes stretched 2.5 x; composite with soft-light directly"},
        "default": DEFAULT,
        "style": "Terracotta (light): stepped classes of height and depth, lowland by aridity; Detuned (dark): linear sea and land",
        "depth_scale": {"kind": "classes", "max_m": key["sea"][-1][0], "ticks_m": [s[0] for s in key["sea"]], "stops": key["sea"], "stepped": True},
        "land_scale": {"max_m": key["land"][-1][0], "ticks_m": [s[0] for s in key["land"]], "stops_m": [s[0] for s in key["land"]], "stops": key["land"], "stepped": True,
                       "note": "classes since 2026-11-28 (Terracotta); draw the height key as classes with the colours of `stops`"},
        "land_classes_m": [s[0] for s in key["land"]],
        "ground": grounds(out, manifest, meta),
        "note": "Draw this image with an identity transform in the frame extent, your data over it, then the hillshade. Do not recolour bands or heights. "
                "A finished ground of a named style (tint and sky shade together) is under `ground`.",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return {"region": region, "shape": [h, w], "bathymetry": bathy, "sea_share": round(float(sea.mean()), 3), "files": files, "ground": manifest["base"]["ground"]["size"]}


def grounds(out: Path, manifest: dict, meta: dict) -> dict:
    """The finished ground of every style, for maps that draw the terrain under their data and nothing over it: the style's
    tint from the demo elevation at its own cell, with the sky shade of the finest level of detail laid on as the style says.
    Written to data/out/<region>/ground/<style>.webp (lossy, quality 92) in the frame's extent."""
    w, h = meta["size"]
    z = elevation(out / "demo", (h, w))
    f = int(np.clip(round((manifest["extent"][2] - manifest["extent"][0]) / w / GROUND_CELL), 1, 2))
    if f > 1:  # a coarse frame is drawn finer than it is held, so that the coast and the edges of the classes are curves and not pixels
        w, h = w * f, h * f
        z = np.asarray(Image.fromarray(z, "F").resize((w, h), Image.BICUBIC), dtype=np.float32)
    arid = zone_weights(out / "demo" / "zones.png", (h, w))[..., 3]
    lod = min((v for k, v in manifest["lods"].items() if (out / f"{k}_hillshade.png").exists()), key=lambda v: v["cell"])
    name = next(k for k, v in manifest["lods"].items() if v is lod)
    hs = np.asarray(Image.open(out / f"{name}_hillshade.png").convert("L").resize((w, h), Image.BILINEAR), dtype=np.float32)
    shade = np.clip(128 + (hs - float(np.sin(np.radians(45)) * 255)) * SHADE_GAIN, 0, 255) / 255.0
    (out / "ground").mkdir(exist_ok=True)
    styles = {}
    for style in STYLES:
        img = np.empty((h, w, 3), dtype="uint8")
        for r in range(0, h, 512):  # in bands of rows: the ramps work in OKLab, in float64
            b = slice(r, r + 512)
            img[b] = np.round(shaded(style_tint(z[b], style, arid[b]), shade[b], z[b], style)).astype("uint8")
        Image.fromarray(img, "RGB").save(out / "ground" / f"{style}.webp", "WEBP", quality=92, method=4)
        styles[style] = {"file": f"ground/{style}.webp", **style_key(style, meta["zmin"], meta["zmax"])}
    return {"size": [w, h], "cell": (manifest["extent"][2] - manifest["extent"][0]) / w, "drawn_finer": f, "shade_from": f"{name}_hillshade.png", "default": DEFAULT, "styles": styles,
            "note": "tint and sky shade together, in the frame extent; draw with an identity transform and the data over it, and no hillshade on top"}


if __name__ == "__main__":
    for r in sys.argv[1:] or ["ne_europe"]:
        print(render(r))
