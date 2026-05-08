What Each Parameter Does

K
- Controls the size of the left and right context windows around each possible boundary.
- For a candidate split at position i, the algorithm compares:
  - the mean embedding of the K units before i
  - against the mean embedding of the K units after i
- Bigger K:
  - more stable, smoother boundaries
  - less sensitive to short topic changes
  - needs more units on both sides, so boundaries near the start/end become impossible to score
- Smaller K:
  - more sensitive
  - works better for short stories
  - more noisy, can split inside one story


MIN_GAP_UNITS
- After finding candidate peaks, this enforces a minimum distance between accepted boundaries.
- Bigger MIN_GAP_UNITS:
  - fewer cuts
  - avoids over-segmentation
  - can suppress a real boundary if stories are short
- Smaller MIN_GAP_UNITS:
  - allows more cuts
  - helps with short stories
  - increases risk of splitting inside a story


PEAK_THRESHOLD
- Minimum boundary score required for a local maximum to count as a candidate.
- Since score is 1 - cosine_similarity, higher means “left and right contexts are more different”.
- Bigger PEAK_THRESHOLD:
  - stricter
  - fewer boundaries
  - can miss subtle transitions
- Smaller PEAK_THRESHOLD:
  - more permissive
  - finds weaker topic shifts
  - can create false positives

  
What Happened In Your Experiments
Expected: 3 news per file.
Observed:
- outputs/news_short/: 2 segments
- outputs/news_medium/: 3 segments
- outputs/news_long/: 2 segments
So the defaults are good for medium stories, but not for short or long ones.
Short Result
- One output merged news 1 + most of news 2.
- The other output starts with the last sentence of news 2 and then includes news 3.
- So it both:
  - missed a real boundary
  - and placed a wrong boundary inside a story
Interpretation:
- Default K=6 and MIN_GAP_UNITS=8 are too large for short stories.
- In these tests, short stories are roughly 25 total units / 3 stories ~= 8.3 units per story.
- That means MIN_GAP_UNITS=8 is almost the whole story length, which is too restrictive.
Medium Result
- Produced exactly 3 outputs.
- Medium stories are roughly 66 / 3 ~= 22 units per story.
- That matches the defaults well.
Long Result
- Produced 2 outputs.
- Zaragoza was separated correctly.
- Cantabria + agricultura orbital were merged.
- Long stories are roughly 139 / 3 ~= 46 units per story.
Interpretation:
- Here MIN_GAP_UNITS=8 is not too big.
- The more likely issue is that the true boundary score was not strong enough relative to the threshold, or internal variation inside the long stories competed with the real boundary.
- Long stories often benefit from:
  - a slightly larger K to smooth paragraph-level noise
  - a slightly lower PEAK_THRESHOLD to catch softer transitions
  - sometimes a larger MIN_GAP_UNITS to avoid internal false peaks winning
Best Rule
Tune by average units per story, not by words.
In production:
- a “unit” is one transcription chunk
In your manual test:
- a “unit” is one sentence-like chunk, sometimes split again at 40 words
From your current samples:
- 200-300 words/story -> about 8-10 units/story
- 500-600 words/story -> about 20-25 units/story
- 1000-1200 words/story -> about 40-50 units/story
Practical Tuning Rules
Let L = average units per story.
Choose K:
- rule of thumb: K ~= 0.2 * L
- keep it roughly in [2, 10]
- if stories are short, reduce it aggressively
Choose MIN_GAP_UNITS:
- rule of thumb: MIN_GAP_UNITS ~= 0.35 * L
- it should be clearly smaller than the shortest real story
- if real stories are being merged, lower it
Choose PEAK_THRESHOLD:
- start around 0.20-0.25
- lower it if real boundaries are missed
- raise it if you see false splits inside stories
Recommended Presets
For short news, 200-300 words/story:
- K = 2 or 3
- MIN_GAP_UNITS = 3 or 4
- PEAK_THRESHOLD = 0.12 to 0.18
For medium news, 500-600 words/story:
- K = 4 to 6
- MIN_GAP_UNITS = 6 to 8
- PEAK_THRESHOLD = 0.20 to 0.25
For long news, 1000-1200 words/story:
- K = 7 to 9
- MIN_GAP_UNITS = 10 to 15
- PEAK_THRESHOLD = 0.16 to 0.22
How To Decide What To Change
If two news are merged:
- first lower PEAK_THRESHOLD
- if stories are short, also lower K
- if stories are short, lower MIN_GAP_UNITS
If one news is split into two:
- raise PEAK_THRESHOLD
- increase MIN_GAP_UNITS
- sometimes increase K
If boundaries are unstable in short files:
- reduce K first
- then reduce MIN_GAP_UNITS
If long files miss one transition:
- try larger K
- and slightly lower PEAK_THRESHOLD
For Your Current Tests
I would try:
Short:
- K=3
- MIN_GAP_UNITS=4
- PEAK_THRESHOLD=0.15
Medium:
- keep current defaults
Long:
- K=8
- MIN_GAP_UNITS=12
- PEAK_THRESHOLD=0.20