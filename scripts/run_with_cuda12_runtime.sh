#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "usage: $0 PYTHON_EXECUTABLE SCRIPT [ARGS...]" >&2
  exit 2
fi

python_executable="$1"
shift
site_packages="$("$python_executable" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
nvidia_lib="$site_packages/nvidia"
cuda12_libs=(
  "$nvidia_lib/cublas/lib"
  "$nvidia_lib/cuda_runtime/lib"
  "$nvidia_lib/cuda_nvrtc/lib"
  "$nvidia_lib/cufft/lib"
  "$nvidia_lib/nvjitlink/lib"
)
for lib_dir in "${cuda12_libs[@]}"; do
  if [ ! -d "$lib_dir" ]; then
    echo "Missing CUDA 12 runtime library directory: $lib_dir" >&2
    echo "Install requirements-gipformer.txt in $python_executable first." >&2
    exit 1
  fi
done
export LD_LIBRARY_PATH="$(IFS=:; echo "${cuda12_libs[*]}")${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$python_executable" "$@"
