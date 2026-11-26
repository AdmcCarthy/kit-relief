"""Smoothed elevation and bathymetry surfaces for Petrel, with colour bars, from a Relief frame's merged grid.

The smoothing is Relief's own generalisation by scale (scripts/build.py): the merged grid is averaged to the level of
detail's cell, then Gaussian-smoothed by that level's sigma in cells (regional 2,000 m and sigma 1.0, detail 800 m and
sigma 0.8). Nothing is contoured or resampled by another rule. One smoothed surface per level is cut into the products:

  full    every cell: land heights and sea-floor depths
  norway  sea floor everywhere, land only inside Norway; land of every other country is null
  koppen  Köppen-Geiger class (Beck and others 2023, 1991 to 2020) on land, null at sea (regional level only)

Per product: an Irap classic ASCII grid (Petrel: Import > Irap classic grid) with Z positive down, the Petrel convention,
a float32 GeoTIFF in the region's CRS with Z as elevation (sea negative, as everywhere in Relief), and a preview map.
Colour bars: elevation on the house Detuned scale, the same with one land bar per climate zone, and the Köppen classes;
each as SVG, PNG and a CSV colour table.

  uv run python scripts/petrel_surfaces.py ne_europe [--lods regional,detail] [--crs EPSG:25831] [--force] [--dry-run]

Reads data/raw/<region>/hires.tif (or merged.tif), the Köppen raster and Natural Earth countries; writes
data/out/<region>/petrel/. A second run on the same inputs stops with "unchanged" (petrel/runs.json, runs_utm31.json).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from areas import AREAS
from base_tint import (
    DETUNED_SEA,
    LB,
    LMAX,
    SB,
    SMAX,
    ZONES,
    land_stops,
    linear_land,
    linear_ramp,
)
from build import LOD_RULES, load_merged
from PIL import Image, ImageDraw, ImageFont
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.warp import reproject
from scipy.ndimage import binary_dilation, distance_transform_edt, gaussian_filter
from shapely.geometry import shape
from shapely.ops import transform as shp_transform
from shapely.ops import unary_union
from sky_view import sky_hillshade

ROOT = Path(__file__).resolve().parents[1]
KOPPEN = ROOT / "data" / "raw" / "climate" / "1991_2020" / "koppen_geiger_0p00833333.tif"
NE_COUNTRIES = ROOT / "data" / "raw" / "natural_earth" / "ne_10m_admin_0_countries.geojson"
NODATA_IRAP = 9999900.0
SEA_STOPS = DETUNED_SEA["light"]
ATTRIBUTION = [
    "Copernicus DEM GLO-90: © DLR e.V. 2010-2014 and © Airbus 2014-2018, provided under COPERNICUS by the European Union and ESA.",
    "EMODnet Bathymetry Consortium (2024): EMODnet Digital Bathymetry (DTM).",
    "NOAA NCEI (2022) ETOPO 2022 15 Arc-Second Global Relief Model.",
    "Contains OS data © Crown copyright and database right 2026. © Kartverket.",
    "Köppen-Geiger: Beck and others (2023), 1991-2020, CC BY 4.0.",
    "Made with Natural Earth. Free vector and raster map data @ naturalearthdata.com",
]

# Beck and others (2023) class codes 1 to 30
KG = {1: "Af", 2: "Am", 3: "Aw", 4: "BWh", 5: "BWk", 6: "BSh", 7: "BSk", 8: "Csa", 9: "Csb", 10: "Csc", 11: "Cwa", 12: "Cwb",
      13: "Cwc", 14: "Cfa", 15: "Cfb", 16: "Cfc", 17: "Dsa", 18: "Dsb", 19: "Dsc", 20: "Dsd", 21: "Dwa", 22: "Dwb", 23: "Dwc",
      24: "Dwd", 25: "Dfa", 26: "Dfb", 27: "Dfc", 28: "Dfd", 29: "ET", 30: "EF"}
KG_NAME = {"Cfb": "Temperate, no dry season, warm summer", "Cfc": "Temperate, no dry season, cold summer",
           "Cfa": "Temperate, no dry season, hot summer", "Csb": "Temperate, dry warm summer", "Csa": "Temperate, dry hot summer",
           "Dfb": "Cold, no dry season, warm summer", "Dfc": "Cold, no dry season, cold summer", "Dsb": "Cold, dry summer, warm summer",
           "Dfa": "Cold, no dry season, hot summer", "Dwc": "Cold, dry winter, cold summer", "Dsc": "Cold, dry summer, cold summer",
           "ET": "Polar tundra", "EF": "Polar frost", "BSk": "Arid steppe, cold", "BSh": "Arid steppe, hot",
           "BWk": "Arid desert, cold", "BWh": "Arid desert, hot"}
GROUP_OF = {**{k: "arid" for k in (4, 5, 6, 7)}, **{k: "temperate" for k in (1, 2, 3, *range(8, 17))},
            **{k: "boreal" for k in range(17, 29)}, 29: "tundra", 30: "tundra"}
GROUP_HUE = {"arid": 80, "temperate": 140, "boreal": 275, "tundra": 215}


# ---------------------------------------------------------------- surfaces

def smoothed(region: str, lod: str, crs: str | None = None) -> tuple[np.ndarray, rasterio.Affine, dict]:
    """Relief's smoothing for one level of detail: mean to the cell, then Gaussian by the level's sigma in cells.

    In another CRS the merged grid is warped once, by averaging, onto a grid that covers the frame, and smoothed there
    (never smoothed and warped again). Cells the frame does not reach are null; the smoothing is normalised so the
    edge of the data does not pull heights towards zero.
    """
    a = AREAS[region]
    cell = a["lods"][lod]["cell"]
    sigma = LOD_RULES[lod]["sigma"]
    if crs is None or crs == a["crs"]:
        z, tr = load_merged(region, a, cell)
        return gaussian_filter(np.nan_to_num(z, nan=0.0), sigma).astype("float32"), tr, {"cell_m": cell, "sigma_cells": sigma}
    from rasterio.warp import transform_bounds

    raw = ROOT / "data" / "raw" / region
    src_path = raw / "hires.tif" if (raw / "hires.tif").exists() else raw / "merged.tif"
    x0, y0, x1, y1 = transform_bounds(a["crs"], crs, *a["extent"], densify_pts=41)
    x0, y0 = np.floor(x0 / cell) * cell, np.floor(y0 / cell) * cell
    w, h = int(np.ceil((x1 - x0) / cell)), int(np.ceil((y1 - y0) / cell))
    tr = rasterio.Affine(cell, 0, x0, 0, -cell, y0 + h * cell)
    z = np.full((h, w), np.nan, dtype="float32")
    with rasterio.open(src_path) as src:
        res_m = src.res[0] if src.crs.is_projected else src.res[1] * 111_000
        reproject(rasterio.band(src, 1), z, dst_transform=tr, dst_crs=crs, dst_nodata=np.nan, tolerance=0.0,
                  resampling=Resampling.average if cell >= res_m else Resampling.bilinear)
    m = (~np.isnan(z)).astype("float32")
    num = gaussian_filter(np.nan_to_num(z, nan=0.0) * m, sigma)
    den = gaussian_filter(m, sigma)
    zs = np.where(m > 0, num / np.maximum(den, 1e-6), np.nan).astype("float32")
    return zs, tr, {"cell_m": cell, "sigma_cells": sigma}


def country_masks(region: str, shape_hw: tuple[int, int], tr: rasterio.Affine, crs: str) -> tuple[np.ndarray, np.ndarray]:
    """Boolean grids on the surface grid: inside Norway, and inside any country (land), from Natural Earth 10 m."""
    to_crs = Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform
    feats = json.loads(NE_COUNTRIES.read_text(encoding="utf-8"))["features"]
    w0, s0, e0, n0 = AREAS[region]["box"]
    keep = []
    for f in feats:
        g = shape(f["geometry"])
        if g.bounds[2] < w0 or g.bounds[0] > e0 or g.bounds[3] < s0 or g.bounds[1] > n0:
            continue
        keep.append((f["properties"].get("ADMIN") or f["properties"].get("NAME"), shp_transform(to_crs, g)))
    nor = [g for n, g in keep if n == "Norway"]
    if not nor:
        raise SystemExit("Natural Earth has no Norway polygon in the frame")
    all_land = unary_union([g for _, g in keep])
    norway = unary_union(nor)
    r = lambda g: rasterize([(g, 1)], out_shape=shape_hw, transform=tr, fill=0, dtype="uint8").astype(bool)
    return r(norway), r(all_land)


def koppen_classes(shape_hw: tuple[int, int], tr: rasterio.Affine, crs: str) -> np.ndarray:
    """Köppen-Geiger class per cell (modal class of the 1 km cells under it); 0 where the raster has no land."""
    from rasterio.warp import transform_bounds
    from rasterio.windows import from_bounds

    h, w = shape_hw
    b = transform_bounds(crs, "EPSG:4326", tr.c, tr.f + tr.e * h, tr.c + tr.a * w, tr.f)
    with rasterio.open(KOPPEN) as r:
        win = from_bounds(b[0] - 0.2, b[1] - 0.2, b[2] + 0.2, b[3] + 0.2, r.transform)
        kg, ktr = r.read(1, window=win), r.window_transform(win)
    cls = np.zeros((h, w), dtype="uint8")
    reproject(kg, cls, src_transform=ktr, src_crs="EPSG:4326", dst_transform=tr, dst_crs=crs, resampling=Resampling.mode)
    return cls


def zone_weights(cls: np.ndarray, cell: float) -> np.ndarray:
    """Temperate, boreal, tundra, arid weights from the class grid, blurred over 6 km as Relief does (render_demo.climate_zones)."""
    near = distance_transform_edt(cls == 0, return_distances=False, return_indices=True)
    filled = cls[tuple(near)]
    out = np.zeros(cls.shape + (4,), dtype="float32")
    for k, g in GROUP_OF.items():
        out[..., ZONES.index(g)] += filled == k
    sig = max(6000 / cell, 0.0)
    for c in range(4):
        out[..., c] = gaussian_filter(out[..., c], sig) if sig else out[..., c]
    return out / np.maximum(out.sum(axis=2, keepdims=True), 1e-6)


# ---------------------------------------------------------------- writers

def write_irap(path: Path, zdown: np.ndarray, tr: rasterio.Affine) -> None:
    """Irap classic ASCII: nodes at the cell centres, x fastest, rows south to north, five values per line, 9999900 undefined.
    The value order was checked against xtgeo 4.28 (see tests/test_petrel_surfaces.py)."""
    h, w = zdown.shape
    cell = tr.a
    xmin, ymin = tr.c + cell / 2, tr.f + tr.e * h + cell / 2
    xmax, ymax = xmin + (w - 1) * cell, ymin + (h - 1) * cell
    vals = np.where(np.isnan(zdown), NODATA_IRAP, zdown)[::-1].ravel()
    pad = (-len(vals)) % 5
    vals = np.concatenate([vals, np.full(pad, NODATA_IRAP)]) if pad else vals
    lines = vals.reshape(-1, 5)
    with path.open("w", newline="\n") as f:
        f.write(f"-996 {h} {cell:.6f} {cell:.6f}\n{xmin:.6f} {xmax:.6f} {ymin:.6f} {ymax:.6f}\n{w} 0.000000 {xmin:.6f} {ymin:.6f}\n")
        f.write("0  0  0  0  0  0  0\n")
        for i in range(0, len(lines), 20000):
            f.write("\n".join(" ".join(f"{v:.2f}" for v in row) for row in lines[i : i + 20000]) + "\n")


def write_tif(path: Path, z: np.ndarray, tr: rasterio.Affine, crs: str, tags: dict) -> None:
    with rasterio.open(path, "w", driver="GTiff", height=z.shape[0], width=z.shape[1], count=1, dtype="float32", crs=crs,
                       transform=tr, nodata=np.nan, compress="deflate", predictor=3) as dst:
        dst.write(z.astype("float32"), 1)
        dst.update_tags(**tags)


# ---------------------------------------------------------------- colour

def sea_rgb(depth: np.ndarray) -> np.ndarray:
    return linear_ramp(depth / SMAX, SB, SEA_STOPS, SMAX)


def land_rgb_zone(height: np.ndarray, zone: str) -> np.ndarray:
    return linear_ramp(height / LMAX, LB, land_stops(zone, "light"), LMAX)


def elevation_rgb(z: np.ndarray, weights: np.ndarray | None, zone: str = "temperate") -> np.ndarray:
    """Sea on the shelf scale, land on one zone's ramp, or blended by the climate weights when given."""
    land = linear_land(np.maximum(z, 0), weights, "light") if weights is not None else land_rgb_zone(np.maximum(z, 0), zone)
    return np.where((z < 0)[..., None], sea_rgb(np.maximum(-z, 0)), land)


