"""Build the Glasgow 2019 case study from Landsat 8 Collection 2 and an LST/land-cover workflow.

Inputs (not stored in the repository):
  * Landsat 8 Collection 2 Level-2 scene LC08_L2SP_205021_20190628_20200827_02_T1 (SR_B4, SR_B5)
  * Land-surface temperature in deg C on the same 30 m grid (Sobrino single-channel workflow, ENVI)
  * Maximum-likelihood land-cover classification on the same grid
  * A city boundary polygon (any CRS readable by pyproj; British National Grid here)

The script crops to the boundary, marks everything outside it as class 0, writes the aligned
scene to ``results/glasgow_scene.npz`` (small enough to commit) and runs the package's
``run_scene`` analysis on it, then draws the case-study figures.

Requires numpy, matplotlib, tifffile, pyshp and pyproj (see case-studies/requirements.txt).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
from urban_heat_explorer.data import CLASSES, UrbanScene  # noqa: E402
from urban_heat_explorer.demo import run_scene  # noqa: E402

SR_SCALE, SR_OFFSET = 0.0000275, -0.2  # Landsat Collection 2 surface reflectance


def read_grid(path: Path):
    import tifffile

    with tifffile.TiffFile(path) as tif:
        page = tif.pages[0]
        tie = page.tags["ModelTiepointTag"].value
        scale = page.tags["ModelPixelScaleTag"].value
        raster_type = 1
        geokeys = page.tags.get("GeoKeyDirectoryTag")
        if geokeys is not None:
            keys = geokeys.value
            for i in range(4, len(keys), 4):
                if keys[i] == 1025:  # GTRasterTypeGeoKey: 1 = PixelIsArea, 2 = PixelIsPoint
                    raster_type = keys[i + 3]
        x0, y0 = tie[3], tie[4]
        if raster_type == 2:  # tie point is a pixel centre; shift to the corner
            x0, y0 = x0 - scale[0] / 2, y0 + scale[1] / 2
        return tifffile.memmap(path) if page.is_memmappable else page.asarray(), (x0, y0, scale[0])


def window(arr, grid, bounds):
    x0, y0, size = grid
    c0, c1 = int((bounds[0] - x0) // size), int(np.ceil((bounds[2] - x0) / size))
    r0, r1 = int((y0 - bounds[3]) // size), int(np.ceil((y0 - bounds[1]) / size))
    return np.array(arr[r0:r1, c0:c1]), (x0 + c0 * size, y0 - r0 * size, size)


def polygon_mask(shape, grid, rings):
    x0, y0, size = grid
    x = x0 + (np.arange(shape[1]) + 0.5) * size
    y = y0 - (np.arange(shape[0]) + 0.5) * size
    xx, yy = np.meshgrid(x, y)
    inside = np.zeros(shape, dtype=bool)
    for ring in rings:  # even-odd rule across all rings handles holes
        for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
            crosses = (y1 > yy) != (y2 > yy)
            with np.errstate(divide="ignore", invalid="ignore"):
                x_at = x1 + (yy - y1) * (x2 - x1) / (y2 - y1)
            inside ^= crosses & (xx < x_at)
    return inside


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--landsat-prefix", required=True, help="Path prefix ending in ..._02_T1_ (SR_B4.TIF is appended)")
    ap.add_argument("--lst", type=Path, required=True)
    ap.add_argument("--classification", type=Path, required=True)
    ap.add_argument("--boundary", type=Path, required=True)
    args = ap.parse_args(argv)

    import pyproj
    import shapefile

    case = json.loads((HERE / "case.json").read_text(encoding="utf-8"))
    lst_full, grid = read_grid(args.lst)
    shp = shapefile.Reader(str(args.boundary))
    source_crs = pyproj.CRS.from_wkt(args.boundary.with_suffix(".prj").read_text())
    to_grid = pyproj.Transformer.from_crs(source_crs, case["grid_epsg"], always_xy=True)
    shape0 = shp.shape(0)
    parts = list(shape0.parts) + [len(shape0.points)]
    rings = [[to_grid.transform(*p) for p in shape0.points[a:b]] for a, b in zip(parts[:-1], parts[1:])]
    xs = [p[0] for r in rings for p in r]
    ys = [p[1] for r in rings for p in r]
    bounds = (min(xs) - 60, min(ys) - 60, max(xs) + 60, max(ys) + 60)

    lst, sub = window(lst_full, grid, bounds)
    cls_full, cls_grid = read_grid(args.classification)
    red_full, red_grid = read_grid(Path(f"{args.landsat_prefix}SR_B4.TIF"))
    nir_full, nir_grid = read_grid(Path(f"{args.landsat_prefix}SR_B5.TIF"))
    for name, g in (("classification", cls_grid), ("SR_B4", red_grid), ("SR_B5", nir_grid)):
        if any(abs(a - b) > 1e-6 for a, b in zip(g, grid)):
            raise ValueError(f"{name} grid {g} differs from LST grid {grid}")
    cls, _ = window(cls_full, grid, bounds)
    red_dn, _ = window(red_full, grid, bounds)
    nir_dn, _ = window(nir_full, grid, bounds)

    mapping = {int(k): v for k, v in case["class_map"].items()}
    land_cover = np.zeros(cls.shape, dtype="int16")
    for source, target in mapping.items():
        land_cover[cls == source] = target
    inside = polygon_mask(lst.shape, sub, rings)
    valid = inside & np.isfinite(lst) & (red_dn > 0) & (nir_dn > 0) & (land_cover > 0)
    land_cover[~valid] = 0
    red = np.where(valid, np.clip(red_dn * SR_SCALE + SR_OFFSET, 0, None), 0).astype("float32")
    nir = np.where(valid, np.clip(nir_dn * SR_SCALE + SR_OFFSET, 0, None), 0).astype("float32")
    lst_c = np.where(valid, lst, 0).astype("float32")

    out = HERE / "results"
    out.mkdir(exist_ok=True)
    np.savez_compressed(out / "glasgow_scene.npz", red=red, nir=nir, lst_c=lst_c, land_cover=land_cover.astype("uint8"),
                        origin_xy=np.array(sub[:2]), pixel_m=np.array(sub[2]))
    scene = UrbanScene(red, nir, lst_c, land_cover, resolution_m=sub[2], provenance=case["provenance"])
    paths = run_scene(scene, out)
    summary = json.loads(paths["summary"].read_text(encoding="utf-8"))
    summary.update({"scene": case["scene"], "grid_epsg": case["grid_epsg"], "lst_method": case["lst_method"],
                    "classification": case["classification"], "boundary_note": case["boundary_note"]})
    paths["summary"].write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for code, name in CLASSES.items():
        print(f"{name:10s} {np.count_nonzero(land_cover == code) * sub[2] ** 2 / 1e6:6.1f} km2")
    draw_figures(out, scene, sub, case)
    print(json.dumps({k: summary[k] for k in ("pixels", "mean_lst_c", "lst_sd_c", "heat_island_core_area_pct", "ndvi_lst_regression")}, indent=2))
    return 0


def draw_figures(out: Path, scene: UrbanScene, grid, case) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch

    from urban_heat_explorer.analysis import analyse_scene

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": "#55606a",
                         "axes.labelcolor": "#17212b", "xtick.color": "#3c4650", "ytick.color": "#3c4650"})
    ndvi, uhi, priority, land, uhi_rows, scenarios, summary = analyse_scene(scene)
    inside = scene.land_cover > 0
    x0, y0, size = grid
    h, w = scene.lst_c.shape
    extent = [0, w * size / 1000, 0, h * size / 1000]
    note = case["figure_note"]

    def frame(ax, title, subtitle):
        ax.set_xlabel("km east")
        ax.set_ylabel("km north")
        ax.set_facecolor("#eef0f1")
        ax.set_title(subtitle, loc="left", fontsize=8.5, color="#55606a")
        ax.annotate(title, xy=(0, 1), xycoords="axes fraction", xytext=(0, 22), textcoords="offset points",
                    fontsize=12.5, fontweight="bold", va="bottom")

    lst = np.where(inside, scene.lst_c, np.nan)
    fig, ax = plt.subplots(figsize=(8, 6.6), dpi=150)
    im = ax.imshow(lst, extent=extent, cmap="inferno", vmin=np.nanpercentile(lst, 2), vmax=np.nanpercentile(lst, 98),
                   interpolation="nearest")
    frame(ax, "Glasgow land-surface temperature, 28 June 2019", note)
    fig.colorbar(im, ax=ax, shrink=0.8, pad=0.02).set_label("LST (°C)")
    fig.savefig(out / "lst_map.png", bbox_inches="tight", pad_inches=0.2)
    plt.close(fig)

    colours = ("#c8553d", "#3d7ea6", "#2e6b3f", "#a7c36b")
    cover = np.where(inside, scene.land_cover, np.nan)
    fig, ax = plt.subplots(figsize=(8, 6.6), dpi=150)
    ax.imshow(cover, extent=extent, cmap=ListedColormap(colours), vmin=0.5, vmax=4.5, interpolation="nearest")
    handles = [Patch(color=c, label=f"{row['land_cover']} · {row['mean_lst_c']:.1f} °C mean")
               for c, row in zip(colours, land)]
    ax.legend(handles=handles, loc="lower left", fontsize=8.5, framealpha=0.92)
    frame(ax, "Land cover and its mean surface temperature", "Maximum-likelihood classification of Landsat 8 OLI")
    fig.savefig(out / "land_cover_map.png", bbox_inches="tight", pad_inches=0.2)
    plt.close(fig)

    shown = np.where(priority > 0, priority, np.nan)
    fig, ax = plt.subplots(figsize=(8, 6.6), dpi=150)
    ax.imshow(np.where(inside, 0.0, np.nan), extent=extent, cmap=ListedColormap(["#dfe3e6"]), interpolation="nearest")
    im = ax.imshow(shown, extent=extent, cmap="YlOrRd", vmin=0, vmax=np.nanpercentile(shown, 98), interpolation="nearest")
    area = scenarios[0]["eligible_built_up_area_km2"]
    frame(ax, "Where greening could cool the hottest built-up land",
          f"Hot (≥ +0.35 SD) built-up pixels with NDVI < 0.35 · {area:.1f} km² eligible · grey = rest of city")
    fig.colorbar(im, ax=ax, shrink=0.8, pad=0.02).set_label("Screening priority (heat z-score × (1 − NDVI))")
    fig.savefig(out / "intervention_priority_map.png", bbox_inches="tight", pad_inches=0.2)
    plt.close(fig)

    reg = summary["ndvi_lst_regression"]
    rng = np.random.default_rng(3)
    idx = rng.choice(np.flatnonzero(inside), 4000, replace=False)
    fig, ax = plt.subplots(figsize=(8, 4.4), dpi=150)
    for code, colour in zip(CLASSES, colours):
        pick = idx[scene.land_cover.ravel()[idx] == code]
        ax.scatter(ndvi.ravel()[pick], scene.lst_c.ravel()[pick], s=4, alpha=0.35, color=colour, label=CLASSES[code])
    xs = np.linspace(np.nanmin(ndvi[inside]), np.nanmax(ndvi[inside]), 50)
    ax.plot(xs, reg["slope_c_per_ndvi"] * xs + reg["intercept_c"], color="#111", lw=1.6)
    lo, hi = reg["bootstrap_slope_ci_95"]
    ax.set_title(f"{reg['slope_c_per_ndvi']:.1f} °C per unit NDVI · bootstrap 95% CI {lo:.1f} to {hi:.1f} · "
                 f"R² = {reg['r_squared']:.2f} · n = {reg['sample_size']} random pixels (4,000 plotted)",
                 loc="left", fontsize=8.5, color="#55606a")
    ax.annotate("Greener pixels are cooler", xy=(0, 1), xycoords="axes fraction", xytext=(0, 20),
                textcoords="offset points", fontsize=12.5, fontweight="bold", va="bottom")
    ax.set_xlabel("NDVI")
    ax.set_ylabel("LST (°C)")
    ax.grid(alpha=0.25)
    ax.legend(markerscale=3, fontsize=8, loc="upper right")
    fig.savefig(out / "ndvi_lst_scatter.png", bbox_inches="tight", pad_inches=0.2)
    plt.close(fig)


if __name__ == "__main__":
    raise SystemExit(main())
