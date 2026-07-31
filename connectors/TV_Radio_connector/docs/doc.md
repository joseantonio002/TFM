# Dev TV/Radio Connector Audio Flow

This document explains how the dev connector audio extraction, streaming transcription, and transcription merge code works after the latest changes. It is intended as a code guide, not as a usage guide.

The relevant files are:

- `extract_audio.py`: records stream audio and writes segmented WAV files.
- `main.py`: orchestrates extraction, concurrent transcription workers, merging, and embeddings.
- `transcript_segments_cpp.py`: transcribes segment WAV files as they become available.
- `merge_transcriptions.py`: first joins per-segment transcriptions into one source transcription, then runs the existing clean/merge logic.

## Extraction

`extract_audio.py` accepts only two inputs from code or CLI:

- `input_urls`: the stream URLs to record.
- `total_duration`: the total recording duration.

Segment duration is not provided by the caller anymore. It is calculated internally by `compute_segment_time_seconds(total_duration_seconds)`:

- If total duration is 30 minutes or less, there is one segment with the full duration.
- If total duration is between 30 minutes and 1 hour, the recording is split into two near-equal segments.
- If total duration is longer than 1 hour, the segment time is 30 minutes.

The important change is in `build_segment_cut_times(total_duration_seconds, segment_time_seconds)`. Instead of asking ffmpeg to split every `segment_time_seconds` until the end, the code builds explicit split points and intentionally does not create a split for the leftover tail.

For example, with a total duration of 2 hours and 20 minutes and a segment time of 30 minutes:

- Total duration: `8400` seconds.
- Segment time: `1800` seconds.
- Cut points: `1800,3600,5400`.
- ffmpeg output durations: `30m, 30m, 30m, 50m`.

This works because ffmpeg receives `-segment_times` with explicit timestamps. Every listed timestamp starts a new segment. Since there is no cut at `7200`, the last segment includes the normal 30-minute segment plus the 20-minute leftover.

If total duration divides exactly by segment time, the cut list still creates normal fixed-size segments. For 2 hours with 30-minute segments:

- Total duration: `7200` seconds.
- Cut points: `1800,3600,5400`.
- ffmpeg output durations: `30m, 30m, 30m, 30m`.

If total duration is shorter than the computed segment time, there are no explicit cut points and ffmpeg produces one segment.

The ffmpeg command now writes only segment files:

```text
<source_id>_out_00000.wav
<source_id>_out_00001.wav
<source_id>_out_00002.wav
...
```

It no longer writes a full `*_full.wav` file.

## Async Extraction

`run_extraction()` uses `asyncio` because extraction is I/O-bound and there may be several source URLs.

For each source, it creates one async task:

```python
asyncio.create_task(run_ffmpeg_for_source(...))
```

Each task starts an ffmpeg subprocess with `asyncio.create_subprocess_exec()`. All ffmpeg processes run concurrently, one per source. The Python event loop waits for them together with:

```python
await asyncio.gather(*tasks)
```

The timeout is `total_duration_seconds + EXCEDING_TIME_BUFFER_SECONDS`. If the timeout is reached, unfinished ffmpeg tasks are cancelled and their subprocesses are terminated.

This asyncio layer is only for recording. It does not do transcription work.

## Main Orchestration

`main.py` now starts transcription workers before calling extraction.

The order is:

1. Parse `input_urls` and `total_duration`.
2. Build the expected `pipeline_<source_id>` directories from source metadata.
3. Write `execution_starting_date.txt` once.
4. Start one multiprocessing transcription worker per source directory.
5. Run async ffmpeg extraction.
6. Signal transcription workers that extraction has ended.
7. Wait for transcription workers to finish.
8. Run `merge_transcriptions.main()`.
9. Run `segment_embeddings.main()`.

The key point is that transcription workers are already running while ffmpeg records. They poll the source directory and start transcribing as soon as a segment is safe to process.

## Multiprocessing Transcription

`transcript_segments_cpp.py` uses `multiprocessing.Process`, not a process pool, because the new model is one long-lived worker per source.

`start_transcription_workers()` creates exactly one process for each pipeline directory:

```python
mp.Process(target=transcribe_pipeline_segments, args=(pipeline_dir, stop_event, start_datetime_text))
```

This satisfies the rule that there is only one transcription process per source. Inside a source worker, segments are processed sequentially. If a new segment appears while the previous segment is still being transcribed, nothing else starts. The same worker finishes the current segment first, then moves to the next segment index.