def font(size: int) -> ImageFont.ImageFont:
    for name in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def hexof(c) -> str:
    return "#" + "".join(f"{round(v):02x}" for v in c)


def kg_colour(code: int, present: list[int]) -> tuple[int, int, int]:
    """Köppen class colour: a hue per group, lightness stepping through the group's classes present (indicative, not Beck's scheme)."""
    from depth_ramp import oklch_to_srgb

    g = GROUP_OF[code]
    members = [k for k in present if GROUP_OF[k] == g]
    f = members.index(code) / max(len(members) - 1, 1)
    L, C = 0.86 - 0.42 * f, (0.04 if g == "tundra" else 0.12)
    return tuple(round(v * 255) for v in oklch_to_srgb(L, C, GROUP_HUE[g]))


def fmt(v: float) -> str:
    return f"{abs(v):,.0f}".replace("-", "") if v >= 0 else f"−{abs(v):,.0f}"


def gradient_stops(breaks: list[float], cols: list[str], vmax: float) -> list[tuple[float, str]]:
    pos = [b / vmax for b in breaks] + ([1.0] if len(cols) > len(breaks) else [])
    return list(zip(pos, cols))


def svg_bar(path: Path, bars: list[dict], title: str, sub: str, hmin: float = -SMAX, hmax: float = float(LMAX)) -> None:
    """Vertical colour bar(s) as SVG: each bar is a list of (height, colour) stops in metres, drawn between hmin and hmax."""
    W, H, top, bot = max(120 + 96 * len(bars), 400), 560, 70, 60
    span = hmax - hmin
    y = lambda v: top + (hmax - v) / span * (H - top - bot)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Segoe UI, Arial, sans-serif">',
           f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
           f'<text x="12" y="24" font-size="14" font-weight="600" fill="#1d2b33">{title}</text>',
           f'<text x="12" y="44" font-size="11" fill="#4a5a63">{sub}</text>', "<defs>"]
    for i, b in enumerate(bars):
        stops = "".join(f'<stop offset="{(hmax - v) / span:.5f}" stop-color="{c}"/>' for v, c in sorted(b["stops"], key=lambda s: -s[0]))
        out.append(f'<linearGradient id="g{i}" x1="0" y1="0" x2="0" y2="1">{stops}</linearGradient>')
    out.append("</defs>")
    x0 = 84
    for i, b in enumerate(bars):
        lo, hi = b["range"]
        x = x0 + i * 96
        out.append(f'<rect x="{x}" y="{y(hi):.1f}" width="34" height="{y(lo) - y(hi):.1f}" fill="url(#g{i})" stroke="#1d2b33" stroke-width="0.6"/>')
        out.append(f'<text x="{x + 17}" y="{H - 38}" font-size="11" text-anchor="middle" fill="#1d2b33">{b["label"]}</text>')
    ticks = [-1300, -1000, -500, -250, 0, 500, 1000, 1500, 2000]
    for t in ticks:
        out.append(f'<line x1="{x0 - 5}" x2="{x0}" y1="{y(t):.1f}" y2="{y(t):.1f}" stroke="#1d2b33" stroke-width="0.8"/>')
        lab = fmt(t)
        out.append(f'<text x="{x0 - 9}" y="{y(t) + 4:.1f}" font-size="11" text-anchor="end" fill="#1d2b33">{lab}</text>')
    out.append(f'<text x="{x0 - 9}" y="{H - 20}" font-size="10" text-anchor="end" fill="#4a5a63">m</text></svg>')
    path.write_text("\n".join(out), encoding="utf-8")


