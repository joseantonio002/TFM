#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

shopt -s nullglob

segmented_files=("${SCRIPT_DIR}"/pipeline_*/*_transcription_merged_segmented.json)
score_plots=("${SCRIPT_DIR}"/pipeline_*/*_transcription_merged_scores.png)

deleted_count=0

for file_path in "${segmented_files[@]}"; do
  rm -f "${file_path}"
  deleted_count=$((deleted_count + 1))
  printf 'Deleted: %s\n' "${file_path}"
done

for file_path in "${score_plots[@]}"; do
  rm -f "${file_path}"
  deleted_count=$((deleted_count + 1))
  printf 'Deleted: %s\n' "${file_path}"
done

printf 'Done. Deleted %d files.\n' "${deleted_count}"
