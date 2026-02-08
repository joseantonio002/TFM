#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WHISPER_CLI="${PROJECT_ROOT}/whisper.cpp/build/bin/whisper-cli"
MODEL_PATH="${PROJECT_ROOT}/whisper.cpp/models/ggml-base.bin"

if command -v nproc >/dev/null 2>&1; then
  PARALLEL="$(nproc)"
elif command -v getconf >/dev/null 2>&1; then
  PARALLEL="$(getconf _NPROCESSORS_ONLN 2>/dev/null || true)"
fi

PARALLEL="${PARALLEL:-4}"

log() {
  printf '[INFO] %s\n' "$*"
}

process_directory() {
  local dir="$1"
  local dir_abs
  local dir_name
  local joined_wav
  local out_base
  local out_txt
  local list_file=""
  local -a mka_files=()

  cleanup() {
    if [[ -n "${list_file}" && -f "${list_file}" ]]; then
      rm -f "${list_file}"
    fi
  }

  trap cleanup RETURN

  if [[ "${dir}" == *"__pycache__"* ]]; then
    log "Skipping '${dir}' (contains __pycache__)."
    return 0
  fi

  if [[ ! -d "${dir}" || -L "${dir}" ]]; then
    log "Skipping '${dir}' (not a real directory)."
    return 0
  fi

  dir_abs="$(cd "${dir}" && pwd)"
  dir_name="$(basename "${dir}")"
  joined_wav="${dir_abs}/joined.wav"
  out_base="${dir_name}_out"
  out_txt="${dir_abs}/${out_base}.txt"

  while IFS= read -r -d '' file; do
    mka_files+=("${file}")
  done < <(find "${dir_abs}" -maxdepth 1 -type f -name '*.mka' -print0 | sort -z -V)

  if (( ${#mka_files[@]} == 0 )); then
    log "No .mka files in '${dir_name}', skipping."
    return 0
  fi

  list_file="$(mktemp "${dir_abs}/.ffmpeg_concat.XXXXXX.txt")"

  for file in "${mka_files[@]}"; do
    local escaped
    escaped="${file//\'/\'\\\'\'}"
    printf "file '%s'\n" "${escaped}" >> "${list_file}"
  done

  if [[ -f "${joined_wav}" ]]; then
    log "Overwriting existing '${joined_wav}'."
  fi

  local join_start_ns
  local join_end_ns
  local join_elapsed_ms
  join_start_ns="$(date +%s%N)"

  ffmpeg -hide_banner -loglevel error -y \
    -f concat -safe 0 -i "${list_file}" \
    -ar 16000 -ac 1 -c:a pcm_s16le \
    "${joined_wav}"

  join_end_ns="$(date +%s%N)"
  join_elapsed_ms=$(( (join_end_ns - join_start_ns) / 1000000 ))
  log "Join/conversion for '${dir_name}' took ${join_elapsed_ms} ms."

  if [[ -f "${out_txt}" ]]; then
    log "Overwriting existing '${out_txt}'."
  fi

  local transcript_start_ns
  local transcript_end_ns
  local transcript_elapsed_ms
  transcript_start_ns="$(date +%s%N)"

  "${WHISPER_CLI}" \
    -m "${MODEL_PATH}" \
    -l es -otxt \
    -of "${dir_abs}/${out_base}" \
    --no-prints \
    -f "${joined_wav}"

  transcript_end_ns="$(date +%s%N)"
  transcript_elapsed_ms=$(( (transcript_end_ns - transcript_start_ns) / 1000000 ))
  log "Transcript for '${dir_name}' took ${transcript_elapsed_ms} ms."

  if [[ -f "${out_txt}" ]]; then
    log "Completed '${dir_name}'."
  else
    log "Completed '${dir_name}', but transcript not found at '${out_txt}'."
  fi
}

if [[ ! -x "${WHISPER_CLI}" ]]; then
  printf '[ERROR] whisper-cli not found or not executable: %s\n' "${WHISPER_CLI}" >&2
  exit 1
fi

if [[ ! -f "${MODEL_PATH}" ]]; then
  printf '[ERROR] Model file not found: %s\n' "${MODEL_PATH}" >&2
  exit 1
fi

export WHISPER_CLI MODEL_PATH
export -f log
export -f process_directory

find . -mindepth 1 -maxdepth 1 -type d ! -name '__pycache__' -print0 \
  | xargs -0 -I {} -P "${PARALLEL}" bash -c 'process_directory "$1"' _ "{}"
