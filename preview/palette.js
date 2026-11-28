// Shared palette code: class breaks, cross-blended hypsometric tints by climate zone, the Detuned style and
// colour bars. Used by the region examples (regions.js) and the techniques page (demo.js).

// Non-linear steps (metres). Sea is finest near the coast, where most of the sea-floor shape is; land is coarser.
export const LB = [0, 50, 150, 300, 600, 1000, 1500, 2000];
export const SB = [0, 20, 50, 100, 200, 500, 1000];
export const LMAX = 2000, SMAX = 1300;
export const at = (breaks, cols, max) => breaks.map((b, i) => [b / max, cols[i]]).concat(cols.length > breaks.length ? [[1, cols.at(-1)]] : []);

// Cross-blended hypsometric tints (Patterson & Jenny): one land ramp per climate zone below 1,000 m and a shared
// alpine ramp above. ZPAL is the full-strength "relief" set; every other style is derived from it by detuning.
export const ZPAL = {
  light: {
    temperate: ["#d6e8b8", "#c6dea0", "#bad38f", "#cbcf92", "#d9c897", "#ccb8a0", "#d8d0c6", "#efece8"],
    boreal: ["#a9c7a6", "#97bb98", "#8aae8c", "#93a98b", "#a8ad96", "#ccb8a0", "#d8d0c6", "#efece8"],
    tundra: ["#e0e3dc", "#d6dad2", "#cdd1c9", "#c6c8c0", "#c4c0b6", "#ccb8a0", "#d8d0c6", "#efece8"],
    arid: ["#efe2c2", "#e9d6ac", "#e1c695", "#d6b382", "#c9a077", "#ccb8a0", "#d8d0c6", "#efece8"],
    sea: ["#e3f2f9", "#c6e5f3", "#a6d3eb", "#82bde0", "#5fa3d2", "#3f85bd", "#29689f", "#1b4f80"],
  },
  dark: {
    temperate: ["#46572f", "#4c5d33", "#536237", "#5d633b", "#665f42", "#655d50", "#85807a", "#aaa6a1"],
    boreal: ["#2c4232", "#304836", "#354d39", "#3f513e", "#4e5547", "#655d50", "#85807a", "#aaa6a1"],
    tundra: ["#55595a", "#585b5b", "#5b5d5c", "#5e5e5b", "#615d57", "#655d50", "#85807a", "#aaa6a1"],
    arid: ["#5e533c", "#665a3f", "#6c5c40", "#6e5a43", "#6a5747", "#655d50", "#85807a", "#aaa6a1"],
    sea: ["#2f7896", "#286a87", "#225c78", "#1c4e69", "#16405a", "#11334b", "#0c263c", "#081c2e"],
  },
};
// "Detuned": the sea floor gets more room than the land (wider range, deeper indigo) while land is held back.
export const DETUNED_SEA = {
  light: ["#e8f0f2", "#cfe1e6", "#aacdd8", "#7eb0c5", "#5891ae", "#3a6d94", "#264b73", "#162b50"],
  dark: ["#3a8aa2", "#2f7690", "#25647d", "#1c526b", "#144157", "#0e3045", "#092336", "#06172a"],
};
// Ocean ramp for basins and the world (scripts/depth_ramp.py designs and checks it in OKLCH): the shelf ramp above uses
// up all its lightness by 1,300 m, so 76 % of the world's ocean floor (2,000 to 6,000 m, where spreading ridges, flanks,
// fracture zones and abyssal plains lie) is one colour. This one spreads a steady lightness step over 7,000 m.
export const OCEAN_SB = [0, 200, 1000, 2000, 3000, 4000, 5000, 6000, 7000], OCEAN_MAX = 7000;
export const DETUNED_OCEAN = {
  light: ["#e2f4f9", "#bfe2ed", "#83bddc", "#5c9acd", "#4579ba", "#355a9f", "#2a3e80", "#1e2763", "#131546"],
  dark: ["#71b7c8", "#56a5bd", "#2c83aa", "#1d679c", "#154b8a", "#113375", "#101e5c", "#0a0b42", "#040027"],
};
// Styles by height (2026-11-28): Terracotta is the default base of the light theme, the others are asked for by name. Stops are [metres, colour]; a stepped
// style gives a class the colour of its lower stop, a linear one runs between the stops in OKLab. Mirrors STYLES in scripts/base_tint.py (tests keep them
// in step), which renders them; the examples on these pages still draw Detuned.
export const DEFAULT_STYLE = "terracotta";
export const STYLES = {
  "terracotta": {"name": "Terracotta", "stepped": true, "land": [[0, "#b3bd74"], [60, "#cfd596"], [150, "#e6e2b8"], [300, "#f2dfc0"], [500, "#eec7a2"], [800, "#e0a380"], [1100, "#cd7f5e"], [1400, "#b55f43"], [1700, "#964734"], [2000, "#803b2d"], [2400, "#f7f3ee"]], "arid": [[0, "#f1d8b4"], [60, "#f3dcbc"], [150, "#f4dfc4"], [300, "#f2dfc0"], [500, "#eec7a2"], [800, "#e0a380"], [1100, "#cd7f5e"], [1400, "#b55f43"], [1700, "#964734"], [2000, "#803b2d"], [2400, "#f7f3ee"]], "sea": [[0, "#fcfbf7"], [40, "#f1f5f2"], [80, "#e2eeec"], [120, "#d0e4e5"], [200, "#b5d3da"], [350, "#8fbac8"], [600, "#6a9db3"], [1000, "#4a7f9b"], [1600, "#335f7e"], [2300, "#22445f"], [3200, "#18344c"], [4500, "#10263a"]], "shade": {"land": 1.25, "sea": 1.25}},
  "seabed": {"name": "Sea floor first", "stepped": false, "land": [[0, "#ebe8e2"]], "sea": [[0, "#f7faf8"], [30, "#e6f1ef"], [60, "#d3e7e6"], [90, "#bfdcdd"], [130, "#a6cdd2"], [200, "#88b9c4"], [350, "#6a9fb2"], [700, "#4a7d98"], [1500, "#2f587a"], [2700, "#1c3a5a"], [4500, "#112842"]], "shade": {"land": 0.6, "sea": 1.6}},
  "night": {"name": "Night chart", "stepped": false, "land": [[0, "#3b3a37"], [300, "#4a4743"], [800, "#665f55"], [1400, "#8d8271"], [2000, "#c2b7a3"]], "sea": [[0, "#3c5f70"], [50, "#2f4f61"], [120, "#254253"], [250, "#1b3445"], [600, "#132737"], [1500, "#0c1b29"], [2700, "#07121d"], [5000, "#040b13"]], "shade": {"land": 1.5, "sea": 1.5, "tint": ["#05090d", "#e8d9b8", 0.55]}},
  "shell": {"name": "Shell and slate", "stepped": false, "land": [[0, "#dfe6e2"], [100, "#cdd8d3"], [300, "#b4c4c1"], [600, "#98abb0"], [1000, "#7d8f9e"], [1500, "#66758c"], [1900, "#f4f5f7"]], "sea": [[0, "#fdf8f3"], [50, "#f7ebe4"], [100, "#f0dcd5"], [160, "#e6c9c4"], [300, "#d3aab0"], [700, "#b3889b"], [1500, "#8a6685"], [2700, "#5f4a6e"], [4500, "#44365a"]], "shade": {"land": 1.2, "sea": 1.2}},
  "air": {"name": "Mountain air", "stepped": false, "land": [[0, "#b7c8c6"], [100, "#c3d0c4"], [300, "#d3d8bf"], [600, "#e6debb"], [1000, "#f4e4bd"], [1500, "#f7dcc6"], [2000, "#fdf6ee"]], "sea": [[0, "#f3f6f7"], [60, "#e3ebef"], [130, "#cfdbe4"], [300, "#b0c3d4"], [800, "#869fbd"], [1600, "#62799f"], [2700, "#465781"], [4500, "#33416a"]], "shade": {"land": 1.5, "sea": 1.5, "tint": ["#4f4d85", "#fff4c8", 0.6]}},
};
export const ZK = ["temperate", "boreal", "tundra", "arid"];

