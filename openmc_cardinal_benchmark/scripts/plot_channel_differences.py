"""Plot relative Cardinal − OpenMC difference on an XY slice of both channels."""
from pathlib import Path
import argparse
import csv

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import numpy as np
import openmc

RUN_DIR = Path(__file__).resolve().parents[1] / "run"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--k", type=int, default=None, help="Zero-based z bin; default: central z bin")
    parser.add_argument("--structure", choices=("steel", "air"), default="steel")
    args = parser.parse_args()
    suffix = "_air" if args.structure == "air" else ""
    with openmc.StatePoint(RUN_DIR / f"openmc{suffix}" / "statepoint.10.h5") as sp:
        meshes = {side: sp.get_tally(name=f"{side}_channel_mesh_tally").find_filter(openmc.MeshFilter).mesh
                  for side in ("left", "right")}
        scores = sp.get_tally(name="left_channel_mesh_tally").scores
    heating_score = next(score for score in scores if score in ("heating", "heating-local"))
    if args.k is None:
        args.k = int(meshes["left"].dimension[2]) // 2
    if any(not 0 <= args.k < mesh.dimension[2] for mesh in meshes.values()):
        parser.error("--k is outside a channel mesh")
    zs = [mesh.lower_left[2] + (args.k + 0.5) *
          (mesh.upper_right[2] - mesh.lower_left[2]) / mesh.dimension[2]
          for mesh in meshes.values()]
    if not np.allclose(zs, zs[0]):
        raise ValueError("Selected z bins have different physical centers")
    with (RUN_DIR / f"channel_comparison{suffix}.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    z = zs[0]
    fig, axes = plt.subplots(2, 2, figsize=(9, 10), layout="constrained")
    for r, (score, label) in enumerate([
        (heating_score, "Nuclear heating"),
        ("(n,Xt)", "Tritium"),
    ]):
        grids = []
        for side in ("left", "right"):
            nx, ny, _ = meshes[side].dimension
            grid = np.full((ny, nx), np.nan)
            selected = [row for row in rows if row["channel"] == side
                        and row["score"] == score and int(row["k"]) == args.k]
            for row in selected:
                o, c = float(row["openmc"]), float(row["cardinal"])
                value = 100 * (c - o) / max(abs(o), abs(c)) if max(abs(o), abs(c)) else 0
                grid[int(row["j"]), int(row["i"])] = value
            if np.isnan(grid).any():
                raise ValueError(f"Incomplete {side} {score} slice")
            grids.append(grid)
        limit = max(np.max(abs(g)) for g in grids) or 1
        for col, (side, grid, xmin, xmax) in enumerate(zip(
                ("Left", "Right"), grids,
                [meshes[s].lower_left[0] for s in ("left", "right")],
                [meshes[s].upper_right[0] for s in ("left", "right")])):
            ax = axes[r, col]
            im = ax.imshow(grid, origin="lower", extent=(xmin, xmax, meshes[side.lower()].lower_left[1], meshes[side.lower()].upper_right[1]),
                           aspect="equal", interpolation="nearest", cmap="RdBu_r",
                           norm=TwoSlopeNorm(vmin=-limit, vcenter=0, vmax=limit))
            ax.set(title=f"{side} channel · {label}", xlabel="x [cm]", ylabel="y [cm]")
        fig.colorbar(im, ax=list(axes[r]), label="Difference [%]")
    fig.suptitle(f"Signed relative difference: Cardinal − OpenMC\nXY slice at z = {z:g} cm", fontsize=14)
    fig.supxlabel("100 × (Cardinal − OpenMC) / max(|Cardinal|, |OpenMC|)")
    output = RUN_DIR / f"channel_difference_xy_relative_k{args.k}{suffix}.png"
    fig.savefig(output, dpi=180)
    plt.close(fig)
    print(output)


if __name__ == "__main__":
    main()