def png_bar(path: Path, bars: list[dict], title: str, sub: str, hmin: float = -SMAX, hmax: float = float(LMAX)) -> None:
    W, H, top, bot = max(120 + 96 * len(bars), 400), 560, 70, 60
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    span = hmax - hmin
    y = lambda v: top + (hmax - v) / span * (H - top - bot)
    ink = (29, 43, 51)
    d.text((12, 12), title, fill=ink, font=font(15))
    d.text((12, 36), sub, fill=(74, 90, 99), font=font(11))
    x0 = 84
    for i, b in enumerate(bars):
        lo, hi = b["range"]
        x = x0 + i * 96
        vals = np.linspace(hi, lo, max(int(y(lo) - y(hi)), 2))
        col = b["fn"](vals)
        for k, c in enumerate(col):
            yy = int(y(hi)) + k
            d.line([(x, yy), (x + 34, yy)], fill=tuple(round(v) for v in c))
        d.rectangle([x, y(hi), x + 34, y(lo)], outline=ink)
        d.text((x + 17, H - 40), b["label"], fill=ink, font=font(11), anchor="ma")
    for t in [-1300, -1000, -500, -250, 0, 500, 1000, 1500, 2000]:
        d.line([(x0 - 5, y(t)), (x0, y(t))], fill=ink)
        d.text((x0 - 9, y(t)), fmt(t), fill=ink, font=font(11), anchor="rm")
    d.text((x0 - 9, H - 24), "m", fill=(74, 90, 99), font=font(10), anchor="rm")
    im.save(path)