export const rgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
export const hexOf = (v) => "#" + v.map((x) => Math.round(Math.min(255, Math.max(0, x))).toString(16).padStart(2, "0")).join("");
// Detune a colour: scale its saturation towards its own grey, then lift (mix > 0, towards white) or sink (< 0, towards black).
export function tune(h, sat, mix = 0) {
  const c = rgb(h), y = 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2], t = mix > 0 ? 255 : 0, m = Math.abs(mix);
  return hexOf(c.map((v) => { const g = y + (v - y) * sat; return g + (t - g) * m; }));
}

// The house style, fixed for the region examples: land tints at half strength (a linear gradient, one ramp per climate
// zone), the sea floor on its own wide indigo ramp as a LINEAR gradient, both under the sky shade (soft light x the sky-view
// factor; land 0.35, sea 0.9, ocean basins 0.8) when a pixel scale is given. No contours, no coastline.
// Returned in the shape relief.js draws: `stepped` applies to land, `seaStepped` is false.
export function detunedStyle(theme, bathymetry = "shelf", mpp = 0, tune_ = null) {
  const dark = theme === "dark", Z = ZPAL[theme], ocean = bathymetry === "ocean";
  const land = Object.fromEntries(ZK.map((k) => [k, at(LB, Z[k].map((c) => tune(c, 0.5, dark ? -0.08 : 0.08)), LMAX)]));
  const sea = ocean ? at(OCEAN_SB, DETUNED_OCEAN[theme], OCEAN_MAX) : at(SB, DETUNED_SEA[theme], SMAX);
  return { land: land.temperate, zones: land, sea, landMax: LMAX, seaMax: ocean ? OCEAN_MAX : SMAX, landStops: LB, seaStops: ocean ? OCEAN_SB : SB,
    seaTicks: ocean ? [0, 1000, 2000, 3000, 4000, 5000, 6000] : [0, 250, 500, 1000],
    stepped: false, seaStepped: false, contours: "none", coast: false, ice: false,  // linear land and sea since 2026-11-15
    ...(mpp > 0 ? { shade: "sky", shadeK: 0.35, seaShadeK: 0.9, exag: landExag(mpp), landExag: landExag(mpp), alt: 40 } : { shade: "none" }),
    ...(ocean && mpp > 0 ? oceanShade(mpp, tune_) : {}) };
}

