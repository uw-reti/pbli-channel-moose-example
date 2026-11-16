# RAFM structure + coolant meshes (meters). Generate: generate_geometry_mesh.py
# Products in cardinal/:
#   tally_domain_in.e      — structure + coarse + fine coolant (openmc.i)
#   pipe_structure_mesh.e  — structure + coarse coolant only (--mesh-only)
# Coarse/fine coolant blocks overlap; restrict every tally by block.
# Coolant and structure do not share interface nodes.

[Mesh]
  allow_renumbering = false

  # Full outer pipe box (1 cm x 2 cm x 1 cm structure cells).
  [pipe]
    type = GeneratedMeshGenerator
    dim = 3
    xmin = 0.0
    xmax = 0.28
    ymin = 0.0
    ymax = 0.50
    zmin = 0.0
    zmax = 0.20
    nx = 28
    ny = 25
    nz = 20
    subdomain_ids = 2
  []

  # Tag left-channel cells in the pipe mesh.
  [left_channel]
    type = SubdomainBoundingBoxGenerator
    input = pipe
    block_id = 3
    bottom_left = '0.04 0.0 0.04'
    top_right = '0.14 0.50 0.16'
  []

  # Tag right-channel cells (input is the mesh after left tagging).
  [right_channel]
    type = SubdomainBoundingBoxGenerator
    input = left_channel
    block_id = 4
    bottom_left = '0.18 0.0 0.04'
    top_right = '0.26 0.50 0.16'
  []

  # Delete tagged channel cells so structure has voids for coolant meshes.
  [structure]
    type = BlockDeletionGenerator
    input = right_channel
    block = '3 4'
  []

  # Coarse left channel for heating (1 x 25 x 1).
  [left_coarse]
    type = GeneratedMeshGenerator
    dim = 3
    xmin = 0.04
    xmax = 0.14
    ymin = 0.0
    ymax = 0.50
    zmin = 0.04
    zmax = 0.16
    nx = 1
    ny = 25
    nz = 1
    subdomain_ids = 3
  []

  # Coarse right channel for heating (1 x 25 x 1).
  [right_coarse]
    type = GeneratedMeshGenerator
    dim = 3
    xmin = 0.18
    xmax = 0.26
    ymin = 0.0
    ymax = 0.50
    zmin = 0.04
    zmax = 0.16
    nx = 1
    ny = 25
    nz = 1
    subdomain_ids = 4
  []

  # Fine left channel for tritium (5 x 25 x 6).
  [left_fine]
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
    subdomain_ids = 5
  []

  # Fine right channel for tritium (4 x 25 x 6).
  [right_fine]
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
    subdomain_ids = 6
  []

  # Join structure + coarse + fine (still numeric block IDs).
  [assemble]
    type = MeshCollectionGenerator
    inputs = 'structure left_coarse right_coarse left_fine right_fine'
  []

  # Name blocks for openmc.i and write tally_domain_in.e.
  # Coarse → left_channel/right_channel; fine → left_tritium/right_tritium.
  [tally_domain]
    type = RenameBlockGenerator
    input = assemble
    old_block = '2 3 4 5 6'
    new_block = 'pipe_structure left_channel right_channel left_tritium right_tritium'
    output = true
  []

  # Drop fine coolant from the final mesh; names on the rest are kept.
  [heating_domain]
    type = BlockDeletionGenerator
    input = tally_domain
    block = 'left_tritium right_tritium'
  []
[]
