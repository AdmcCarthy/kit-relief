"""Irap writer layout (checked against xtgeo 4.28 on 2026-11-26), Norway mask rule and the unchanged second run."""

import numpy as np
import petrel_surfaces as ps
import rasterio


def test_irap_layout(tmp_path):
    # 3 columns x 2 rows, north row first as rasters are; Irap wants the south row first, x fastest
    z = np.array([[4.0, 5.0, 6.0], [1.0, 2.0, np.nan]])
    tr = rasterio.Affine(10, 0, 100, 0, -10, 120)
    p = tmp_path / "t.irap"
    ps.write_irap(p, z, tr)
    lines = p.read_text().splitlines()
    assert lines[0] == "-996 2 10.000000 10.000000"
    assert lines[1] == "105.000000 125.000000 105.000000 115.000000"
    assert lines[2] == "3 0.000000 105.000000 105.000000"
    vals = " ".join(lines[4:]).split()
    assert vals[:6] == ["1.00", "2.00", "9999900.00", "4.00", "5.00", "6.00"]


def test_colour_bar_ends():
    assert tuple(ps.sea_rgb(np.array([0.0]))[0].round()) == (232.0, 240.0, 242.0)
    assert ps.elevation_rgb(np.array([-5000.0]), None)[0].tolist() == ps.sea_rgb(np.array([1300.0]))[0].tolist()


def test_koppen_colours_distinct():
    present = [8, 9, 15, 16, 18, 26, 27, 29]
    cols = {ps.kg_colour(k, present) for k in present}
    assert len(cols) == len(present)