// The house exaggeration rule, with the metres each screen pixel covers as the cell: 2 x, growing beyond 1 km per pixel
// so relief does not go flat as the map zooms out (the same rule as scripts/sky_view.py for the shipped shade).
export function landExag(mpp) {
  return 2 * Math.max(1, mpp / 1000);
}

// Ocean basins: fracture zones, ridge-parallel abyssal hills and trenches are a few hundred metres on grids of 2 to 20 km,
// too faint for colour alone at the full-basin view, so the sea floor takes far more exaggeration than the land beside it
// (`exag`; land keeps `landExag`). The sky model (soft light x the baked sky-view factor, relief.js) is the default; without
// a baked texture it falls back to soft light.
export function oceanShade(mpp, t = null) {
  const exag = t?.exag ?? Math.min(40, Math.max(4, mpp / 1500));  // about 14 at 21 km per pixel (the Atlantic fitted to a screen)
  return { shade: "sky", seaShadeK: t?.k ?? 0.8, exag, alt: 40 };
}

// ---------------------------------------------------------------- colour bars
// Same interpolation as the shader's ramp texture, so a bar shows exactly the colours on the map.
export function rampAt(stops, t) {
  t = Math.min(1, Math.max(0, t)); let k = 0;
  while (k < stops.length - 2 && t > stops[k + 1][0]) k++;
  const [t0, c0] = stops[k], [t1, c1] = stops[k + 1], f = Math.min(1, Math.max(0, (t - t0) / (t1 - t0 || 1)));
  const a = rgb(c0), b = rgb(c1);
  return `rgb(${a.map((v, j) => Math.round(v + (b[j] - v) * f)).join(",")})`;
}
export const fmtM = (v) => v.toLocaleString("en-GB");

// One block per class, labelled with its range (stepped), or a continuous gradient (linear).
export function strip(label, stops, max, bands, stepped) {
  if (stepped) {
    const cells = bands.map((lo, i) => {
      const hi = bands[i + 1];
      const mid = hi == null ? lo + (lo - bands[i - 1]) / 2 : (lo + hi) / 2;
      return `<span class="cb-band" style="background:${rampAt(stops, mid / max)}" title="${fmtM(lo)}${hi == null ? "+" : `–${fmtM(hi)}`} m"></span>`;
    }).join("");
    return `<span class="cb-l">${label}</span><div class="cb-steps" style="--n:${bands.length}">${cells}</div>`;
  }
  const grad = Array.from({ length: 24 }, (_, i) => `${rampAt(stops, i / 23)} ${(i / 23 * 100).toFixed(1)}%`).join(",");
  return `<span class="cb-l">${label}</span><div class="cb-lin" style="background:linear-gradient(90deg,${grad})"></div>`;
}
export function axis(max, bands, stepped, ticks) {
  if (stepped) return `<span></span><div class="cb-labs" style="--n:${bands.length}">${bands.map((v, i) => `<span>${fmtM(v)}${i === bands.length - 1 ? "+" : ""}</span>`).join("")}<span></span></div>`;
  const tk = ticks.filter((v) => v / max < 0.85).map((v) => `<span style="left:${(v / max) * 100}%">${fmtM(v)}</span>`).join("");
  return `<span></span><div class="cb-ticks">${tk}<span style="left:100%">${fmtM(max)}+</span></div>`;
}

// Legend for the Detuned style: one linear height gradient per climate zone present, then a linear depth gradient.
export function regionBars(st, share) {
  const present = ZK.filter((k) => k !== "arid" || (share && share.arid > 0.005));
  const names = { temperate: "Temperate", boreal: "Boreal", tundra: "Tundra", arid: "Arid" };
  return `<div class="cbs"><span class="cb-kind">Relief: linear by climate zone, m · Bathymetry: linear, m</span><div class="cbg">` +
    present.map((k) => strip(names[k], st.zones[k], st.landMax, st.landStops, false)).join("") + axis(st.landMax, st.landStops, false, [0, 500, 1000, 1500]) +
    strip("Depth", st.sea, st.seaMax, st.seaStops, false) + axis(st.seaMax, st.seaStops, false, st.seaTicks ?? [0, 250, 500, 1000]) + "</div></div>";
}
