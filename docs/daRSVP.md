# daRSVP in this fork

This document explains what the daRSVP fork adds to
[juccul/ReadSpeeder](https://github.com/juccul/ReadSpeeder), how the pieces fit
together, and what is still the same as upstream.

## Short version

Upstream ReadSpeeder shows one word at a time at a single speed. This fork can
also read a **scored** book, where every word carries its own duration
multiplier. The scoring happens on a PC; the phone only reads the resulting
`.darsvp.json` file. Unscored books keep the upstream behavior.

## What is added

### 1. A desktop scorer

`tools/darsvp-scorer` is a Python package that reads a TXT or EPUB book and
writes a `.darsvp.json` file. It combines:

- **Lexical features** — word length and corpus frequency.
- **Surprisal** — how unexpected the word is in context, from a language model
  (SmolLM3-3B-Base by default) or a frequency-only fallback.
- **Pauses** — punctuation, sentence, paragraph, and chapter boundaries.

The output is one integer weight per word in hundredths: `100` means the normal
base time, `200` means twice as long. See the
[scorer README](../tools/darsvp-scorer/README.md) for install, usage, and the
full formula.

### 2. A scored-book import path

The app imports `.darsvp.json` files through the same add button as ordinary
documents. The importer validates the format, version, word count, and weights,
then stores the text and weights. The file can also carry title, author,
language, chapters, and a base64 cover.

### 3. Per-word timing in the reader

When a document has weights and the **daRSVP timing for scored books** setting is
on, the reader delays each word by:

```text
base = 60_000 / WPM
delay = base * weight / 100
```

The **daRSVP strength** slider blends the scored weight `y` with the app's
baseline multiplier `z` (word length plus punctuation):

```text
final = (1 - alpha) * y + alpha * z
```

where `alpha` is the slider's complement: at 0% strength the reader uses the
plain baseline; at 100% it uses the full scored weight. Scored weights are
relative, so the WPM slider still controls the overall pace.

### 4. Storage format version 2

Document caches now store an optional short array of word weights. Version 1
caches still load and are treated as unscored. Unscored documents are written
without the weight array, so their cache size is unchanged.

### 5. EPUB text cleanup

The scorer normalizes whitespace and additionally:

- joins words split by in-word tabs from print/PDF conversions (`press\ted` →
  `pressed`);
- repairs clear merged words when the whole token is unknown and both halves are
  common (`Thencame` → `Then came`).

The repair is conservative and can be disabled with
`--no-repair-merged-words`.

## What is unchanged from upstream

- The library, covers, search, sorting, metadata editing, and deletion.
- RSVP and standard reading modes, themes, typography, and dynamic color.
- Chapter navigation, progress restore, and the file picker.
- TXT, PDF, and EPUB import for ordinary documents.
- No network access and no account.
- The application ID `com.juckul.readspeeder`.

## Compatibility and migration

- **Signing:** the app ID is the same, so a build signed with the same key can
  replace an upstream install. A debug build signed with a different key cannot;
  Android requires uninstalling the old app, which erases its library.
- **Caches:** version 1 caches load without migration. New caches use version 2.
- **Behavior:** documents without weights always use the upstream timing,
  regardless of the daRSVP setting.
- **Scored text:** the scorer's text is authoritative. The app does not re-parse
  the EPUB for scored books, so the word sequence and the weights always match.

## Limitations

- **Scoring needs a PC.** The app does not run the language model. Without a
  scored file, a book uses fixed-speed timing.
- **The model is not bundled.** Download the GGUF separately; the scorer README
  names the reference file.
- **Text repair is heuristic.** Badly converted EPUBs can still contain a few
  merged or split words. A valid merged word is never split.
- **Scored timing is relative.** The WPM slider scales the whole book; the
  strength slider controls how much the per-word contrast applies.
- **Device verification.** The daRSVP import and timing were unit-tested and
  built, but the final on-device check depends on a device or emulator being
  available.