def write_colour_tables(out: Path) -> None:
    rows = [("elevation_m", "z_down_m", "r", "g", "b", "hex")]
    for v in np.linspace(-SMAX, LMAX, 256):
        c = (sea_rgb(np.array([-v]))[0] if v < 0 else land_rgb_zone(np.array([v]), "temperate")[0])
        rows.append((f"{v:.1f}", f"{-v:.1f}", *[round(x) for x in c], hexof(c)))
    with (out / "colourbar_elevation_256.csv").open("w", newline="") as f:
        csv.writer(f).writerows(rows)
    stops = [("elevation_m", "z_down_m", "hex", "role")]
    for b, c in gradient_stops(SB, SEA_STOPS, SMAX)[::-1]:
        stops.append((f"{-b * SMAX:.0f}", f"{b * SMAX:.0f}", c, "sea floor"))
    for b, c in gradient_stops(LB, land_stops("temperate", "light"), LMAX)[1:]:
        stops.append((f"{b * LMAX:.0f}", f"{-b * LMAX:.0f}", c, "land, temperate ramp"))
    with (out / "colourbar_elevation_stops.csv").open("w", newline="") as f:
        csv.writer(f).writerows(stops)
    rows = [("zone", "height_m", "r", "g", "b", "hex")]
    for zn in ZONES:
        for v in LB:
            c = land_rgb_zone(np.array([float(v)]), zn)[0]
            rows.append((zn, v, *[round(x) for x in c], hexof(c)))
    with (out / "colourbar_land_by_climate_zone.csv").open("w", newline="") as f:
        csv.writer(f).writerows(rows)


