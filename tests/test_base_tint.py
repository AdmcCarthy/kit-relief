"""The base-tint stops mirror preview/palette.js; Detuned is linear sea and linear land, and the styles by height are as they are declared."""

import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import base_tint as bt

JS = (ROOT / "preview" / "palette.js").read_text(encoding="utf-8")


def js_list(name: str, theme: str) -> list[str]:
    block = re.search(name + r"\s*=\s*\{(.*?)\n\};", JS, re.DOTALL).group(1)
    row = re.search(theme + r":\s*\[(.*?)\]", block, re.DOTALL).group(1)
    return re.findall(r'"(#[0-9a-f]{6})"', row)


def test_sea_stops_match_palette_js():
    for theme in ("light", "dark"):
        assert bt.DETUNED_SEA[theme] == js_list("DETUNED_SEA", theme)
        assert bt.DETUNED_OCEAN[theme] == js_list("DETUNED_OCEAN", theme)


def test_land_stops_match_palette_js():
    zpal = re.search(r"ZPAL = \{(.*?)\n\};", JS, re.DOTALL).group(1)
    for theme in ("light", "dark"):
        block = re.search(theme + r":\s*\{(.*?)\n  \}", zpal, re.DOTALL).group(1)
        for zone in bt.ZONES:
            assert bt.ZPAL[theme][zone] == re.findall(r'"(#[0-9a-f]{6})"', re.search(zone + r":\s*\[(.*?)\]", block).group(1))
    assert bt.LB == [int(v) for v in re.search(r"LB = \[(.*?)\]", JS).group(1).split(",")]
    assert bt.SB == [int(v) for v in re.search(r"SB = \[(.*?)\]", JS).group(1).split(",")]


def test_land_is_a_linear_gradient_and_the_stepped_option_still_classes():
    z = np.linspace(0, 2000, 401, dtype=np.float32)
    w = np.zeros(z.shape + (4,), dtype=np.float32)
    w[..., 0] = 1  # all temperate
    land = bt.linear_land(z, w, "light")
    assert len({tuple(c) for c in np.round(land).astype(int)}) > 100, "a gradient, not eight classes"
    assert np.abs(np.diff(land, axis=0)).max() < 3, "no jump larger than a few levels between neighbouring heights"
    assert np.allclose(land[0], bt.tune(bt.ZPAL["light"]["temperate"][0], 0.5, 0.08), atol=1)  # the stops are the zone ramp, tuned
    assert len({tuple(c) for c in np.round(bt.stepped_land(z, w, "light")).astype(int)}) == len(bt.LB)


def test_sea_is_linear_and_land_is_stepped():
    t = np.linspace(0, 1, 101, dtype=np.float32)
    sea = bt.linear_ramp(t, bt.SB, bt.DETUNED_SEA["light"], bt.SMAX)
    lum = sea @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    assert np.all(np.diff(lum) <= 1e-3), "sea lightness falls with depth, with no steps back"
    assert len(np.unique(np.round(lum, 1))) > 60, "the sea ramp is a gradient, not a few steps"
    z = np.linspace(0, 2000, 401, dtype=np.float32)
    w = np.zeros(z.shape + (4,), dtype=np.float32)
    w[..., 0] = 1  # all temperate
    land = bt.stepped_land(z, w, "light")
    assert len({tuple(c) for c in np.round(land).astype(int)}) == len(bt.LB), "one colour per height class"


def test_styles_match_palette_js_and_terracotta_is_the_default():
    block = re.search(r"export const STYLES = (\{.*?\n\});", JS, re.DOTALL).group(1)
    assert json.loads(re.sub(r",\n\}$", "\n}", block)) == bt.STYLES
    assert bt.DEFAULT == "terracotta" == re.search(r'DEFAULT_STYLE = "(\w+)"', JS).group(1)


def test_a_stepped_style_is_classes_and_a_linear_one_a_gradient():
    z = np.concatenate([np.linspace(-2000, -1, 400), np.linspace(0, 2500, 400)])
    for name, st in bt.STYLES.items():
        tint = bt.style_tint(z, name)
        colours = len({tuple(c) for c in np.round(tint).astype(int)})
        if st["stepped"]:
            assert colours <= len(st["land"]) + len(st["sea"])
            assert np.allclose(tint[-1], bt.rgb(st["land"][-1][1])) and np.allclose(tint[0], bt.rgb([s for s in st["sea"] if s[0] <= 2000][-1][1]))
        else:
            assert colours > 100, name
        sea = tint[z < 0] @ np.array([0.2126, 0.7152, 0.0722])
        assert np.all(np.diff(sea) >= -0.6), f"{name}: the sea darkens with depth, with no steps back"


def test_the_arid_lowland_differs_and_the_highland_does_not():
    z = np.array([10.0, 1500.0])
    wet, dry = bt.style_tint(z, "terracotta", np.zeros(2)), bt.style_tint(z, "terracotta", np.ones(2))
    assert not np.allclose(wet[0], dry[0]) and np.allclose(wet[1], dry[1])


def test_flat_ground_keeps_its_tint_under_the_shade_and_slopes_do_not():
    z = np.array([[100.0, 100.0, -100.0]])
    for name in bt.STYLES:
        tint = bt.style_tint(z, name)
        flat = bt.shaded(tint, np.full(z.shape, 0.5), z, name)
        assert np.abs(flat - tint).max() < 1.5, name
        dark = bt.shaded(tint, np.full(z.shape, 0.2), z, name)
        assert (dark.sum(axis=-1) < tint.sum(axis=-1)).all(), name
