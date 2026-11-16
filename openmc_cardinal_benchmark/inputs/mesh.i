# Two independent coolant-channel grids, matching pipe_model.py tally meshes.
# Coordinates are meters; OpenMC uses cm (openmc.i: scaling = 100).

[Mesh]
  allow_renumbering = false

  [left_channel]
    type = GeneratedMeshGenerator
    dim = 3
    xmin = 0.04
    xmax = 0.14
    ymin = 0.0
    ymax = 0.50
    zmin = 0.04
    zmax = 0.16
    nx = 5
    ny = 25
    nz = 6
    subdomain_ids = 3
  []

  [right_channel]
    type = GeneratedMeshGenerator
    dim = 3
    xmin = 0.18
    xmax = 0.26
    ymin = 0.0
    ymax = 0.50
    zmin = 0.04
    zmax = 0.16
    nx = 4
    ny = 25
    nz = 6
    subdomain_ids = 4
  []

  [channels]
    type = MeshCollectionGenerator
    inputs = 'left_channel right_channel'
  []

  [rename]
    type = RenameBlockGenerator
    input = channels
    old_block = '3 4'
    new_block = 'left_channel right_channel'
  []
[]

[Outputs]
  [exo]
    type = Exodus
    file_base = pipe_mesh
  []
[]
