"""Compare matching channel voxels, never interpolate or average unmatched bins.

Run pipe_model.py with RUN_OPENMC=1, then Cardinal with openmc.i, before this script.
Cardinal uses separate block-restricted unstructured meshes; standalone OpenMC
uses two RegularMeshes with identical HEX8 bins. Both use collision tallies.
"""
import argparse
from pathlib import Path
import csv
import re
import xml.etree.ElementTree as ET

import numpy as np
import openmc
import h5py
from netCDF4 import Dataset

RUN_DIR = Path(__file__).resolve().parents[1] / "run"
SOURCE_STRENGTH = 4.426602e16  # n/s, identical to openmc.i
EV_TO_J = 1.602176634e-19


def names(rows):
    return [row.tobytes().decode().strip("\x00 ") for row in rows]


def cardinal_values(ds, side, mesh, field):
    """Return values in OpenMC's x-fastest order after checking every bin."""
    block_names = names(ds.variables["eb_names"][:])
    eb = block_names.index(f"{side}_channel") + 1
    conn = np.asarray(ds.variables[f"connect{eb}"][:], dtype=int) - 1
    xyz = np.column_stack([ds.variables[f"coord{a}"][:] for a in "xyz"]) * 100
    vertices = xyz[conn]
    dim = np.asarray(mesh.dimension)
    lo = np.asarray(mesh.lower_left)
    step = (np.asarray(mesh.upper_right) - lo) / dim
    centers = vertices.mean(axis=1)
    ijk = np.rint((centers - lo) / step - 0.5).astype(int)
    if conn.shape != (int(np.prod(dim)), 8):
        raise ValueError(f"{side}: expected exactly {np.prod(dim)} HEX8 elements")
    if np.any(ijk < 0) or np.any(ijk >= dim):
        raise ValueError(f"{side}: elements outside the OpenMC mesh")
    expected_lo = lo + ijk * step
    # Require all eight corners, not merely an overlapping centroid/bounding box.
    offsets = (vertices - expected_lo[:, None, :]) / step
    corners = np.rint(offsets).astype(int)
    if not np.allclose(offsets, corners, atol=1e-8, rtol=0):
        raise ValueError(f"{side}: element edges do not match OpenMC bins")
    if np.any(corners < 0) or np.any(corners > 1):
        raise ValueError(f"{side}: incorrect element extent")
    corner_ids = corners @ np.array([1, 2, 4])
    if not np.all(np.sort(corner_ids, axis=1) == np.arange(8)):
        raise ValueError(f"{side}: elements must have eight distinct voxel corners")
    flat = np.ravel_multi_index(ijk.T, tuple(dim), order="F")
    if len(np.unique(flat)) != int(np.prod(dim)):
        raise ValueError(f"{side}: duplicate or missing mesh bins")
    var = names(ds.variables["name_elem_var"][:]).index(field) + 1
    values = np.ma.asarray(ds.variables[f"vals_elem_var{var}eb{eb}"][-1])
    if np.any(np.ma.getmaskarray(values)) or not np.all(np.isfinite(values)):
        raise ValueError(f"{field}: missing or nonfinite Cardinal values")
    ordered = np.empty(len(flat))
    ordered[flat] = np.asarray(values) / 1e6  # per m3 -> per cm3
    return ordered


