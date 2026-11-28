# Base maps for other repos

Written 2026-11-10. Relief owns the look of the terrain under other people's data, so that look is rendered once here
and drawn as it is everywhere else. Nobody specifies it per map.

## Styles by height, and Terracotta as the default (2026-11-28)

By the owner's decision of 28 November 2026 the base of the light theme is **Terracotta**: stepped classes of height that
change hue (olive lowland, cream, salmon, terracotta, snow above 2,400 m) and stepped classes of water depth from paper
white on the shelf to petrol in deep water, after Nadieh Bremer's world map. Lowland in an arid climate takes a sand tint
in place of the olive (the arid weight of the climate zones); nothing else is blended by climate. Detuned, described below,
stays as the base of the dark theme and as a named file.

`scripts/base_tint.py` holds the styles (`STYLES`, mirrored in `preview/palette.js`): `terracotta`, `seabed` (Sea floor
first: land one tone, all colour at sea, most of it above 200 m of water), `night` (Night chart: dark water, charcoal land,
a coloured shade), `shell` (Shell and slate: pink to plum sea, sage to slate land) and `air` (Mountain air: hazy lowland,
cream heights, a violet and yellow shade). For each region it writes:

- `regional_base_light.png` and `.webp`: the flat Terracotta tint (`base.regional.light`). `base.depth_scale` and
  `base.land_scale` now describe classes and carry the colours (`stops`: `[metres, colour]`, `stepped: true`), so a
  consumer draws its keys from the manifest and copies no list.
- `regional_base_detuned.png` and `.webp`: the light base as it was (`base.detuned`).
- `regional_base_dark.png`: Detuned, as before.
- `ground/<style>.webp` (`base.ground`): the **finished ground** of every style, the tint with the sky shade laid on at
  the strength the style names for land and sea (in soft light, or towards two tones for a coloured shade). It is drawn at
  the cell of the demo elevation, twice as fine where that is coarser than about 800 m so that coasts and class edges
  are curves. A map that draws the terrain under its data and no hillshade over it (a printed sheet)
  takes this file; `base.ground.styles.<style>` gives the name, whether it is stepped, the stops within
  the frame's range and the shade.

A consumer that copied the Detuned stops for its keys shows the wrong key over the new light base until it reads the
stops from the manifest. The examples on Relief's own pages (gallery, zoom viewer, techniques) and the fine base
(`scripts/fine_base.py`) still draw Detuned.

## The rule for Detuned

A Detuned base map is, in this order from the bottom:

1. **Sea floor: a linear gradient** on the region's depth scale. Shelf regions (North Sea, NE Europe, Barents Sea,
   Vestland) run 0 to 1,300 m; ocean regions (Norwegian Sea, Atlantic, world) run 0 to 7,000 m. Both ramps are in
   `preview/palette.js` and `docs/depth-scale.md`; never stepped, never contoured.
2. **Land: a linear gradient** from 0 to 2,000 m on the climate zone ramps at half saturation (stops at 0, 50, 150, 300,
   600, 1,000, 1,500, 2,000 m), cross-blended by the Köppen-Geiger zone weights (Beck and others 2023), so lowland tints
   vary with climate and the uplands share one alpine ramp. Stepped classes were the rule until 2026-11-15.
3. The consumer's own data.
4. **Hillshade** on top, composited so the terrain shows through the data (soft-light; the consumer remaps the PNG so flat
   ground is mid grey until the hillshade is written neutral).
5. The depth key, read from the manifest, drawn as a linear bar with the ticks the manifest names.

## The product

```
uv run python scripts/base_tint.py ne_europe north_sea norwegian_sea
# the Köppen-Geiger raster these need is fetched on first use (scripts/fetch_climate.py, 131 MB, md5-checked)
```

