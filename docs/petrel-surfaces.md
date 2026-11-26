# Petrel surfaces

Smoothed elevation and bathymetry grids for Petrel, cut from a frame's merged grid by `scripts/petrel_surfaces.py`. The surface is Relief's own generalisation by scale: the merged grid is averaged to the level's cell, then Gaussian-smoothed by that level's sigma in cells (regional 2,000 m and 1.0; detail 800 m and 0.8). Nothing else resamples the terrain.

```
uv run python scripts/petrel_surfaces.py ne_europe [--lods regional,detail] [--force] [--dry-run]
```

Output is `data/out/ne_europe/petrel/` (not committed). A second run on the same inputs, settings and code stops with "unchanged".

## Products

| Product | Content |
|---|---|
| `*_full_*` | every cell: land heights and sea-floor depths |
| `*_norway_*` | sea floor everywhere; land only in Norway, with a one-cell margin; land of every other country is null |
| `*_koppen.*` | Köppen-Geiger class code (1 to 30) on land, null at sea; regional level only |

Each surface comes as `.irap` (Irap classic ASCII, Z positive down, 9999900 undefined; Petrel imports it as a surface), `.tif` (float32, elevation with sea negative, nodata NaN) and a `_preview.png`. Grid nodes sit at cell centres; the CRS is EPSG:3035 (ETRS89 / LAEA Europe), so the Petrel project needs that CRS or a transform. With `--crs EPSG:25831` the same products are written in ETRS89 / UTM zone 31N, named `ne_europe_utm31_*`: the merged grid is warped once by averaging and smoothed there, not smoothed and warped again. The frame is a rotated rectangle in UTM, because the east of it lies 24° from the zone's central meridian; cells outside the source are null (18 % of the grid), and distances and areas east of about 9 E are distorted. Heights at test points match the 3035 surface to within 1 m. The Irap value order was checked against xtgeo 4.28 and the GeoTIFFs; no Petrel session has read the files yet.

## Colour bars

- `colourbar_elevation.{svg,png}` and the colour tables `colourbar_elevation_stops.csv` and `colourbar_elevation_256.csv`: one bar, sea floor on the shelf ramp to 1,300 m (deeper is the same colour), land on the temperate ramp to 2,000 m.
- `colourbar_elevation_by_climate.{svg,png}` and `colourbar_land_by_climate_zone.csv`: the sea bar and one land bar per climate zone. The base maps blend these by zone, so height and zone together decide a land colour and no single bar can show both.
- `colourbar_koppen.{svg,png}` and `koppen_legend.csv`: the classes present, for the `koppen` surface. Hues are indicative.

A Petrel surface takes one colour table. Climate is therefore carried as its own surface (`koppen`) with its own table, beside the elevation surface, rather than inside one bar.

## Limits

Vertical datums differ: Copernicus heights are on EGM2008 and EMODnet depths on chart datum, so the step at the coast is not unified. Smoothing closes narrow fjords and raises their floors; use the 800 m level where that matters. The `ne_europe` frame stops at 62 N, the Sodir North Sea boundary, so Norway is cut there. Confidence: Derived.
