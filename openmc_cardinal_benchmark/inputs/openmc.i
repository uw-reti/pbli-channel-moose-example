# Cardinal fixed-source driver for the OpenMC channel benchmark.
# Coolant-channel MeshTallies only. Source strength = 1 MW/m2 over 50 cm x 20 cm.

source_strength = 4.426602e16  # n/s

[Mesh]
  allow_renumbering = false
  [file]
    type = FileMeshGenerator
    file = pipe_mesh.e
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
  temperature_blocks = 'left_channel right_channel'

  particles = 800000
  batches = 10

  [Tallies]
    [left]
      type = MeshTally
      block = left_channel
      score = 'heating H3_production'
      name = 'heating_left H3_left'
      estimator = collision
      check_tally_sum = false
      output = unrelaxed_tally_std_dev
    []
    [right]
      type = MeshTally
      block = right_channel
      score = 'heating H3_production'
      name = 'heating_right H3_right'
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
  [tritium_left]
    type = ElementIntegralVariablePostprocessor
    variable = H3_left
    block = left_channel
  []
  [tritium_right]
    type = ElementIntegralVariablePostprocessor
    variable = H3_right
    block = right_channel
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
