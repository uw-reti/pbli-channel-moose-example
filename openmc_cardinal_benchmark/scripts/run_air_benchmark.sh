#!/usr/bin/env bash
# Run the air-filled benchmark and write air-specific comparison products.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
cardinal_exec="${CARDINAL_EXEC:-cardinal-opt}"
cardinal_exec="$(command -v "$cardinal_exec")"
cardinal_exec="$(realpath "$cardinal_exec")"

RUN_OPENMC=1 python inputs/pipe_model.py --structure air

mkdir -p run/cardinal_air
cp inputs/mesh.i inputs/openmc.i run/cardinal_air/
cp run/openmc_air/{geometry,materials,settings}.xml run/cardinal_air/

(
  cd run/cardinal_air
  "$cardinal_exec" -i mesh.i --mesh-only pipe_mesh.e
  "$cardinal_exec" -i openmc.i --n-threads="${CARDINAL_THREADS:-1}"
)

python scripts/compare_channels.py --structure air
python scripts/plot_channel_differences.py --structure air
