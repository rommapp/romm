#!/usr/bin/env bash
# Builds libgme and the RomM shim into a standalone WebAssembly module.
# Built without zlib: the player gunzips VGZ files before handing them over.
# Usage: build.sh <libgme source dir> <output dir>
set -euo pipefail

src_dir="$1"
out_dir="$2"
shim_dir="$(cd "$(dirname "$0")" && pwd)"
build_dir="$(mktemp -d)"

emcmake cmake -S "${src_dir}" -B "${build_dir}" \
	-DCMAKE_BUILD_TYPE=Release \
	-DCMAKE_CXX_FLAGS="-fno-exceptions -fno-rtti" \
	-DGME_BUILD_SHARED=OFF \
	-DGME_BUILD_STATIC=ON \
	-DGME_BUILD_TESTING=OFF \
	-DGME_BUILD_EXAMPLES=OFF \
	-DGME_ZLIB=OFF
cmake --build "${build_dir}" --target gme_static --parallel

mkdir -p "${out_dir}"
# STANDALONE_WASM drops the JS glue: the worklet instantiates the module
# itself, since AudioWorkletGlobalScope has no fetch or DOM.
emcc -O3 -fno-exceptions -fno-rtti \
	-I "${src_dir}" \
	"${shim_dir}/romm_gme.cpp" \
	"${build_dir}/gme/libgme.a" \
	-sSTANDALONE_WASM \
	-sALLOW_MEMORY_GROWTH \
	-sFILESYSTEM=0 \
	-sEXPORTED_FUNCTIONS=_malloc,_free,_romm_gme_open,_romm_gme_start,_gme_track_count,_gme_play,_gme_seek,_gme_tell,_gme_track_ended,_gme_delete \
	--no-entry \
	-o "${out_dir}/gme.wasm"

cp "${src_dir}/license.txt" "${out_dir}/LICENSE.txt"
rm -rf "${build_dir}"