def check_inputs(openmc_dir, cardinal_dir):
    """Check that the two sets of exported transport inputs match."""
    driver = (cardinal_dir / "openmc.i").read_text()
    strength = re.search(r"^source_strength\s*=\s*([0-9.eE+-]+)", driver, re.MULTILINE)
    if strength is None or float(strength.group(1)) != SOURCE_STRENGTH:
        raise ValueError("Cardinal source normalization differs from the comparison")
    model = ET.parse(openmc_dir / "model.xml").getroot()
    def signature(element):
        return (element.tag, tuple(sorted(element.attrib.items())),
                (element.text or "").strip(), tuple(signature(child) for child in element))
    for section in ("geometry", "materials", "settings"):
        standalone = model.find(section)
        cardinal = ET.parse(cardinal_dir / f"{section}.xml").getroot()
        if signature(standalone) != signature(cardinal):
            raise ValueError(f"{section}: standalone and Cardinal XML differ; regenerate both")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--structure", choices=("steel", "air"), default="steel")
    args = parser.parse_args()
    suffix = "_air" if args.structure == "air" else ""
    openmc_dir = RUN_DIR / f"openmc{suffix}"
    cardinal_dir = RUN_DIR / f"cardinal{suffix}"
    openmc_sp = openmc_dir / "statepoint.10.h5"
    cardinal_exo = cardinal_dir / "openmc_out.e"
    check_inputs(openmc_dir, cardinal_dir)
    with openmc.StatePoint(openmc_sp) as reference_sp:
        expected_particles = reference_sp.n_particles
        expected_batches = reference_sp.n_batches
        expected_sizes = sorted(reference_sp.get_tally(name=f"{side}_channel_mesh_tally").num_filter_bins
                                for side in ("left", "right"))
        expected_scores = set(reference_sp.get_tally(name="left_channel_mesh_tally").scores)
        if set(reference_sp.get_tally(name="right_channel_mesh_tally").scores) != expected_scores:
            raise ValueError("Standalone channel scores differ")
        heating_scores = expected_scores & {"heating", "heating-local"}
        if len(heating_scores) != 1 or "(n,Xt)" not in expected_scores:
            raise ValueError("Expected one heating score and tritium production")
        heating_score = heating_scores.pop()
    # Cardinal's in-memory adaptive libMesh statepoints do not contain a mesh
    # filename; inspect metadata directly to support the local Python OpenMC build.
    with h5py.File(cardinal_dir / "statepoint.10.h5") as cardinal_sp:
        if (cardinal_sp["run_mode"][()].decode() != "fixed source"
                or cardinal_sp["n_batches"][()] != expected_batches
                or cardinal_sp["n_particles"][()] != expected_particles):
            raise ValueError("Cardinal run settings do not match the standalone run")
        channel_tallies = [t for key, t in cardinal_sp["tallies"].items()
                           if key.startswith("tally ") and "filters" in t]
        if (len(channel_tallies) != 2
                or sorted(t["results"].shape[0] for t in channel_tallies) != expected_sizes
                or any(t["estimator"][()].decode() != "collision" for t in channel_tallies)
                or any(set(t["score_bins"].asstr()[:]) != expected_scores
                       for t in channel_tallies)):
            raise ValueError("Rerun Cardinal: expected two matching collision channel tallies")
    rows = []
    with openmc.StatePoint(openmc_sp) as sp, Dataset(cardinal_exo) as ds:
        if sp.run_mode != "fixed source" or sp.n_batches != expected_batches or sp.n_particles != expected_particles:
            raise ValueError("Standalone run settings do not match openmc.i")
        if float(ds.variables["time_whole"][-1]) != 1.0:
            raise ValueError("Cardinal has not completed its transport step")
        for side in ("left", "right"):
            tally = sp.get_tally(name=f"{side}_channel_mesh_tally")
            if tally.estimator != "collision":
                raise ValueError("Rerun standalone OpenMC with the collision estimator")
            mesh = tally.find_filter(openmc.MeshFilter).mesh
            volume = float(np.prod((np.asarray(mesh.upper_right) - mesh.lower_left) / mesh.dimension))
            indices = np.array(list(np.ndindex(*mesh.dimension)))
            # Explicit x-fastest indexing to match OpenMC MeshFilter bin order.
            indices = indices[np.argsort(np.ravel_multi_index(indices.T, tuple(mesh.dimension), order="F"))]
            for score, field, unit in (("(n,Xt)", f"H3_{side}", "atoms/s/cm3"),
                                       (heating_score, f"heating_{side}", "W/cm3")):
                factor = SOURCE_STRENGTH / volume * (EV_TO_J if score in {"heating", "heating-local"} else 1)
                reference = tally.get_values(scores=[score]).ravel() * factor
                sigma_o = tally.get_values(scores=[score], value="std_dev").ravel() * factor
                actual = cardinal_values(ds, side, mesh, field)
                sigma_c = cardinal_values(ds, side, mesh, field + "_std_dev")
                delta = actual - reference
                denominator = np.maximum(abs(reference), abs(actual))
                relative = np.divide(abs(delta), denominator, out=np.zeros_like(delta), where=denominator > 0)
                integral_o, integral_c = reference.sum() * volume, actual.sum() * volume
                integral_pct = (integral_c / integral_o - 1) * 100 if integral_o else float("nan")
                print(f"{side:5s} {score:13s}: {len(actual)} matching bins; totals {integral_o:.7g} / {integral_c:.7g}; delta {integral_pct:+.3f}%; median bin difference {np.median(relative)*100:.2f}%")
                for ijk, o, c, so, sc, rd in zip(indices, reference, actual, sigma_o, sigma_c, relative):
                    rows.append([side, score, *ijk, unit, o, c, so, sc, rd * 100])
    output = RUN_DIR / f"channel_comparison{suffix}.csv"
    with output.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["channel", "score", "i", "j", "k", "unit", "openmc", "cardinal", "openmc_std_dev", "cardinal_std_dev", "symmetric_difference_percent"])
        writer.writerows(rows)
    print(f"Per-bin values and Monte Carlo uncertainties: {output}")
    print("Matching bins and estimators do not imply identical random histories across OpenMC builds.")


if __name__ == "__main__":
    main()
