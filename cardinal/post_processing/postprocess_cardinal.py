"""Plot the final Cardinal coolant tallies using the mesh in the Exodus output."""

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.colors import Normalize
import numpy as np
from netCDF4 import Dataset

HERE = Path(__file__).resolve().parents[1]
RUN_DIR = HERE / "run"
PLOT_DIR = HERE / "plots"
CM_PER_M = 100
CM3_PER_M3 = 1e6


def decode_names(rows):
    return [row.tobytes().decode().strip("\x00 ") for row in rows]


def read_block_field(dataset, coordinates, block_name, field_name):
    """Return element vertices and final field values for one named block."""
    block_index = decode_names(dataset["eb_names"][:]).index(block_name) + 1
    field_index = decode_names(dataset["name_elem_var"][:]).index(field_name) + 1

    # Exodus connectivity uses one-based node indices.
    connectivity = np.asarray(dataset[f"connect{block_index}"][:], dtype=int) - 1
    values = dataset[f"vals_elem_var{field_index}eb{block_index}"][-1]
    if np.ma.getmaskarray(values).any() or not np.isfinite(values).all():
        raise ValueError(f"Missing or invalid values for {field_name} on {block_name}")
    return coordinates[connectivity], np.asarray(values) / CM3_PER_M3


def plot_heating(dataset, coordinates):
    fig, ax = plt.subplots(figsize=(8, 4), layout="constrained")
    for side in ("left", "right"):
        cells, heating = read_block_field(
            dataset, coordinates, f"{side}_channel", f"heating_{side}"
        )
        # Use physical y so the two profiles are aligned along the pipe.
        lower = cells[:, :, 1].min(axis=1)
        upper = cells[:, :, 1].max(axis=1)
        order = np.argsort(lower)
        edges = np.r_[lower[order], upper[order[-1]]]
        ax.stairs(heating[order], edges, baseline=None, label=side.title())
    ax.set(title="Coolant heating", xlabel="y [cm]", ylabel="Heating [W/cm³]")
    ax.legend()
    save_plot(fig, "heating_in_flow_channels.png")


def tritium_slice(cells, values):
    # Select the central axial layer and draw each element at its physical bounds.
    centers_y = np.round(cells[:, :, 1].mean(axis=1), decimals=10)
    layers = np.unique(centers_y)
    slice_y = layers[len(layers) // 2]
    in_slice = centers_y == slice_y
    lower = cells[in_slice].min(axis=1)
    upper = cells[in_slice].max(axis=1)
    rectangles = [
        [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]
        for (x0, _, z0), (x1, _, z1) in zip(lower, upper)
    ]
    return slice_y, rectangles, values[in_slice]


def plot_tritium(dataset, coordinates):
    slices = []
    for side in ("left", "right"):
        cells, values = read_block_field(
            dataset, coordinates, f"{side}_tritium", f"H3_{side}"
        )
        slices.append(tritium_slice(cells, values))

    # Use one normalization for both channel patches.
    norm = Normalize(vmin=0, vmax=max(values.max() for _, _, values in slices))
    fig, ax = plt.subplots(figsize=(8, 4), layout="constrained")
    for _, rectangles, values in slices:
        patches = PolyCollection(rectangles, array=values, cmap="viridis", norm=norm)
        ax.add_collection(patches)
    ax.autoscale_view()
    ax.set_aspect("equal")
    left_y, right_y = (item[0] for item in slices)
    location = (
        f"y = {left_y:g} cm" if np.isclose(left_y, right_y)
        else f"left y = {left_y:g} cm, right y = {right_y:g} cm"
    )
    ax.set(title=f"Tritium breeding at {location}", xlabel="x [cm]", ylabel="z [cm]")
    fig.colorbar(patches, ax=ax, label="Tritium production [atoms/s/cm³]")
    save_plot(fig, "tritium_breeding_in_flow_channels.png")


def save_plot(fig, filename):
    output = PLOT_DIR / filename
    fig.savefig(output, dpi=150)
    plt.close(fig)
    print(f"Wrote {output}")


def print_totals(csv_path):
    with csv_path.open() as handle:
        final_row = list(csv.DictReader(handle))[-1]
    print("Final block-integrated tallies")
    for name, unit in (
        ("heating_structure", "W"),
        ("heating_left", "W"),
        ("heating_right", "W"),
        ("tritium_left", "atoms/s"),
        ("tritium_right", "atoms/s"),
    ):
        print(f"  {name:18s} {float(final_row[name]):.6g} {unit}")


def main():
    with Dataset(RUN_DIR / "openmc_out.e") as dataset:
        if not len(dataset["time_whole"]) or dataset["time_whole"][-1] <= 0:
            raise SystemExit("No completed transport time step in run/openmc_out.e.")

        print_totals(RUN_DIR / "openmc_out.csv")
        PLOT_DIR.mkdir(exist_ok=True)
        coordinates = np.column_stack(
            [dataset[f"coord{axis}"][:] for axis in "xyz"]
        ) * CM_PER_M
        plot_heating(dataset, coordinates)
        plot_tritium(dataset, coordinates)


if __name__ == "__main__":
    main()
