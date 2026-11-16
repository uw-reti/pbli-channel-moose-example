"""Build pipe OpenMC model for Cardinal: materials / geometry / settings only.

No OpenMC tallies — channel heating and tritium are defined in cardinal/openmc.i.
Exports XML into cardinal/run/.

  conda activate paratan
  python pipe_model_no_tallies.py
"""

from pathlib import Path

import openmc

CARDINAL_DIR = Path(__file__).resolve().parents[1] / "run"
CARDINAL_DIR.mkdir(parents=True, exist_ok=True)

######## Materials ########

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

materials = openmc.Materials([air, rafm_steel, pbli])

######## Geometry ########

universe = openmc.Universe()

room_surface = openmc.model.RectangularParallelepiped(
    xmin=-5, xmax=40, ymin=-5, ymax=60, zmin=-5, zmax=30
)
room_surface.boundary_type = "vacuum"
room_region = -room_surface

pipe_surface = openmc.model.RectangularParallelepiped(
    xmin=0, xmax=28, ymin=0, ymax=50, zmin=0, zmax=20
)
pipe_structure_region = -pipe_surface

left_channel_surface = openmc.model.RectangularParallelepiped(
    xmin=4, xmax=14, ymin=0, ymax=50, zmin=4, zmax=16
)
right_channel_surface = openmc.model.RectangularParallelepiped(
    xmin=18, xmax=26, ymin=0, ymax=50, zmin=4, zmax=16
)
left_channel_region = -left_channel_surface
right_channel_region = -right_channel_surface

pipe_structure_region &= ~left_channel_region
pipe_structure_region &= ~right_channel_region
room_region &= ~pipe_structure_region
room_region &= ~left_channel_region
room_region &= ~right_channel_region

room_cell = openmc.Cell(name="room", region=room_region, fill=air)
pipe_structure_cell = openmc.Cell(
    name="pipe_structure", region=pipe_structure_region, fill=rafm_steel
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

######## Settings (no tallies) ########

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
settings.particles = 250000
settings.seed = 1
settings.temperature["default"] = 600.0
settings.temperature["method"] = "interpolation"
settings.temperature["range"] = (294.0, 3000.0)

######## Export for Cardinal ########

materials.export_to_xml(path=CARDINAL_DIR / "materials.xml")
geometry.export_to_xml(path=CARDINAL_DIR / "geometry.xml")
settings.export_to_xml(path=CARDINAL_DIR / "settings.xml")
print(f"Exported XMLs (no tallies) -> {CARDINAL_DIR}")
print("Channel tallies live in cardinal/run/openmc.i")