writes, for each region, `data/out/<region>/regional_base_light.png` and `regional_base_dark.png` (RGB, the regional
LOD grid, the region's extent, from the demo elevation texture and `zones.png`) and records in `manifest.json`:

```json
"base": {
  "regional": {"light": "regional_base_light.png", "dark": "regional_base_dark.png"},
  "style": "Detuned: linear bathymetry on the shelf depth scale, linear land cross-blended by climate zone",
  "depth_scale": {"kind": "shelf", "max_m": 1300, "ticks_m": [0, 250, 500, 1000]},
  "land_scale": {"max_m": 2000, "ticks_m": [0, 500, 1000, 1500], "stops_m": [0, 50, 150, 300, 600, 1000, 1500, 2000]},
  "land_classes_m": [0, 50, 150, 300, 600, 1000, 1500, 2000],
  "note": "Draw this image with an identity transform in the frame extent, your data over it, then the hillshade."
}
```

The same script writes the **web assets** a page should fetch instead of the PNGs: `regional_base_{light,dark}.webp`
(lossy, quality 85, about a fifth of the PNG: 68 KB against 576 KB for NE Europe) and `regional_shade.webp`, the regional
hillshade with flat ground at mid grey and the slopes stretched 2.5 times (130 KB against 460 KB), which a page composites
with soft-light as it is, with no remapping pass over the pixels. The manifest lists them under `base.webp` and
`base.shade`. A page that has the base needs the bands only for a key, and the manifest's `land_scale` and
`depth_scale` give that (both linear bars now; `land_classes_m` stays for pages that still draw classes), so the 470 KB
`regional.geojson` is not fetched at all.

The files are part of the data release with the other layers (`scripts/publish_data.py`), so a consumer fetching a
release gets them with the hillshade and the bands.

## The fine base, for maps of small windows

A map of a 30 km window is 33 pixels of the regional tint and 100 of the detail hillshade. Where a region's merged grid is
finer than its levels of detail (`central_graben` is merged at 125 m), `scripts/fine_base.py` renders the same base at the
grid's own cell for a rectangle cut on whole cells:

```
uv run python scripts/fine_base.py central_graben --extent 130000 6060000 800000 6510000
```

writes `data/out/<region>/fine/`: `base_light.png` and `base_dark.png` (and WebP), by the same ramps and stops as the regional
tint; `hillshade.png`, the sky shade with flat ground at 180; `shade.png` and `shade.webp`, flat ground at 128 and slopes
stretched 2.5 times, for soft-light as it is; `elevation.tif`; and `manifest.json` (`fine_base: 1`) with the exact extent, cell,
size, CRS, depth scale and ticks, shade model, sources and attribution lines. The shade is computed with a margin of the
sky-view search radius and trimmed, at the house exaggeration (2 x); a flat shelf gets no more than that. A consumer
crops by whole cells and draws the crop with an identity transform. The folder ships with the region in a data release.

## Drawing it (d3, canvas)

```js
const man = await (await fetch(`${reliefDir}/manifest.json`)).json();
const img = new Image(); img.src = `${reliefDir}/${man.base.regional[dark ? "dark" : "light"]}`; await img.decode();
const [x0, y0, x1, y1] = man.extent, a = proj([x0, y1]), b = proj([x1, y0]);
ctx.drawImage(img, a[0], a[1], b[0] - a[0], b[1] - a[1]);     // 1 and 2
// ... your data ...                                           // 3
// ... hillshade, soft-light ...                               // 4
// depth key: a linear bar on the ramp for man.base.depth_scale.kind, ticks at man.base.depth_scale.ticks_m
```

The stops for the key are the same lists as `preview/palette.js` (`DETUNED_SEA`, `DETUNED_OCEAN`); a consumer that
needs them copies those two lists and says so. `tests/test_base_tint.py` keeps the Python and the JS stops identical.

## Why linear sea and, since 2026-11-15, linear land

Shelf bathymetry carries its information in gentle gradients (the Norwegian Trench's edge, the Dogger Bank, the Baltic
sills), which steps turn into false shorelines. Land was stepped from 2026-11-08 because hypsometric classes are a
convention readers know and gave a flat background between the steps. With the sky shade carrying the landforms
(docs/sky-view.md), the class edges became a second, false set of contours over them, so on 2026-11-15 land went linear
as well, in the examples, the zoom viewer and these base tints alike. The stepped classes remain as a technique on the
techniques page and as `stepped_land` in `base_tint.py`. This note makes the linear pair the default for every consumer
rather than a choice each map has to make.
