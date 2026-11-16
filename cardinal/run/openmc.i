# OpenMC-only Cardinal driver for the pipe model (no THM / solid conduction).
# Coolant-channel tallies are defined HERE (not in OpenMC tallies.xml).
# Geometry/materials/settings come from ../openmc_model/pipe_model_no_tallies.py
# NWL = 1 MW/m2 over 50 cm x 20 cm at 14.1 MeV -> source_strength below.

source_strength = 4.426602e16  # n/s

[Mesh]
  allow_renumbering = false
  [file]
    type = FileMeshGenerator
    file = meshes/tally_domain_in.e
  []
[]

[ICs]
  [temp]
    type = ConstantIC
    variable = temp
    value = 600.0
  []
[]

[AuxVariables]
  [cell_temperature]
    family = MONOMIAL
    order = CONSTANT
  []
[]

[AuxKernels]
  [cell_temperature]
    type = CellTemperatureAux
    variable = cell_temperature
  []
[]

[Problem]
  type = OpenMCCellAverageProblem
  verbose = true
  scaling = 100.0

  source_strength = ${source_strength}

  cell_level = 0
  # Fine tritium blocks are scoring-only; feedback uses each physical volume once.
  temperature_blocks = 'pipe_structure left_channel right_channel'

  particles = 755000
  batches = 10

  # Separate block-restricted meshes: no tally spans overlapping coolant blocks.
  [Tallies]
    [heating_left]
      type = MeshTally
      block = left_channel
      score = heating
      name = heating_left
      estimator = collision
      check_tally_sum = false
      output = unrelaxed_tally_std_dev
    []
    [heating_right]
      type = MeshTally
      block = right_channel
      score = heating
      name = heating_right
      estimator = collision
      check_tally_sum = false
      output = unrelaxed_tally_std_dev
    []
    [tritium_left]
      type = MeshTally
      block = left_tritium
      score = H3_production
      name = H3_left
      estimator = collision
      check_tally_sum = false
      output = unrelaxed_tally_std_dev
    []
    [tritium_right]
      type = MeshTally
      block = right_tritium
      score = H3_production
      name = H3_right
      estimator = collision
      check_tally_sum = false
      output = unrelaxed_tally_std_dev
    []
    [heating_structure]
      type = MeshTally
      block = pipe_structure
      score = heating
      name = heating_structure
      estimator = collision
      check_tally_sum = false
      output = unrelaxed_tally_std_dev
    []
  []
[]

[Postprocessors]
  [heating_left]
    type = ElementIntegralVariablePostprocessor
    variable = heating_left
    block = left_channel
  []
  [heating_right]
    type = ElementIntegralVariablePostprocessor
    variable = heating_right
    block = right_channel
  []
  [heating_structure]
    type = ElementIntegralVariablePostprocessor
    variable = heating_structure
    block = pipe_structure
  []
  [tritium_left]
    type = ElementIntegralVariablePostprocessor
    variable = H3_left
    block = left_tritium
  []
  [tritium_right]
    type = ElementIntegralVariablePostprocessor
    variable = H3_right
    block = right_tritium
  []

[]

[Executioner]
  type = Transient
  num_steps = 1
[]

[Outputs]
  exodus = true
  csv = true
[]