def write_bars(out: Path) -> None:
    sea = {"label": "sea floor", "range": (-SMAX, 0), "stops": [(-b * SMAX, c) for b, c in gradient_stops(SB, SEA_STOPS, SMAX)],
           "fn": lambda v: sea_rgb(-np.asarray(v))}
    sea_s = {**sea}

    def land(zone: str, label: str) -> dict:
        return {"label": label, "range": (0, LMAX), "stops": [(b * LMAX, c) for b, c in gradient_stops(LB, land_stops(zone, "light"), LMAX)],
                "fn": lambda v, zone=zone: land_rgb_zone(np.asarray(v), zone)}

    single = [{**sea, "label": "elevation"}, {**land("temperate", ""), "label": ""}]
    # one continuous bar: the sea ramp below 0 and the temperate land ramp above it
    cont = {"label": "elevation", "range": (-SMAX, LMAX),
            "stops": sea["stops"] + [(b * LMAX, c) for b, c in gradient_stops(LB, land_stops("temperate", "light"), LMAX)[1:]],
            "fn": lambda v: np.where((np.asarray(v) < 0)[..., None], sea_rgb(-np.asarray(v)), land_rgb_zone(np.asarray(v), "temperate"))}
    del single
    sub = "metres, sea floor negative · saturates at 1,300 m deep · Derived"
    svg_bar(out / "colourbar_elevation.svg", [cont], "Elevation and bathymetry", sub)
    png_bar(out / "colourbar_elevation.png", [cont], "Elevation and bathymetry", sub)
    by_zone = [sea_s, land("temperate", "temperate"), land("boreal", "boreal"), land("tundra", "tundra"), land("arid", "arid")]
    sub2 = "land tint depends on climate zone (Köppen-Geiger groups); the sea scale is one for all"
    svg_bar(out / "colourbar_elevation_by_climate.svg", by_zone, "Elevation by climate zone", sub2)
    png_bar(out / "colourbar_elevation_by_climate.png", by_zone, "Elevation by climate zone", sub2)


