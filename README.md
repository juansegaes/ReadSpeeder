# ReadSpeeder

The RSVP reading app for android

[![Release qualification](https://github.com/juccul/ReadSpeeder/actions/workflows/release-qualification.yml/badge.svg)](https://github.com/juccul/ReadSpeeder/actions/workflows/release-qualification.yml)

## daRSVP fork

This repository is a fork of
[juccul/ReadSpeeder](https://github.com/juccul/ReadSpeeder). Upstream is a
fixed-speed RSVP reader. This fork adds **dynamic adaptive RSVP (daRSVP)**: a
desktop scorer gives every word its own display time from word length, frequency,
language-model surprisal, and punctuation. The app imports the resulting
`.darsvp.json` file and plays it with those timings. Ordinary TXT/PDF/EPUB
documents keep the upstream fixed-speed and smart-pause behavior.

### What differs from upstream

| Area | Upstream ReadSpeeder | This fork |
| --- | --- | --- |
| Word timing | One speed for the whole book; optional smart pauses and complex-word pauses | Optional per-word timing from a scored `.darsvp.json` file |
| Scored-book import | Not supported | Imports `.darsvp.json` (format version 1) |
| Desktop tooling | None | `tools/darsvp-scorer`: TXT/EPUB scorer with a SmolLM3 llama.cpp backend, Vulkan acceleration, caching, inspection, and a frequency-only fallback |
| Timing control | WPM slider | WPM slider plus a **daRSVP strength** slider (0–100%) that blends scored timing with the baseline length/punctuation timing |
| Storage | Document cache codec version 1 | Codec version 2 stores per-word weights; version 1 caches still load |
| Text cleanup | EPUB whitespace normalization | EPUB conversion also joins in-word tabs and repairs clear merged words |
| Everything else | — | Unchanged: library, themes, typography, chapters, progress, standard reader, privacy |

### Compatibility

- The application ID is still `com.juckul.readspeeder`, so installing this build
  replaces an upstream install only if it is signed with the same key. A debug
  build signed with a different key needs the old app uninstalled first (which
  erases its library).
- Version 1 document caches load without migration. New caches use version 2.
- Unscored documents behave exactly as upstream. The daRSVP setting only affects
  documents that carry weights.
- The app still has no network access. Scoring runs on the PC; the phone only
  reads the JSON file.

### Workflow

1. Score the book on a PC with the
   [daRSVP scorer](tools/darsvp-scorer/README.md).
2. Copy the `.darsvp.json` file to the phone.
3. Import it from the app's add button and read it.

The **daRSVP strength** slider (Settings → Speed reading) blends the scored
timing with the app's baseline length/punctuation timing: 0% is the plain
baseline, 100% is the full daRSVP timing. Scored timings are relative, so the
WPM slider still sets the overall pace.

See [docs/daRSVP.md](docs/daRSVP.md) for the format, the scoring formula, and
known limitations. Read the background article:
[What is daRSVP?](https://www.gardenofadam.com/writing/what-is-darsvp/)

ReadSpeeder is a free and open-source Android app for reading text with rapid
serial visual presentation (RSVP) or a conventional scrolling reader. Use it to
work through books, articles, study material, and pasted text at your own pace.

## Features

- Import TXT, PDF, and EPUB documents, or paste text directly into the app.
- Import daRSVP-scored `.darsvp.json` books with per-word timing.
- Read one word at a time with adjustable RSVP speed, or switch to standard reading.
- Navigate chapters and automatically resume from saved reading progress.
- Organize a local library with covers, search, sorting, metadata editing, and deletion.
- Customize reading typography, spacing, themes, and Android dynamic color.
- Read offline without ads or an account.

ReadSpeeder supports Android 7.0 and newer.

## Privacy

ReadSpeeder has no in-app network access and does not collect or transmit user
data. Imported documents, settings, and reading progress are stored in the
app's private storage. See the [privacy policy](PRIVACY.md) for backup and
deletion details.

## Build and run

Install JDK 17 or newer and the Android SDK 37.1, then clone the repository and
run the Gradle wrapper from its root:

```shell
./gradlew assembleDebug
```

On Windows, use `.\gradlew.bat assembleDebug`. The APK is written to
`app/build/outputs/apk/debug/app-debug.apk` and can be installed on a connected,
authorized device with:

```shell
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Run the automated checks with:

```shell
./gradlew testDebugUnitTest connectedDebugAndroidTest lintRelease
```

`connectedDebugAndroidTest` requires a running emulator or connected device.
Use `./gradlew assembleRelease` to create a minified release APK; release signing
must be configured separately before distribution.

## Contributing and support

Bug reports and feature requests are welcome through
[GitHub Issues](https://github.com/juccul/ReadSpeeder/issues). See
[CONTRIBUTING.md](CONTRIBUTING.md) before submitting a change.

If ReadSpeeder is useful to you, you can support its development on
[Ko-fi](https://ko-fi.com/juckul).

## License

ReadSpeeder is free software licensed under the
[GNU General Public License version 3](LICENSE) (`GPL-3.0-only`). Third-party
components remain subject to their respective licenses and notices.
