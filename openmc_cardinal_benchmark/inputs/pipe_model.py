"""Build the two-channel OpenMC benchmark and export its transport inputs."""

import argparse
import os
from pathlib import Path

import numpy as np
import openmc

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--structure", choices=("steel", "air"), default="steel",
    help="Material filling the pipe region around the coolant channels",
)
args = parser.parse_args()

run_name = "openmc_air" if args.structure == "air" else "openmc"
RUN_DIR = Path(__file__).resolve().parents[1] / "run" / run_name

######## Material compositions ########
# Material compositions copied from src/paratan/materials/material.py

# Air openmc material
air = openmc.Material(name="air")
air.set_density("g/cm3", 0.001205)
air.add_nuclide("C12", 1.48583129e-04)
air.add_nuclide("C13", 1.60703476e-06)
air.add_nuclide("N14", 7.81575372e-01)
air.add_nuclide("N15", 2.85532775e-03)
air.add_nuclide("O16", 2.10235865e-01)
air.add_nuclide("O17", 8.00842335e-05)
air.add_nuclide("O18", 4.32033365e-04)
air.add_nuclide("Ar36", 1.55828794e-05)
air.add_nuclide("Ar38", 2.93813883e-06)
air.add_nuclide("Ar40", 4.65260590e-03)

# RAFM Steel openmc material (Eurofer97)
rafm_steel = openmc.Material(name="Eurofer97")
rafm_steel.set_density("g/cm3", 7.75)
rafm_steel.add_nuclide("C12", 1.1545e-03, "wo")
rafm_steel.add_nuclide("C13", 1.3531e-05, "wo")
rafm_steel.add_nuclide("V50", 4.9454e-06, "wo")
rafm_steel.add_nuclide("V51", 2.0126e-03, "wo")
rafm_steel.add_nuclide("Cr52", 7.9100e-02, "wo")
rafm_steel.add_nuclide("Cr53", 9.1420e-03, "wo")
rafm_steel.add_nuclide("Cr54", 2.3186e-03, "wo")
rafm_steel.add_nuclide("Fe56", 8.6988e-01, "wo")
rafm_steel.add_nuclide("Fe57", 2.0449e-02, "wo")
rafm_steel.add_nuclide("Fe58", 2.7690e-03, "wo")
rafm_steel.add_nuclide("Ta180", 1.7755e-07, "wo")
rafm_steel.add_nuclide("Ta181", 1.4864e-03, "wo")
rafm_steel.add_nuclide("W182", 3.0634e-03, "wo")
rafm_steel.add_nuclide("W183", 1.6634e-03, "wo")
rafm_steel.add_nuclide("W184", 3.5810e-03, "wo")
rafm_steel.add_nuclide("W186", 3.3589e-03, "wo")

# PbLi openmc material (lead-lithium eutectic; set at% Li-6 enrichment)
enrichment_li6 = 0.075 
LiPb_density = 9965  # kg/m3
pb_at_percent = 84.3

pbli = openmc.Material(name="lead_83_lithium_17")
pbli.set_density("kg/m3", LiPb_density)
pbli.add_element(
    "Li",
    100 - pb_at_percent,
    percent_type="ao",
    enrichment=enrichment_li6 * 100,
    enrichment_target="Li6",
    enrichment_type="ao",
)
pbli.add_element("Pb", pb_at_percent)

structure_material = air if args.structure == "air" else rafm_steel
materials = openmc.Materials([air, rafm_steel, pbli])
if structure_material is air:
    materials.remove(rafm_steel)

####### Geometry ########

# Root universe — add Cells / nested Universes here, then assign to Geometry.
universe = openmc.Universe()

# Room region and cell
room_surface = openmc.model.RectangularParallelepiped(
    xmin = -5,
    xmax = 40,
    ymin = -5,
    ymax = 60,
    zmin = -5,
    zmax = 30,
)
room_surface.boundary_type = "vacuum"
room_region = -room_surface

# Pipe region
pipe_surface = openmc.model.RectangularParallelepiped(
    xmin=0,
    xmax=28,
    ymin=0,
    ymax=50,
    zmin=0,
    zmax=20,
)
pipe_structure_region = -pipe_surface

# Left and right PbLi channels
left_channel_surface = openmc.model.RectangularParallelepiped(
    xmin=4,
    xmax=14,
    ymin=0,
    ymax=50,
    zmin=4,
    zmax=16,
)
right_channel_surface = openmc.model.RectangularParallelepiped(
    xmin=18,
    xmax=26,
    ymin=0,
    ymax=50,
    zmin=4,
    zmax=16,
)
left_channel_region = -left_channel_surface
right_channel_region = -right_channel_surface

# Nested CSG: room ⊃ pipe ⊃ channels (assign final regions to cells)
pipe_structure_region &= ~left_channel_region
pipe_structure_region &= ~right_channel_region
room_region &= ~pipe_structure_region
room_region &= ~left_channel_region
room_region &= ~right_channel_region