def write_koppen_legend(out: Path, counts: dict[int, int]) -> None:
    present = [k for k in sorted(counts) if k in KG]
    with (out / "koppen_legend.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(("code", "class", "description", "zone_group", "cells", "r", "g", "b", "hex"))
        for k in present:
            c = kg_colour(k, present)
            w.writerow((k, KG[k], KG_NAME.get(KG[k], ""), GROUP_OF[k], counts[k], *c, hexof(c)))
    rows = [(k, KG[k], hexof(kg_colour(k, present))) for k in present]
    h = 70 + 26 * len(rows)
    im = Image.new("RGB", (430, h), "white")
    d = ImageDraw.Draw(im)
    d.text((12, 12), "Köppen-Geiger class (Beck and others 2023)", fill=(29, 43, 51), font=font(15))
    d.text((12, 36), "Interpreted: zone groups follow Relief; hues are indicative", fill=(74, 90, 99), font=font(11))
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="430" height="{h}" font-family="Segoe UI, Arial, sans-serif"><rect width="430" height="{h}" fill="#fff"/>',
           '<text x="12" y="24" font-size="14" font-weight="600" fill="#1d2b33">Köppen-Geiger class (Beck and others 2023)</text>',
           '<text x="12" y="44" font-size="11" fill="#4a5a63">Interpreted: zone groups follow Relief; hues are indicative</text>']
    for i, (k, name, hx) in enumerate(rows):
        yy = 62 + 26 * i
        d.rectangle([12, yy, 40, yy + 18], fill=hx, outline=(29, 43, 51))
        txt = f"{name}  {KG_NAME.get(name, '')}  ({GROUP_OF[k]})"
        d.text((50, yy + 9), txt, fill=(29, 43, 51), font=font(12), anchor="lm")
        svg.append(f'<rect x="12" y="{yy}" width="28" height="18" fill="{hx}" stroke="#1d2b33" stroke-width="0.6"/>'
                   f'<text x="50" y="{yy + 13}" font-size="12" fill="#1d2b33">{txt}</text>')
    im.save(out / "colourbar_koppen.png")
    (out / "colourbar_koppen.svg").write_text("\n".join(svg) + "</svg>", encoding="utf-8")


# ---------------------------------------------------------------- previews

