# Changelog

Notable changes to ReadSpeeder are documented here.

## Unreleased

### Added

- daRSVP support: import `.darsvp.json` books scored on a PC and play each word
  with its own timing from word length, frequency, language-model surprisal,
  and punctuation.
- A "daRSVP timing for scored books" setting, on by default.
- A "daRSVP strength" slider (0–100%) that blends scored timings with the
  app's baseline length/punctuation timing; 100% is full daRSVP.
- A desktop scorer (`tools/darsvp-scorer`) with a SmolLM3 llama.cpp backend,
  Vulkan acceleration, caching, inspection, and a frequency-only fallback.

### Fixed

- EPUB extraction no longer splits words on in-word tabs or leaves clear
  conversion merges like `Thencame` as one word.

### Changed

- Document caches use codec version 2 so scored documents keep their word
  weights across app restarts. Version 1 caches still load.

## 1.0.0 - 2026-08-15

### Added

- TXT, PDF, and EPUB importing, plus pasted-text reading.
- RSVP and standard reading modes with configurable presentation.
- A persistent, searchable library with chapter and progress restoration.
- Light, dark, and dynamic-color themes.
- Release qualification across Android API 24 through 36.
- GNU General Public License version 3 project licensing.

### Changed

- The Android application ID is now `com.juckul.readspeeder`.
