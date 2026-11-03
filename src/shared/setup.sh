# Shared setup for the phase scripts at the repo root (01_collect_data.sh ... 04_build_map.sh).
# Sourced, not run: moves to the repo root, makes the local virtual environment in .venv/
# (installs nothing globally) and gives the scripts three helpers.
#   require_inputs <script that makes them> <file or folder>...   stop if an input is missing
#   require_tippecanoe                                             stop if tippecanoe is missing
#   run_python <script> [args]                                     run a pipeline script in .venv
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."

PYTHON="${PYTHON:-python3.12}"
if [ -z "${PH_LOTTERY_ENV_READY:-}" ]; then  # once per run, even when run_all.sh calls every phase
  if [ ! -x .venv/bin/python ]; then
    "$PYTHON" -m venv .venv
    .venv/bin/pip install --quiet --upgrade pip
  fi
  .venv/bin/pip install --quiet -r requirements.txt
  export PH_LOTTERY_ENV_READY=1
fi

require_inputs() {
  local maker="$1"; shift
  local missing=()
  for path in "$@"; do
    [ -e "$path" ] || missing+=("$path")
  done
  if [ "${#missing[@]}" -gt 0 ]; then
    echo "missing input: ${missing[*]}" >&2
    echo "run $maker first" >&2
    exit 1
  fi
}

require_tippecanoe() {
  if ! command -v tippecanoe >/dev/null; then
    echo "tippecanoe is needed for the web map: brew install tippecanoe" >&2
    echo "(or build it from https://github.com/felt/tippecanoe)" >&2
    exit 1
  fi
}

run_python() {
  echo "== $1"
  .venv/bin/python "$@"
}