def preview(path: Path, z: np.ndarray, weights: np.ndarray, cell: float, title: str, note: str, crs_label: str, null: np.ndarray | None = None,
            climate: np.ndarray | None = None) -> None:
    rgb = elevation_rgb(z, weights) if climate is None else climate
    m = sky_hillshade(z, cell)
    if climate is not None:
        m = 1 + (m - 1) * 0.5 * (z >= 0)  # a light touch of relief on land, none over the white sea
    rgb = np.clip(rgb * np.clip(m, 0.4, 1.4)[..., None], 0, 255)
    if null is not None:
        rgb = np.where(null[..., None], np.array([236, 238, 240], dtype=np.float32), rgb)
    h, w = z.shape
    scale = 1 if w >= 1100 else 2
    im = Image.fromarray(np.round(rgb).astype("uint8"), "RGB").resize((w * scale, h * scale), Image.LANCZOS) if scale > 1 else Image.fromarray(np.round(rgb).astype("uint8"), "RGB")
    pad = 96
    canvas = Image.new("RGB", (im.width, im.height + pad + 90), "white")
    d = ImageDraw.Draw(canvas)
    d.text((14, 12), title, fill=(29, 43, 51), font=font(20))
    d.text((14, 44), note, fill=(74, 90, 99), font=font(12))
    canvas.paste(im, (0, pad - 12))
    yb = pad - 12 + im.height + 8
    for lines, k in zip(ATTRIBUTION, range(len(ATTRIBUTION))):
        if k < 3:
            d.text((14, yb + k * 16), lines, fill=(74, 90, 99), font=font(10))
    d.text((14, yb + 3 * 16), crs_label + ". Elevation: Derived (merged, then smoothed). " + ATTRIBUTION[3] + " " + ATTRIBUTION[5],
           fill=(74, 90, 99), font=font(10))
    canvas.save(path, optimize=True)


# ---------------------------------------------------------------- run

def fingerprint(region: str, lods: list[str], crs: str) -> dict:
    files = [ROOT / "data" / "raw" / region / n for n in ("hires.tif", "merged.tif")] + [KOPPEN, NE_COUNTRIES]
    return {"region": region, "lods": lods, "crs": crs,
            "inputs": {p.name: [p.stat().st_size, int(p.stat().st_mtime)] for p in files if p.exists()},
            "settings": {k: LOD_RULES[k] for k in lods},
            "code": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:16]}


CRS_LABEL = {"EPSG:3035": "ETRS89 / LAEA Europe (EPSG:3035)", "EPSG:25831": "ETRS89 / UTM zone 31N (EPSG:25831)"}
CRS_TAG = {"EPSG:3035": "", "EPSG:25831": "_utm31"}


