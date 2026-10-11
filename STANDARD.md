# Luan Sound Repository Standard v1

A Luan sound repository is a set of static files on the web: one manifest, `luan.json`, plus WAV files. Anyone can publish one. Luan Pro users add it by pasting its address, then pick a pack from it. In the Luan app these repositories are called **sound sources**.

This document is for repository authors. It defines the manifest, the audio rules and the hosting rules. `tools/luan_repo.py` (Python 3 standard library only) builds the manifest and enforces every rule below.

## 1. Two version numbers

| Number | Where | Owned by | Meaning |
|---|---|---|---|
| `schemaVersion` | top of `luan.json`, integer | Luan | Version of this standard. Adding optional fields does not change it; only incompatible changes raise it. v1 is `1`. |
| `version` | each pack, integer ≥ 1 | you | Version of the pack's content. Raise it whenever any file or any metadata of the pack changes. |

If a manifest has a higher `schemaVersion` than the installed Luan supports, Luan refuses to add or update it and asks the user to update Luan. A copy that is already downloaded keeps working.

The repository itself has no version number. Changing its name or description needs no confirmation, and added or removed packs are found by comparing the old and new manifest.

## 2. Directory layout

```
<repo-root>/
├── luan.json                 # the manifest; the only file Luan reads first
├── packs/
│   └── <pack-id>/
│       ├── pack.json         # written by you: this pack's metadata
│       └── <event>.wav       # 1–9 event sounds, named after the event
├── assets/
│   └── <sha256>.wav          # written by build: the audio luan.json points to, named by its content
├── README.md
└── LICENSE
```

- You write the top-level fields of `luan.json` by hand. `python3 tools/luan_repo.py build .` generates its `packs` array from `packs/*/pack.json` and the WAV files, including every `sha256` and `size`. Never write hashes by hand.
- You edit the WAV files in `packs/<pack-id>/`. `build` copies each one to `assets/<sha256>.wav` and points `file` there, so a path's content never changes (see [§5](#5-hosting)). A pack whose `version` is unchanged keeps the paths it was published with: Luan treats a changed path as changed content. A pack published by an older version of the tool, with paths such as `packs/<pack-id>/<event>.wav`, therefore moves to `assets/` the next time its `version` goes up, not before.
- `build` never deletes anything in `assets/`. Keep old files there: while a cache still serves an older `luan.json`, Luan downloads the files that one lists.
- Only `luan.json` and the audio files are part of the standard. `pack.json`, `assets/` and the `packs/` layout are conventions of the tool: Luan never reads `pack.json`; it fetches exactly the `file` paths listed in `luan.json`, whatever they are.
- `pack.json` holds every pack field except `id` (the folder name) and `sounds` (generated), for example `{ "name": "Night rain", "version": 1, "license": "CC-BY-4.0" }`. Fields such as `localizations` are copied into `luan.json` as written.

## 3. The manifest: `luan.json`

```json
{
  "schemaVersion": 1,
  "id": "com.example.sounds",
  "name": "Example sounds",
  "description": "Soft sounds for coding sessions",
  "localizations": {
    "zh-Hans": { "name": "示例音效", "description": "写代码时用的轻柔音效" }
  },
  "author": { "name": "Example", "email": "hi@example.com", "url": "https://example.com" },
  "homepage": "https://github.com/example/luan-sounds",
  "packs": [
    {
      "id": "night-rain",
      "name": "Night rain",
      "description": "Raindrops on a window sill",
      "localizations": {
        "zh-Hans": { "name": "夜雨", "description": "雨滴落在窗沿上的轻响" },
        "ja": { "name": "夜の雨" }
      },
      "version": 3,
      "license": "CC-BY-4.0",
      "author": { "name": "Someone" },
      "sounds": {
        "session-start": { "file": "packs/night-rain/session-start.wav", "sha256": "<64 lowercase hex>", "size": 96044 },
        "task-complete": { "file": "packs/night-rain/task-complete.wav", "sha256": "<64 lowercase hex>", "size": 88120 }
      }
    }
  ]
}
```

