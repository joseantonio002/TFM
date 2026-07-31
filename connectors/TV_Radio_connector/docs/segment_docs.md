# Segment Embeddings

`segment_embeddings.py` segments a merged transcription into separate news stories.

## How It Works

1. The merged transcription is loaded and converted into ordered units.
2. Each unit is embedded with `BAAI/bge-m3`.
3. For every possible boundary between two adjacent units, the algorithm compares:
  - the mean embedding of the `K` units on the left
  - the mean embedding of the `K` units on the right
4. The boundary score is computed as `1 - cosine_similarity(left_mean, right_mean)`.
5. Local maxima above `PEAK_THRESHOLD` are considered candidate boundaries.
6. `MIN_GAP_UNITS` removes candidates that are too close to a stronger one.
7. The remaining boundaries define the final segmented stories.

## Parameters

### `-k`

Window size used on each side of a possible boundary.

- Lower values make the algorithm more sensitive to short topic changes.
- Higher values make it more stable, but can miss short stories.

Default:

```text
6
```

### `-mgu`

Minimum number of transcription units between accepted boundaries.

- Lower values allow more cuts.
- Higher values reduce over-segmentation, but can merge nearby real stories.

Default:

```text
8
```

### `-pt`

Minimum boundary score required for a local maximum to be accepted as a candidate.

- Lower values detect more potential boundaries.
- Higher values are stricter and produce fewer cuts.

Default:

```text
0.25
```

## Presets

You can use `-news_length` instead of manually passing `-k`, `-mgu`, and `-pt`.

Accepted values:

- `short`
- `medium`
- `long`

Preset values:

```text
short  -> K=3, MIN_GAP_UNITS=4,  PEAK_THRESHOLD=0.16
medium -> K=5, MIN_GAP_UNITS=8,  PEAK_THRESHOLD=0.22
long   -> K=8, MIN_GAP_UNITS=12, PEAK_THRESHOLD=0.18
```

If `-news_length` is provided, you must not pass `-k`, `-mgu`, or `-pt` in the same command.

## Preset Philosophy

These presets are intentionally biased toward catching real story boundaries even if that means some stories may be split into more than one segment.

Because of that:

- `K` is kept on the lower side to stay sensitive to topic changes.
- `PEAK_THRESHOLD` is kept on the lower side to avoid missing weaker real boundaries.
- `MIN_GAP_UNITS` is kept on the upper side to avoid too many cuts clustering together around the same transition.

This bias favors recall of true boundaries over perfectly clean segmentation.

## Examples

Manual parameters:

```bash
python main.py -i <url> -t 30 -k 5 -mgu 8 -pt 0.22
```

Preset:

```bash
python main.py -i <url> -t 30 -news_length medium
```

Running only the segmentation step:

```bash
python segment_embeddings.py -news_length long
```