def run(region: str, lods: list[str], force: bool, dry: bool, crs: str | None = None) -> int:
    crs = crs or AREAS[region]["crs"]
    if crs not in CRS_TAG:
        raise SystemExit(f"CRS {crs} has no output tag; known: {', '.join(CRS_TAG)}")
    tag = CRS_TAG[crs]
    label = CRS_LABEL[crs]
    out = ROOT / "data" / "out" / region / "petrel"
    runs = out / f"runs{tag}.json"
    fp = fingerprint(region, lods, crs)
    prev = json.loads(runs.read_text()) if runs.exists() else None
    done = prev is not None and prev["fingerprint"] == fp and all((out / f).exists() for f in prev["files"])
    if done and not force:
        print("unchanged: inputs, settings and code match the last run; nothing written (use --force)")
        return 0
    if dry:
        print("would run: " + ("--force" if force else "inputs, settings or code changed") + f", levels {', '.join(lods)}")
        return 0
    out.mkdir(parents=True, exist_ok=True)
    stats: dict = {}
    for lod in lods:
        t0 = time.time()
        zs, tr, cfg = smoothed(region, lod, crs)
        cell = cfg["cell_m"]
        norway, land = country_masks(region, zs.shape, tr, crs)
        cls = koppen_classes(zs.shape, tr, crs)
        weights = zone_weights(cls, cell)
        tags = {"source": "Relief " + region + " merged grid", "smoothing": f"mean to {cell:.0f} m, Gaussian sigma {cfg['sigma_cells']} cells (Relief {lod} level)",
                "vertical": "metres; land on EGM2008 (Copernicus), sea floor EMODnet DTM chart datum; not unified", "confidence": "Derived"}
        outside = np.isnan(zs)  # corners of the frame the source does not reach (other CRS only)
        zs = np.nan_to_num(zs, nan=0.0)
        full = np.where(outside, np.nan, zs).astype("float32")
        nor = full.copy()
        # smoothing lifts narrow fjord floors above 0 and the coast polygon is coarser than the cell: keep a one-cell margin round Norway
        near_norway = binary_dilation(norway, iterations=1)
        nor[~near_norway & ((zs >= 0) | land)] = np.nan
        variants = {"full": full, "norway": nor}
        for name, z in variants.items():
            stem = f"{region}{tag}_{lod}_{name}"
            write_irap(out / f"{stem}_zdown.irap", -z, tr)
            write_tif(out / f"{stem}_elevation.tif", z, tr, crs, {**tags, "z": "elevation, sea negative", "variant": name})
            title = {"full": "Elevation and bathymetry, North Sea basin and surrounds",
                     "norway": "Elevation and bathymetry, Norway land only"}[name]
            note = (f"Smoothed surface, {cell:,.0f} m cells (Relief {lod} level, sigma {cfg['sigma_cells']}). "
                    + ("Land of other countries is null (grey)." if name == "norway" else "Land tint by climate zone; sea floor on the shelf scale to 1,300 m."))
            preview(out / f"{stem}_preview.png", np.nan_to_num(z, nan=0.0), weights, cell, title, note, label, null=np.isnan(z))
            stats[stem] = {"z_min": float(np.nanmin(z)), "z_max": float(np.nanmax(z)), "null_cells": int(np.isnan(z).sum()), "shape": list(z.shape)}
        if lod == "regional":
            kg = np.where(land & (cls > 0), cls, 0).astype("float32")
            kg[kg == 0] = np.nan
            write_irap(out / f"{region}{tag}_{lod}_koppen.irap", kg, tr)
            write_tif(out / f"{region}{tag}_{lod}_koppen.tif", kg, tr, crs, {**tags, "z": "Köppen-Geiger class code 1-30 (Beck and others 2023)", "confidence": "Observed, modelled climate"})
            codes, n = np.unique(kg[~np.isnan(kg)].astype(int), return_counts=True)
            counts = dict(zip(codes.tolist(), n.tolist()))
            write_koppen_legend(out, counts)
            colour = np.zeros(zs.shape + (3,), dtype=np.float32) + 255
            for k in counts:
                colour[kg == k] = kg_colour(k, list(counts))
            preview(out / f"{region}{tag}_{lod}_koppen_preview.png", zs, weights, cell, "Climate zones (Köppen-Geiger) on the smoothed surface",
                    "Hue by zone group, lightness by class; sea is white. See koppen_legend.csv.", label, climate=np.where(np.isnan(kg)[..., None], 255, colour))
            stats[f"{region}{tag}_{lod}_koppen"] = {"classes": {KG[k]: v for k, v in counts.items()}}
        print(f"{lod}: {zs.shape[1]}x{zs.shape[0]} at {cell:.0f} m, {time.time() - t0:.0f} s")
    write_colour_tables(out)
    write_bars(out)
    (out / "ATTRIBUTION.txt").write_text("\n".join(ATTRIBUTION) + "\n", encoding="utf-8")
    shared = ("colourbar_", "koppen_legend", "ATTRIBUTION")
    files = sorted(p.name for p in out.iterdir() if p.is_file() and (p.name.startswith(shared) or p.name.startswith(f"{region}{tag}_") and not (not tag and "_utm31_" in p.name)))
    runs.write_text(json.dumps({"fingerprint": fp, "files": files, "stats": stats, "built": time.strftime("%Y-%m-%d")}, indent=1))
    print(f"wrote {len(files)} files to {out}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("region", nargs="?", default="ne_europe")
    p.add_argument("--lods", default="regional,detail")
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--crs", default=None, help="output CRS, default the region CRS; EPSG:25831 for UTM 31N")
    a = p.parse_args()
    return run(a.region, a.lods.split(","), a.force, a.dry_run, a.crs)


if __name__ == "__main__":
    sys.exit(main())