This is useful because whisper transcription is CPU-bound. Running it in separate processes avoids Python GIL contention and lets transcription happen in parallel across sources, while still keeping strict sequential order inside each source.

## Segment Readiness

Each worker runs `transcribe_pipeline_segments()` and tracks:

- `next_segment_index`: the next expected segment number.
- `next_segment_start_seconds`: cumulative start time for that segment.

The worker repeatedly scans the source directory for files matching:

```text
*_out_*.wav
```

A segment is considered ready when either:

- The next segment file already exists, meaning ffmpeg has moved on and closed the previous one.
- Extraction has finished, meaning the current segment is the final segment.

This avoids transcribing a WAV file while ffmpeg is still writing it.

When transcription starts and ends, the code prints:

```text
Starting transcription: <audio_file>
Finished transcription: <audio_file> -> <json_output_path>
```

Each segment transcription is written next to the WAV file with this naming pattern:

```text
<source_id>_out_00000.transcription.json
<source_id>_out_00001.transcription.json
...
```

Each JSON contains the transcription for that segment, plus metadata needed by the later merge step:

- `segment_audio_file`
- `segment_index`
- `segment_start_seconds`
- `segment_duration_seconds`

## Per-Segment Timestamp Behavior

Whisper transcribes each segment as an independent audio file, so its timestamps start at zero for every segment.

For example, segment 2 may contain:

```json
{
  "[00:00:00.000 --> 00:00:06.000]": "first text in segment 2"
}
```

That timestamp is correct only relative to segment 2. It is not correct relative to the whole recording.

To make the final transcription look like the whole audio was transcribed at once, `merge_transcriptions.py` shifts each segment timestamp by that segment's absolute start offset.

## Segment Pre-Merge

Before the old cleaning and block-merge code runs, `merge_transcriptions.main()` now calls:

```python
merge_segment_transcriptions(BASE_DIR)
```

This function scans every `pipeline_*` directory for files matching:

```text
*_out_*.transcription.json
```

It groups those files by `source_id`, sorts them by segment index, and merges them into the normal source-level file:

```text
<source_id>_transcription.json
```

For every timestamp in every segment file, `shift_timestamp()` adds the segment offset:

```python
shifted_start = original_start + segment_offset
shifted_end = original_end + segment_offset
```

The segment offset usually comes from `segment_start_seconds`, written by the transcription worker. If that value is missing, the merge code falls back to a cumulative offset based on previous segment durations.

Example:

- Segment 1 offset: `0` seconds.
- Segment 2 offset: `3600` seconds.
- Segment 2 timestamp: `[00:00:06.000 --> 00:00:09.000]`.
- Final timestamp: `[01:00:06.000 --> 01:00:09.000]`.

The source-level JSON keeps the first segment start datetime and the last segment end datetime. Segment-only fields are removed from the source-level file.

The pre-merge also writes the source-level raw JSON copy under `/outputs/raw`, preserving the previous raw-output behavior but using the correctly shifted full-source transcription.

## Existing Merge Logic

After the pre-merge step creates `<source_id>_transcription.json`, the existing code path continues.

`find_transcription_files()` finds normal source-level transcription files:

```text
*_transcription.json
```

Then `process_transcription_file()` performs the previous operations:

- Load the transcription mapping.
- Parse timestamp keys.
- Correct text with LanguageTool.
- Clean speech text.
- Remove consecutive duplicate speech entries.
- Split oversized entries.
- Merge speech into word-limited blocks.
- Preserve music markers.
- Write `<source_id>_transcription_merged.json`.

This means the new code only prepares the input so the old merge behavior receives a single source-level transcription with correct absolute timestamps.

## Concurrency Summary

There are two concurrency mechanisms, used for different reasons:

- `asyncio` in `extract_audio.py`: runs multiple ffmpeg subprocesses concurrently because recording is I/O-bound and subprocess-based.
- `multiprocessing` in `transcript_segments_cpp.py`: runs one CPU-bound whisper transcription worker per source while avoiding GIL contention.

Within a single source, transcription is sequential. Across different sources, transcription can happen in parallel.

The intended pipeline behavior is:

1. ffmpeg starts recording all sources concurrently.
2. Once source A segment 0 is closed, source A worker starts transcribing it.
3. If source A segment 1 appears while segment 0 is still transcribing, it waits.
4. Source B has its own worker and can transcribe independently.
5. After ffmpeg finishes, workers transcribe each source's final segment.
6. Segment JSON files are timestamp-shifted and merged into source-level transcriptions.
7. Existing merge and embedding steps run as before.
