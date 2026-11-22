# daRSVP scorer

`darsvp-score` is a desktop tool that reads a TXT or EPUB book and writes a
`.darsvp.json` file with one reading-time weight per word. The ReadSpeeder
Android app imports that file and uses the weights to give each word its own
display time (dynamic adaptive RSVP).

This tool is part of the daRSVP fork and is not present in upstream
ReadSpeeder. See [docs/daRSVP.md](../../docs/daRSVP.md) for what the fork adds
and what stays the same.

The scorer runs on the PC. The phone never parses the EPUB for a scored book,
so the word sequence and the weights always line up.

## What it does

For each word the scorer combines three layers:

1. **Lexical** — word length and corpus frequency.
2. **Surprisal** — how unexpected the word is in context, from a language model.
3. **Pauses** — punctuation, sentence, paragraph, and chapter breaks.

The result is an integer **duration multiplier in hundredths**: `100` means the
normal base time, `200` means twice as long. The app converts a weight to
milliseconds as `base * weight / 100`, where `base = 60_000 / WPM`.

## Install

Requirements: Python 3.10+, a Vulkan-capable GPU (optional but recommended),
and enough disk space for the model.

```powershell
cd tools\darsvp-scorer
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[test]"
```

### Build llama-cpp-python with Vulkan (Windows)

1. Install the current AMD Adrenalin driver.
2. Install **Visual Studio Build Tools** with the **Desktop development with C++**
   workload, including **C++ CMake tools for Windows**.
3. Install the **LunarG Vulkan SDK** (it sets `VULKAN_SDK` and provides `glslc`).
4. Open a new PowerShell window.

Check that Vulkan sees the GPU:

```powershell
vulkaninfoSDK --summary
```

Then build inside the venv:

```powershell
$env:CMAKE_ARGS = "-DGGML_VULKAN=on"
pip install --no-cache-dir --force-reinstall --verbose "llama-cpp-python>=0.3"
```

If CMake cannot find a compiler, use the **x64 Native Tools Command Prompt for
VS**. If Vulkan or `glslc` is missing, the SDK was not seen. A CPU-only build
(`pip install llama-cpp-python`) also works, but is slower.

### Model

The reference build uses:

- Repository: `mradermacher/SmolLM3-3B-Base-GGUF`
- File: `SmolLM3-3B-Base.Q8_0.gguf` (~3.3 GB)

The base model is preferred because it is a plain next-word predictor. The
instruct model also works but is tuned for chat. Store the model outside the
repository, for example in `C:\Users\<you>\models\`.

## Usage

```powershell
# Check the model, GPU, and tokens per second
darsvp-score check --model C:\Users\you\models\SmolLM3-3B-Base.Q8_0.gguf

# Score a book with the language model
darsvp-score score book.epub --model C:\Users\you\models\SmolLM3-3B-Base.Q8_0.gguf

# Score without a model (word frequency only; much faster, less accurate)
darsvp-score score book.epub --backend unigram

# Inspect the result
darsvp-score inspect book.darsvp.json --count 40 --top 20
```

`score` writes `<input>.darsvp.json` next to the input unless `-o` is given.
Useful options:

- `--lang en|es|fr|de|it|pt` — language for frequency and abbreviation rules.
- `--config weights.toml` — override the default weight configuration.
- `--normalize content|total` — see below.
- `--debug-fields` — include surprisal, Zipf, and content values in the JSON.
- `--cache-dir PATH` — cache model surprisal values (default `.darsvp-cache`).
- `--max-words N` — score only the first N words (rounded to a paragraph end).
- `--no-cover` — omit the cover image.
- `--no-repair-merged-words` — keep words that EPUB conversion accidentally
  joined. By default the scorer splits clear cases such as `Thencame` into
  `Then came`; see below.

The cache key includes the model file name and the full word stream, so changing
either re-scores from scratch. Keep the cache out of version control.

## EPUB text cleanup

Some EPUBs come from scanned or PDF text and carry artifacts that break words
apart or join them together. The scorer cleans the common cases:

- **Tabs inside a word** (`press\ted`, `wha\tev\ter`) are removed, because a tab
  between two letters is a conversion artifact, not a word separator. Tabs next
  to whitespace still become spaces.
- **Merged words** (`Thencame`, `sayto`, `mypoor`) are split when the whole token
  is unknown to the word-frequency dictionary and both halves are common words.
  The split is conservative: known words like `jurymen` are left alone. Disable
  it with `--no-repair-merged-words`.
- Soft hyphens and zero-width characters are removed.
- Missing spaces that produce a plausible single word cannot be recovered, so a
  badly converted EPUB may still contain a few artifacts.

## The weight formula

For each word `i`:

```text
z_surprisal = clip((S_i - median) / MAD, z_surprisal_min, z_surprisal_max)
z_length    = clip((letters_i - length_center) / length_scale, z_length_min, z_length_max)
z_freq      = clip((zipf_center - zipf_i) / zipf_scale, z_freq_min, z_freq_max)
spill_i     = max(0, z_surprisal[i-1])   # 0 at the first word of a paragraph