| Field | Required | Rule |
|---|---|---|
| `schemaVersion` | yes | Integer, `1` for this version |
| `id` | yes | 1–128 characters, `^[a-z0-9]+([.-][a-z0-9]+)*$`; reverse-DNS recommended. `builtin` is reserved. Must never change for the same URL |
| `name` | yes | 1–64 characters, no control characters |
| `description` | no | ≤ 280 characters |
| `localizations` | no | Translated `name` / `description`, see [Localization](#localization) |
| `author` | no | `{ "name" (required), "email"?, "url"? }`; `url` must be `https://` |
| `homepage` | no | `https://` URL |
| `packs` | yes | 1–64 packs with unique `id`s |
| `packs[].id` | yes | 1–64 characters, `^[a-z0-9]+(-[a-z0-9]+)*$` |
| `packs[].name` | yes | 1–64 characters, no control characters |
| `packs[].description` | no | ≤ 280 characters |
| `packs[].localizations` | no | Same as the top-level `localizations` |
| `packs[].version` | yes | Integer ≥ 1 |
| `packs[].license` | no | SPDX identifier (e.g. `CC-BY-4.0`) or `LicenseRef-…` |
| `packs[].author` | no | Same shape as the top-level `author`; defaults to the repository author |
| `packs[].sounds` | yes | At least one known event |
| `sounds.<event>.file` | yes | Relative path using only `A–Z a–z 0–9 . _ -` and `/`, ≤ 255 characters; no empty, `.` or `..` segments; ends in `.wav` (lowercase) |
| `sounds.<event>.sha256` | yes | SHA-256 of the file, 64 lowercase hex characters |
| `sounds.<event>.size` | yes | File size in bytes, integer |

Lengths count Unicode code points. Integers must be JSON integers (`1`, not `1.0` or `"1"`).

### Localization

Write `name` and `description` in the language most of your users read; English is a good default. Add translations in `localizations`, keyed by BCP 47 language tag:

```json
"localizations": {
  "zh-Hans": { "name": "夜雨", "description": "雨滴落在窗沿上的轻响" },
  "ja": { "name": "夜の雨" }
}
```

- Keys are language tags of the form language[-Script][-REGION][-variant], such as `ja`, `zh-Hans`, `pt-BR`. Tags are case-insensitive; the same tag must not appear twice.
- Each value may contain `name` and/or `description`, with the same rules as the main fields. Anything left out falls back to the main field.
- Luan goes through the user's preferred languages in order and tries each from the full tag down (`zh-Hans-CN`, then `zh-Hans`, then `zh`), separately for `name` and `description`. When nothing matches it uses the main field.
- Luan skips an invalid entry (bad tag, over-long text) instead of rejecting the repository. `luan_repo.py check` reports it as an error so you can fix it.
- `localizations` is allowed on the repository and on each pack. It is an optional addition to v1 and does not change `schemaVersion`; older versions of Luan ignore it.

### Events

| Key | When it plays |
|---|---|
| `session-start` | A coding session starts |
| `task-acknowledge` | A task is accepted |
| `task-complete` | A task finishes |
| `task-error` | A task fails |
| `input-required` | The agent needs approval |
| `input-required-question` | The agent asks a question |
| `resource-limit` | The context is being compacted |
| `user-spam` | Several prompts sent in quick succession |
| `idle-reminder` | Idle reminder |

A pack does not need all nine. Missing events use Luan's built-in default sounds.

### Forward compatibility

- Unknown fields are ignored.
- Unknown event keys are ignored; they never make the whole repository invalid. New events can be added without changing `schemaVersion`.
- `schemaVersion` is raised only for incompatible changes: removing a field, or changing the meaning or type of an existing one.

`luan_repo.py check` prints a warning for unknown fields and events so that typos are visible, but they are not errors.

## 4. Audio rules

The same numbers are used by this standard, by `luan_repo.py` and by Luan.

| Rule | Value | `luan_repo.py` | Luan |
|---|---|---|---|
| Format | WAV, linear PCM, 16- or 24-bit integer | error | rejects |
| Sample rate | 44.1 kHz or 48 kHz | error | rejects |
| Channels | 1 or 2 | error | rejects |
| Duration | longer than 0, at most 5 seconds | error | rejects |
| File size | ≤ 2 MiB and exactly equal to `size` | error | rejects |
| Repository size | ≤ 64 MiB in total, identical files counted once | error | rejects |
| Manifest size | `luan.json` ≤ 1 MiB | error | rejects |
| Loudness | Recommended: peak ≤ −1 dBFS, loudness close to Luan's built-in sounds | warning | accepted; turned down at playback |

WAV is the only format in v1 because it can be validated exactly with a standard library, without ffmpeg, both in CI and in the app. The limits leave plenty of room: five seconds of 48 kHz, stereo, 24-bit audio is about 1.4 MiB.

Luan measures the peak and RMS of every sound and, if it is louder than the built-in sound for the same event, plays it quieter. It never makes a sound louder.

## 5. Hosting

- Every file must be served over HTTPS with its exact bytes.
- All files must be on the same host as `luan.json`, in the same directory or below it. Redirects are followed only within that scope.
- GitHub raw URLs (`https://raw.githubusercontent.com/<owner>/<repo>/<branch>/luan.json`) and GitHub Pages work. GitHub Releases assets do not: they redirect to another host.
- jsDelivr's GitHub mirror (`https://cdn.jsdelivr.net/gh/<owner>/<repo>@<ref>/luan.json`) also works. It caches branch addresses such as `@main` for up to about 12 hours, so an update may reach users late; a tag or commit ref (`@v3`, `@<commit>`) is never stale.
- Caches work per path: right after a push, a host can serve the new `luan.json` with an older copy of an audio file at the same path (jsDelivr for hours, GitHub raw for minutes). Luan then finds a SHA-256 that doesn't match, installs nothing and tries again later. Never change the content behind a published path; give new content a new path. `luan_repo.py build` does this for you with `assets/<sha256>.wav`, and `check` reports a file named after a SHA-256 whose content differs.
- Paths are case-sensitive on most hosts. Do not commit symlinks; GitHub raw serves a symlink as a small text file.

Addresses users can paste into Luan:

| Pasted address | Luan reads |
|---|---|
| `https://github.com/<owner>/<repo>` (optionally ending in `/` or `.git`) | `https://raw.githubusercontent.com/<owner>/<repo>/HEAD/luan.json`, the default branch |
| `https://github.com/<owner>/<repo>/tree/<ref>/<folder>` | `https://raw.githubusercontent.com/<owner>/<repo>/<ref>/<folder>/luan.json` |
| `https://github.com/<owner>/<repo>/blob/<ref>/<path>/luan.json` | the matching `raw.githubusercontent.com` address |
| `https://cdn.jsdelivr.net/gh/<owner>/<repo>[@<ref>]` with nothing after it | that address plus `/luan.json` |
| any other HTTPS address ending in `.json` | that address as is |
| any other HTTPS address ending in `/`, or whose last segment has no extension | that address plus `/luan.json` |

A ref that contains `/` (for example `feature/x`) cannot be told apart from a folder in a GitHub page address: Luan takes the first segment as the ref. Paste the `raw.githubusercontent.com` address instead. Addresses with `http://`, a user name or password, `?` or `#` are rejected. Every hosting rule above applies to the address Luan reads, not to the one pasted.

## 6. Updates

Luan Pro checks every added repository for updates in the background every twelve hours, and whenever the user asks. With automatic updates on (the default) it downloads and applies new pack versions right away; with them off it shows a summary, for example "Night rain v3 → v4 · 2 packs added", and the user decides whether to update. An update applies the whole new manifest at once. If an automatic update can't be installed, for example because a file is missing or doesn't match its `sha256`, Luan keeps what it has and tries again after 15 minutes, 1 hour and 4 hours, then every twelve hours.

To publish a change to a pack, change its files or metadata, raise `version` in its `pack.json`, run `build` and push the new files in `assets/` together with `luan.json`. Rules Luan applies when comparing manifests:

- A new pack id means the pack was added; a missing id means it was removed. If the user's selected pack is removed, Luan keeps playing the copy it already has.
- A pack whose files or metadata changed must have a larger `version`. If the content changed and `version` stayed the same, Luan treats the manifest as invalid and offers no update.
- A manifest in which some packs have a smaller `version` than the copy Luan already has, and none a larger one, is an older copy still held by a cache. Luan ignores it and keeps what it has. Smaller and larger versions mixed in one manifest make it invalid.
- The repository `id` must not change.

`luan_repo.py build` refuses to write a manifest in which a changed pack kept its version. `luan_repo.py check . --previous old-luan.json` applies the same comparison against a previously published manifest; the sample CI workflow does this for every push and pull request.

## 7. Verified publishers

Luan ships a short list of verified publishers, each with the URL prefixes it controls. A repository whose manifest address starts with one of those prefixes shows a "Verified" badge in the app, with the publisher's name where there is room (for example "Verified · Luan"); any other repository is shown as unverified when the user is asked to confirm adding it. The prefix is compared, ignoring case, with the address Luan reads after resolving what was pasted (see §5), so a repository gets the same result whichever form was pasted. Luan's own repository is verified when read from `https://raw.githubusercontent.com/onepiece-studio/luan-sounds/` from `https://cdn.jsdelivr.net/gh/onepiece-studio/luan-sounds@` (any ref), or from `https://cdn.jsdelivr.net/gh/onepiece-studio/luan-sounds/` (no ref, the default branch). The list is curated by Luan and changes only with a new app release.

A badge says who controls the address. It says nothing else. The SHA-256 values in a manifest only prove that the downloaded files are the ones the manifest lists; they do not prove who published it.

## 8. Validate and publish

```sh
python3 tools/luan_repo.py build .   # regenerate the packs array, then check
python3 tools/luan_repo.py check .   # check only; exit status 1 on any error
```

Each problem is printed as `error: <where>: <message> [<rule>]`. Warnings (unknown fields, loud peaks) do not change the exit status.

To check every push on GitHub, copy `tools/luan_repo.py` into your repository and add `.github/workflows/check.yml` from the official repository: <https://github.com/onepiece-studio/luan-sounds>. The JSON Schema `schema/luan-v1.schema.json` covers the manifest structure for editors; the tool covers everything else (hashes, sizes, audio).

## 9. Licensing your sounds

Only publish sounds you have the right to distribute, and say how they may be used: set `license` on each pack and include a `LICENSE` file.