room_cell = openmc.Cell(name="room", region=room_region, fill=air)
pipe_structure_cell = openmc.Cell(
    name="pipe_structure", region=pipe_structure_region, fill=structure_material
)
left_channel_cell = openmc.Cell(
    name="left_channel", region=left_channel_region, fill=pbli
)
right_channel_cell = openmc.Cell(
    name="right_channel", region=right_channel_region, fill=pbli
)
universe.add_cells(
    [room_cell, pipe_structure_cell, left_channel_cell, right_channel_cell]
)

geometry = openmc.Geometry(universe)

####### Shared channel meshes: tally bins and weight-window bins ########

left_bb = left_channel_cell.bounding_box
right_bb = right_channel_cell.bounding_box

# Match the independent channel grids in cardinal/mesh.i.
left_channel_mesh = openmc.RegularMesh()
left_channel_mesh.dimension = [5, 25, 6]
left_channel_mesh.lower_left = left_bb.lower_left
left_channel_mesh.upper_right = left_bb.upper_right

right_channel_mesh = openmc.RegularMesh()
right_channel_mesh.dimension = [4, 25, 6]
right_channel_mesh.lower_left = right_bb.lower_left
right_channel_mesh.upper_right = right_bb.upper_right

####### Create settings ########

source = openmc.IndependentSource(
    space=openmc.stats.Box([29.0, 0.0, 0.0], [31.0, 50.0, 20.0]),
    angle=openmc.stats.Monodirectional([-1.0, 0.0, 0.0]),
    energy=openmc.stats.Discrete([14.1e6], [1.0]),
    particle="neutron",
)

settings = openmc.Settings()
settings.source = source
settings.run_mode = "fixed source"
settings.batches = 10
settings.particles = 800000
settings.seed = 1
settings.temperature["default"] = 600.0
settings.temperature["method"] = "interpolation"
settings.temperature["range"] = (294.0, 3000.0)

####### Fixed channel weight windows ########
WW_LOWER_WEIGHT = 0.125
WW_UPPER_WEIGHT = 0.5
WW_SURVIVAL_RATIO = 2.0
WW_MAX_LOWER_BOUND_RATIO = 100.0
WW_MAX_SPLIT = 10

settings.weight_windows = [
    openmc.WeightWindows(
        mesh=mesh,
        lower_ww_bounds=np.full((*mesh.dimension, 1), WW_LOWER_WEIGHT),
        upper_ww_bounds=np.full((*mesh.dimension, 1), WW_UPPER_WEIGHT),
        energy_bounds=[0.0, 20.0e6],
        particle_type="neutron",
        survival_ratio=WW_SURVIVAL_RATIO,
        max_lower_bound_ratio=WW_MAX_LOWER_BOUND_RATIO,
        max_split=WW_MAX_SPLIT,
    )
    for mesh in (left_channel_mesh, right_channel_mesh)
]
settings.weight_windows_on = True
settings.weight_window_checkpoints = {"collision": True, "surface": True}

####### Export XMLs for Cardinal ########

RUN_DIR.mkdir(parents=True, exist_ok=True)
materials.export_to_xml(path=RUN_DIR / "materials.xml")
geometry.export_to_xml(path=RUN_DIR / "geometry.xml")
settings.export_to_xml(path=RUN_DIR / "settings.xml")
print(f"Exported OpenMC XMLs to {RUN_DIR}")

# Cardinal only needs the XMLs above. Set RUN_OPENMC=1 to also plot/run standalone OpenMC.
if os.environ.get("RUN_OPENMC", "0") != "1":
    raise SystemExit(0)

####### Plot geometry (optional) ########

if os.environ.get("PLOT_GEOM", "0") == "1":
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    origin = (17.5, 27.5, 12.5)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    plot_kwargs = dict(origin=origin, pixels=(600, 480), color_by="material")
    geometry.root_universe.plot(basis="xz", width=(50, 40), axes=axes[0], **plot_kwargs)
    axes[0].set_title("xz")
    geometry.root_universe.plot(basis="xy", width=(50, 70), axes=axes[1], **plot_kwargs)
    axes[1].set_title("xy")
    fig.tight_layout()
    fig.savefig(RUN_DIR / "pipe_model_geometry.png", bbox_inches="tight")
    plt.close(fig)

####### Create tallies ########

tallies = openmc.Tallies()

left_channel_mesh_tally = openmc.Tally(name="left_channel_mesh_tally")
left_channel_mesh_tally.filters = [openmc.MeshFilter(left_channel_mesh)]
left_channel_mesh_tally.estimator = "collision"
left_channel_mesh_tally.scores = ["(n,Xt)", "heating"]

right_channel_mesh_tally = openmc.Tally(name="right_channel_mesh_tally")
right_channel_mesh_tally.filters = [openmc.MeshFilter(right_channel_mesh)]
right_channel_mesh_tally.estimator = "collision"
right_channel_mesh_tally.scores = ["(n,Xt)", "heating"]

tallies.extend([left_channel_mesh_tally, right_channel_mesh_tally])

####### Run ########

model = openmc.Model(
    geometry=geometry,
    materials=materials,
    settings=settings,
    tallies=tallies,
)
sp_path = model.run(
    cwd=RUN_DIR,
    openmc_exec=os.environ.get("OPENMC_EXEC", "openmc"),
)
print(f"Finished. Statepoint: {sp_path}")
