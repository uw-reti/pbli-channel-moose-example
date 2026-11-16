"""Geometry data for the two-channel pipe example, independent of solver inputs."""

import json
from dataclasses import dataclass, field, fields
from math import isfinite
from pathlib import Path

# Define a 3D point as a tuple of three floats
Point3D = tuple[float, float, float]


# Define a box from a pair of points (lower and upper)
@dataclass(frozen=True)
class Box:
    """Axis-aligned bounds in (x, y, z) order, in centimeters."""

    lower: Point3D
    upper: Point3D

    def __post_init__(self):
        if len(self.lower) != 3 or len(self.upper) != 3:
            raise ValueError("Box bounds must each have three coordinates")
        if any(not (isfinite(lo) and isfinite(hi) and lo < hi)
               for lo, hi in zip(self.lower, self.upper)):
            raise ValueError("Box bounds must be finite and upper must exceed lower")

    @property
    def dimensions(self) -> Point3D:
        return tuple(hi - lo for lo, hi in zip(self.lower, self.upper))

    @property
    def center(self) -> Point3D:
        return tuple((lo + hi) / 2 for lo, hi in zip(self.lower, self.upper))


@dataclass
class ModelGeometryObject:
    """Pipe dimensions and materials for the two-channel layout.

    If geometry_file is supplied, its keys override the corresponding
    constructor values. Geometry dimensions are in centimeters.
    """

    structure_material: object = "RAFM steel"
    coolant_material: object = "PbLi"

    # Coolant dimensions in cm. Both channels share a length and height.
    left_channel_width: float = 10
    right_channel_width: float = 8
    channel_flow_length: float = 50
    channel_height: float = 12

    # Steel thicknesses in cm, including the divider between channels.
    left_wall_thickness: float = 4
    right_wall_thickness: float = 2
    bottom_wall_thickness: float = 4
    top_wall_thickness: float = 4
    divider_thickness: float = 4

    geometry_file: str | Path | None = field(default=None, kw_only=True, repr=False)

    pipe: Box = field(init=False)
    left_channel: Box = field(init=False)
    right_channel: Box = field(init=False)

    def __post_init__(self):
        if self.geometry_file is not None:
            self._load_geometry_file(Path(self.geometry_file))

        # Across x: outer wall, left channel, divider, right channel, outer wall.
        pipe_width = (
            self.left_wall_thickness
            + self.left_channel_width
            + self.divider_thickness
            + self.right_channel_width
            + self.right_wall_thickness
        )
        # Across z: bottom wall, coolant, and top wall.
        pipe_height = (
            self.bottom_wall_thickness + self.channel_height + self.top_wall_thickness
        )
        # The channels run the full pipe length along y.
        self.pipe = Box((0, 0, 0), (pipe_width, self.channel_flow_length, pipe_height))

        # Both channels run along y and sit on the bottom steel wall.
        bottom_z = self.bottom_wall_thickness
        top_z = bottom_z + self.channel_height

        # The left wall sets the first channel's x position.
        left_x = self.left_wall_thickness
        left_end_x = left_x + self.left_channel_width
        self.left_channel = Box(
            (left_x, 0, bottom_z),
            (left_end_x, self.channel_flow_length, top_z),
        )

        # The right channel starts after the divider.
        right_x = left_end_x + self.divider_thickness
        self.right_channel = Box(
            (right_x, 0, bottom_z),
            (right_x + self.right_channel_width, self.channel_flow_length, top_z),
        )

    def _load_geometry_file(self, path: Path):
        with path.open(encoding="utf-8") as file:
            config = json.load(file)
        if not isinstance(config, dict):
            raise ValueError(f"{path}: expected a JSON object")

        # The ASCII diagram documents the layout and is not a geometry input.
        config.pop("_diagram", None)

        # Accept input fields only. The pipe and channel boxes are derived.
        allowed = {item.name for item in fields(self) if item.init} - {"geometry_file"}
        unknown = config.keys() - allowed
        if unknown:
            raise ValueError(f"{path}: unknown geometry fields: {', '.join(sorted(unknown))}")

        for name, value in config.items():
            if name in {"structure_material", "coolant_material"}:
                if not isinstance(value, str):
                    raise ValueError(f"{path}: {name} must be a material name")
            elif type(value) not in (int, float) or not isfinite(value) or value <= 0:
                raise ValueError(f"{path}: {name} must be a positive finite number in cm")
            setattr(self, name, value)