cost = 1
     + w_surprisal * z_surprisal
     + w_length    * z_length
     + w_freq      * z_freq
     + w_spill     * spill

content = clip(cost, content_min, content_max)          # words with letters/digits
content = empty_core_content                            # punctuation-only words

if normalize == "content":
    content = content / mean(content of content words)

pause = punctuation / sentence / paragraph / chapter pause, if any

final = clip(content + pause, final_min, final_max)
if normalize == "total":
    final = final / mean(final)

weight = round(final * 100)
```

`normalize = "content"` (the default) keeps the average content word at `100`
before pauses. The real average speed is therefore a little below the WPM
slider because pauses are added on top. `normalize = "total"` makes the slider
match the real average speed.

At 300 WPM (base 200 ms), typical values are: content words ≈ 200 ms, "the"
≈ 100 ms, a long rare surprising word ≈ 400–500 ms, comma +150 ms, semicolon
+200 ms, sentence end +300 ms, paragraph end +400 ms.

## Configuration keys

Copy `weights.example.toml` and pass it with `--config`. Every key is optional;
unknown keys are rejected.

| Key | Default | Meaning |
| --- | --- | --- |
| `w_surprisal` | `0.22` | Weight of the standardized surprisal term |
| `w_length` | `0.12` | Weight of the standardized word-length term |
| `w_freq` | `0.08` | Weight of the standardized inverse-frequency term |
| `w_spill` | `0.08` | Extra cost from the previous word's surprisal |
| `z_surprisal_min` | `-2.0` | Lower clip for the surprisal z-score |
| `z_surprisal_max` | `3.0` | Upper clip for the surprisal z-score |
| `length_center` | `5.0` | Mean letters per word |
| `length_scale` | `3.0` | Standard deviation of letters per word |
| `z_length_min` | `-1.33` | Lower clip for the length z-score |
| `z_length_max` | `3.0` | Upper clip for the length z-score |
| `zipf_center` | `4.5` | Mean Zipf frequency |
| `zipf_scale` | `1.5` | Standard deviation of Zipf frequency |
| `z_freq_min` | `-1.5` | Lower clip for the frequency z-score |
| `z_freq_max` | `2.5` | Upper clip for the frequency z-score |
| `digit_zipf` | `3.5` | Zipf value assumed for words containing digits |
| `content_min` | `0.5` | Minimum content multiplier |
| `content_max` | `2.5` | Maximum content multiplier |
| `empty_core_content` | `0.5` | Multiplier for words with no letters or digits |
| `pause_chapter_end` | `2.5` | Chapter-end pause |
| `pause_paragraph_end` | `2.0` | Paragraph-end pause |
| `pause_sentence_end` | `1.5` | Sentence-end pause |
| `pause_semicolon_colon` | `1.0` | Semicolon or colon pause |
| `pause_comma` | `0.75` | Comma pause |
| `pause_dash` | `0.75` | Dash pause |
| `pause_close_paren` | `0.3` | Closing-parenthesis pause |
| `pause_abbreviation` | `0.3` | Abbreviation pause (e.g. "Dr.") |
| `final_min` | `0.4` | Minimum multiplier after pauses |
| `final_max` | `6.0` | Maximum multiplier after pauses |
| `normalize` | `"content"` | `"content"` or `"total"` |

## Tuning

- **Everything feels too slow or too fast** — use the WPM slider in the app.
  Weights are relative, so the whole book scales with the slider.
- **Not enough contrast between easy and hard words** — raise `w_surprisal`
  (for example `0.30`) or lower `content_min`.
- **Pauses feel too long** — lower the `pause_*` values.
- **Re-scoring is slow** — keep `--cache-dir` and reuse it while tuning. Only
  the weight combination is recomputed when the cache is valid.
- **The slider should equal the real average speed** — use
  `normalize = "total"`.

## Output format

The file is compact UTF-8 JSON. The important fields are:

- `format: "darsvp"`, `version: 1`
- `title`, `author`, `language`
- `text` — paragraphs separated by two newlines; words separated by single
  spaces
- `weights` — one integer per word, in hundredths
- `chapters` — `{ "title": ..., "startWord": ... }`
- `cover` — optional base64 JPEG/PNG
- `debug` — optional, with `--debug-fields`

The Android importer validates the file and rejects mismatched word counts,
unsupported versions, and invalid weights.

## Tests

```powershell
cd tools\darsvp-scorer
.\.venv\Scripts\python.exe -m pytest -q
```

The llama integration test is skipped unless `DARSVP_TEST_MODEL` points to a
GGUF file:

```powershell
$env:DARSVP_TEST_MODEL = "C:\Users\you\models\SmolLM3-3B-Base.Q8_0.gguf"
.\.venv\Scripts\python.exe -m pytest -q
```

## License

Part of the ReadSpeeder project and licensed under GNU GPL v3.
