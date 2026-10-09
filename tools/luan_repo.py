#!/usr/bin/env python3
"""Build and validate a Luan sound repository (standard v1).

    python3 tools/luan_repo.py build <repo-root>   regenerate the packs array of luan.json
    python3 tools/luan_repo.py check <repo-root>   validate luan.json and every audio file

Python 3.9+ standard library only. See STANDARD.md for the rules this tool enforces.
"""
import argparse
import array
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

SCHEMA_VERSION = 1
MANIFEST = 'luan.json'
PACK_FILE = 'pack.json'
EVENTS = ('session-start', 'task-acknowledge', 'task-complete', 'task-error', 'input-required',
          'input-required-question', 'resource-limit', 'user-spam', 'idle-reminder')

MIB = 1024 * 1024
MAX_MANIFEST_BYTES = 1 * MIB
MAX_FILE_BYTES = 2 * MIB
MAX_TOTAL_BYTES = 64 * MIB
MAX_PACKS = 64
MAX_SECONDS = 5
SAMPLE_RATES = (44100, 48000)
BIT_DEPTHS = (16, 24)
CHANNELS = (1, 2)
PEAK_LIMIT_DBFS = -1.0

REPO_ID = re.compile(r'[a-z0-9]+([.-][a-z0-9]+)*')
PACK_ID = re.compile(r'[a-z0-9]+(-[a-z0-9]+)*')
LICENSE = re.compile(r'LicenseRef-[A-Za-z0-9.-]+|(?!LicenseRef-)[A-Za-z0-9][A-Za-z0-9.+-]*')
SHA256 = re.compile(r'[0-9a-f]{64}')
PATH_CHARS = re.compile(r'[A-Za-z0-9._/-]+')
# BCP 47 language[-script][-region][-variant...]; extensions and private use are not needed for display text.
LANGUAGE_TAG = re.compile(r'[A-Za-z]{2,3}(-[A-Za-z]{4})?(-([A-Za-z]{2}|[0-9]{3}))?(-([A-Za-z0-9]{5,8}|[0-9][A-Za-z0-9]{3}))*')

TOP_FIELDS = {'schemaVersion', 'id', 'name', 'description', 'localizations', 'author', 'homepage', 'packs'}
PACK_FIELDS = {'id', 'name', 'description', 'localizations', 'version', 'license', 'author', 'sounds'}
LOCALIZATION_FIELDS = {'name', 'description'}
AUTHOR_FIELDS = {'name', 'email', 'url'}
SOUND_FIELDS = {'file', 'sha256', 'size'}
PCM_GUID_TAIL = bytes.fromhex('000000001000800000aa00389b71')

TEMPLATE = {
    'schemaVersion': SCHEMA_VERSION,
    'id': 'com.example.sounds',
    'name': 'My sounds',
    'description': '',
    'author': {'name': 'Your name'},
}


class Report:
    """Collects errors and warnings. Each issue carries a rule id so messages are greppable."""

    def __init__(self):
        self.errors = []
        self.warnings = []
        self._unknown = {}

    def error(self, where, rule, message):
        self.errors.append((where, rule, message))

    def warn(self, where, rule, message):
        self.warnings.append((where, rule, message))

    def unknown(self, kind, name, where):
        # Aggregated so that one extra field in 29 packs is one line, not 29.
        self._unknown.setdefault((kind, name), []).append(where)

    def rules(self):
        return {rule for _, rule, _ in self.errors}

    def flush_unknown(self):
        for (kind, name), places in sorted(self._unknown.items()):
            rule = 'unknown-event' if kind == 'event' else 'unknown-field'
            where = places[0] if len(places) == 1 else f'{places[0]} (+{len(places) - 1} more)'
            self.warn(where, rule, f'unknown {kind} "{name}" is ignored by this version of Luan')
        self._unknown = {}

    def print(self, out=None):
        out = out or sys.stdout
        for label, items in (('error', self.errors), ('warning', self.warnings)):
            for where, rule, message in items:
                print(f'{label}: {where}: {message} [{rule}]', file=out)


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def has_control(text):
    return any(ord(c) < 32 or 127 <= ord(c) < 160 for c in text)


def is_https_url(value):
    if not isinstance(value, str) or any(c.isspace() for c in value):
        return False
    parts = urlsplit(value)
    return parts.scheme == 'https' and bool(parts.hostname)


def load_json(path, report, where):
    def no_duplicates(pairs):
        keys = [k for k, _ in pairs]
        for key in {k for k in keys if keys.count(k) > 1}:
            report.error(where, 'json', f'duplicate key "{key}"')
        return dict(pairs)

    def no_constant(name):
        raise ValueError(f'{name} is not valid JSON')

    try:
        return json.loads(path.read_bytes().decode('utf-8'), object_pairs_hook=no_duplicates,
                          parse_constant=no_constant)
    except (UnicodeDecodeError, ValueError) as exc:
        report.error(where, 'json', f'not valid UTF-8 JSON: {exc}')
        return None


def sha256_of(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------- WAV

def read_wav(data):
    """Return (fmt, frames, peak_ratio) for linear PCM WAV bytes, or raise ValueError."""
    if len(data) < 12 or data[0:4] != b'RIFF' or data[8:12] != b'WAVE':
        raise ValueError('not a RIFF/WAVE file')
    fmt = None
    pcm = None
    offset = 12
    while offset + 8 <= len(data):
        chunk = data[offset:offset + 4]
        size = int.from_bytes(data[offset + 4:offset + 8], 'little')
        body = offset + 8
        if body + size > len(data):
            raise ValueError(f'chunk "{chunk.decode("latin-1")}" runs past the end of the file')
        if chunk == b'fmt ':
            fmt = parse_fmt(data[body:body + size])
        elif chunk == b'data' and pcm is None:
            pcm = data[body:body + size]
        offset = body + size + (size & 1)
    if fmt is None:
        raise ValueError('missing fmt chunk')
    if pcm is None:
        raise ValueError('missing data chunk')
    if len(pcm) % fmt['blockAlign']:
        raise ValueError('data chunk is not a whole number of frames')
    return fmt, len(pcm) // fmt['blockAlign'], peak_ratio(pcm, fmt['bits'])


def parse_fmt(body):
    if len(body) < 16:
        raise ValueError('fmt chunk is too short')
    tag = int.from_bytes(body[0:2], 'little')
    fmt = {
        'channels': int.from_bytes(body[2:4], 'little'),
        'rate': int.from_bytes(body[4:8], 'little'),
        'byteRate': int.from_bytes(body[8:12], 'little'),
        'blockAlign': int.from_bytes(body[12:14], 'little'),
        'bits': int.from_bytes(body[14:16], 'little'),
    }
    if tag == 0xFFFE:
        if len(body) < 40 or body[26:40] != PCM_GUID_TAIL:
            raise ValueError('WAVE_FORMAT_EXTENSIBLE without a standard subformat')
        tag = int.from_bytes(body[24:26], 'little')
        if tag == 1 and int.from_bytes(body[18:20], 'little') != fmt['bits']:
            raise ValueError('valid bits differ from container bits; use plain 16- or 24-bit PCM')
    if tag != 1:
        raise ValueError(f'audio format {tag:#x} is not linear integer PCM')
    if fmt['bits'] not in BIT_DEPTHS:
        raise ValueError(f'{fmt["bits"]}-bit samples; must be 16 or 24')
    if fmt['channels'] == 0 or fmt['blockAlign'] != fmt['channels'] * fmt['bits'] // 8:
        raise ValueError('inconsistent fmt chunk (blockAlign)')
    if fmt['byteRate'] != fmt['rate'] * fmt['blockAlign']:
        raise ValueError('inconsistent fmt chunk (byteRate)')
    return fmt


def peak_ratio(pcm, bits):
    if not pcm:
        return 0.0
    if bits == 16:
        samples = array.array('h', pcm)
        scale = 32768
    else:
        widened = bytearray(len(pcm) // 3 * 4)
        widened[1::4], widened[2::4], widened[3::4] = pcm[0::3], pcm[1::3], pcm[2::3]
        samples = array.array('i', bytes(widened))
        scale = 2 ** 31
    if sys.byteorder == 'big':
        samples.byteswap()
    return max(-min(samples), max(samples)) / scale


# ---------------------------------------------------------------- build

def generate_packs(root, report):
    """Scan packs/*/pack.json and their <event>.wav files into a packs array."""
    packs = []
    folder = root / 'packs'
    if not folder.is_dir():
        report.error('packs/', 'build', 'missing packs/ directory')
        return packs
    for directory in sorted(p for p in folder.iterdir() if p.is_dir()):
        where = f'packs/{directory.name}/{PACK_FILE}'
        if not (directory / PACK_FILE).is_file():
            report.error(where, 'build', 'missing pack.json')
            continue
        meta = load_json(directory / PACK_FILE, report, where)
        if not isinstance(meta, dict):
            if meta is not None:
                report.error(where, 'build', 'pack.json must be a JSON object')
            continue
        if meta.get('id', directory.name) != directory.name:
            report.error(where, 'build', f'"id" must equal the folder name "{directory.name}"')
        if 'sounds' in meta:
            report.warn(where, 'build', '"sounds" is generated from the audio files; the value here is ignored')
        pack = {'id': directory.name}
        pack.update((k, v) for k, v in meta.items() if k not in ('id', 'sounds'))
        pack['sounds'] = {}
        for event in EVENTS:
            path = directory / f'{event}.wav'
            if path.is_file():
                pack['sounds'][event] = {
                    'file': path.relative_to(root).as_posix(),
                    'sha256': sha256_of(path),
                    'size': path.stat().st_size,
                }
        for extra in sorted(directory.iterdir()):
            if extra.name != PACK_FILE and extra.suffix == '.wav' and extra.stem not in EVENTS:
                report.warn(f'packs/{directory.name}/{extra.name}', 'build',
                            'file name is not a known event; not added to luan.json')
        packs.append(pack)
    return packs


def pack_content(pack):
    return json.dumps({k: v for k, v in pack.items() if k != 'version'}, sort_keys=True)


def compare_versions(old, new, report):
    """Enforce the update rules: any change to a pack requires a larger version."""
    if not isinstance(old, dict) or not isinstance(new, dict):
        return
    if old.get('id') != new.get('id'):
        report.error(MANIFEST, 'repo-id-changed',
                     f'repository id changed from "{old.get("id")}" to "{new.get("id")}"; it must stay the same')
    before = {p.get('id'): p for p in old.get('packs') or [] if isinstance(p, dict)}
    for pack in new.get('packs') or []:
        if not isinstance(pack, dict) or pack.get('id') not in before:
            continue
        previous = before[pack['id']]
        old_version, version = previous.get('version'), pack.get('version')
        if not (is_int(old_version) and is_int(version)):
            continue
        where = f'packs[id={pack["id"]}].version'
        if version < old_version:
            report.error(where, 'version-bump', f'version went down from {old_version} to {version}')
        elif version == old_version and pack_content(pack) != pack_content(previous):
            report.error(where, 'version-bump',
                         f'pack content changed but version is still {version}; increase it')


def write_json(path, document):
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def build(root, skip_version_check=False):
    report = Report()
    manifest_path = root / MANIFEST
    if manifest_path.exists():
        current = load_json(manifest_path, report, MANIFEST)
        if not isinstance(current, dict):
            if current is not None:
                report.error(MANIFEST, 'json', 'top level must be a JSON object')
            return report
    else:
        current = None
        report.warn(MANIFEST, 'build', 'created from a template; edit id, name and author')
    packs = generate_packs(root, report)
    document = {k: v for k, v in (current or TEMPLATE).items() if k != 'packs'}
    document['packs'] = packs
    if current is not None and not skip_version_check:
        compare_versions(current, document, report)
    if report.errors:
        return report
    write_json(manifest_path, document)
    result = check(root)
    result.warnings[:0] = report.warnings
    return result


# ---------------------------------------------------------------- check

def check_text(value, where, rule, report, minimum, maximum, control=False):
    if not isinstance(value, str):
        report.error(where, rule, 'must be a string')
    elif not minimum <= len(value) <= maximum:
        report.error(where, rule, f'length {len(value)} is outside {minimum}-{maximum} characters')
    elif control and has_control(value):
        report.error(where, rule, 'must not contain control characters')


def check_name_and_description(entry, prefix, report, name_required):
    if name_required or 'name' in entry:
        check_text(entry.get('name'), f'{prefix}name', 'name', report, 1, 64, control=True)
    if 'description' in entry:
        check_text(entry['description'], f'{prefix}description', 'description', report, 0, 280)


def check_display_text(owner, prefix, report):
    """name, description and their localizations, shared by the repository and every pack."""
    check_name_and_description(owner, prefix, report, name_required=True)
    if 'localizations' not in owner:
        return
    where = f'{prefix}localizations'
    localizations = owner['localizations']
    if not isinstance(localizations, dict):
        report.error(where, 'localizations', 'must be an object keyed by BCP 47 language tag')
        return
    seen = {}
    for tag, entry in localizations.items():
        place = f'{where}.{tag}'
        if not LANGUAGE_TAG.fullmatch(tag):
            report.error(place, 'localizations', f'"{tag}" is not a BCP 47 language tag such as "zh-Hans" or "ja"')
        elif tag.lower() in seen:
            report.error(place, 'localizations', f'same language as "{seen[tag.lower()]}" (tags ignore case)')
        seen.setdefault(tag.lower(), tag)
        if not isinstance(entry, dict):
            report.error(place, 'localizations', 'must be an object with optional name and description')
            continue
        check_name_and_description(entry, f'{place}.', report, name_required=False)
        for key in entry.keys() - LOCALIZATION_FIELDS:
            report.unknown('field', key, f'{place}.{key}')


def check_author(author, where, report):
    if not isinstance(author, dict):
        report.error(where, 'author', 'must be an object with "name"')
        return
    if not isinstance(author.get('name'), str) or not author['name'].strip():
        report.error(f'{where}.name', 'author', 'required non-empty string')
    if 'email' in author and not isinstance(author['email'], str):
        report.error(f'{where}.email', 'author', 'must be a string')
    if 'url' in author and not is_https_url(author['url']):
        report.error(f'{where}.url', 'author', 'must be an https:// URL')
    for key in author.keys() - AUTHOR_FIELDS:
        report.unknown('field', key, f'{where}.{key}')


def check_file_path(value, where, report):
    if not isinstance(value, str):
        report.error(where, 'file-path', 'must be a string')
        return False
    problems = []
    if not value or len(value) > 255:
        problems.append('must be 1-255 characters')
    if not PATH_CHARS.fullmatch(value):
        problems.append('may only contain A-Z a-z 0-9 . _ - and /')
    if any(segment in ('', '.', '..') for segment in value.split('/')):
        problems.append('must be relative with no empty, "." or ".." segments')
    if not value.endswith('.wav'):
        problems.append('must end in .wav')
    for problem in problems:
        report.error(where, 'file-path', f'"{value}" {problem}')
    return not problems


def exact_case_file(root, relative):
    """True if every path segment exists with exactly this spelling (GitHub raw is case-sensitive)."""
    current = root
    for segment in relative.split('/'):
        if not current.is_dir() or segment not in {p.name for p in current.iterdir()}:
            return False
        current = current / segment
    return current.is_file()


def check_audio(root, relative, where, report, cache):
    """Check one referenced file. Returns (sha256, size) of what is on disk, or None."""
    if relative in cache:
        return cache[relative]
    cache[relative] = None
    path = root / relative
    if not exact_case_file(root, relative):
        report.error(where, 'file-missing', f'{relative} does not exist (paths are case-sensitive)')
        return None
    if path.resolve() != root.resolve() / relative:
        report.error(where, 'file-path', f'{relative} is or passes through a symlink; hosts serve symlinks as text')
        return None
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        report.error(relative, 'file-size', f'{size} bytes exceeds the 2 MiB limit')
        return None
    data = path.read_bytes()
    try:
        fmt, frames, peak = read_wav(data)
    except ValueError as exc:
        report.error(relative, 'wav-format', str(exc))
    else:
        if fmt['rate'] not in SAMPLE_RATES:
            report.error(relative, 'sample-rate', f'{fmt["rate"]} Hz; must be 44100 or 48000')
        if fmt['channels'] not in CHANNELS:
            report.error(relative, 'channels', f'{fmt["channels"]} channels; must be 1 or 2')
        if frames == 0 or frames > MAX_SECONDS * fmt['rate']:
            report.error(relative, 'duration',
                         f'{frames / fmt["rate"]:.3f} s; must be longer than 0 and at most {MAX_SECONDS} s')
        if peak > 10 ** (PEAK_LIMIT_DBFS / 20):
            report.warn(relative, 'loudness',
                        f'peak {20 * math.log10(peak):.2f} dBFS is above the recommended {PEAK_LIMIT_DBFS:g} dBFS')
    cache[relative] = (hashlib.sha256(data).hexdigest(), size)
    return cache[relative]


def check_sound(root, sound, where, report, cache, unique):
    if not isinstance(sound, dict):
        report.error(where, 'sounds', 'must be an object with file, sha256 and size')
        return
    for key in sound.keys() - SOUND_FIELDS:
        report.unknown('field', key, f'{where}.{key}')
    path_ok = check_file_path(sound.get('file'), f'{where}.file', report)
    digest, size = sound.get('sha256'), sound.get('size')
    if not isinstance(digest, str) or not SHA256.fullmatch(digest):
        report.error(f'{where}.sha256', 'sha256', 'must be 64 lowercase hexadecimal characters')
        digest = None
    if not is_int(size) or size < 0:
        report.error(f'{where}.size', 'size', 'must be a non-negative integer')
        size = None
    elif size > MAX_FILE_BYTES:
        report.error(f'{where}.size', 'file-size', f'{size} bytes exceeds the 2 MiB limit')
    if digest is not None and size is not None:
        unique[digest] = size
    if not path_ok:
        return
    actual = check_audio(root, sound['file'], f'{where}.file', report, cache)
    if actual is None:
        return
    if digest is not None and actual[0] != digest:
        report.error(f'{where}.sha256', 'sha256', f'does not match {sound["file"]} (actual {actual[0]})')
    if size is not None and actual[1] != size:
        report.error(f'{where}.size', 'size', f'{size} does not match {sound["file"]} ({actual[1]} bytes)')


def check_pack(root, pack, where, report, cache, unique):
    if not isinstance(pack, dict):
        report.error(where, 'packs', 'must be an object')
        return
    pack_id = pack.get('id')
    if not isinstance(pack_id, str) or not 1 <= len(pack_id) <= 64 or not PACK_ID.fullmatch(pack_id):
        report.error(f'{where}.id', 'pack-id', 'must be 1-64 characters matching ^[a-z0-9]+(-[a-z0-9]+)*$')
    check_display_text(pack, f'{where}.', report)
    version = pack.get('version')
    if not is_int(version) or version < 1:
        report.error(f'{where}.version', 'pack-version', 'required integer >= 1')
    if 'license' in pack and not (isinstance(pack['license'], str) and LICENSE.fullmatch(pack['license'])):
        report.error(f'{where}.license', 'license', 'must be an SPDX identifier or LicenseRef-...')
    if 'author' in pack:
        check_author(pack['author'], f'{where}.author', report)
    for key in pack.keys() - PACK_FIELDS:
        report.unknown('field', key, f'{where}.{key}')
    sounds = pack.get('sounds')
    if not isinstance(sounds, dict):
        report.error(f'{where}.sounds', 'sounds', 'required object keyed by event')
        return
    for event, sound in sounds.items():
        if event in EVENTS:
            check_sound(root, sound, f'{where}.sounds.{event}', report, cache, unique)
        else:
            report.unknown('event', event, f'{where}.sounds.{event}')
    if not any(event in EVENTS for event in sounds):
        report.error(f'{where}.sounds', 'sounds', 'must contain at least one known event')


def check_manifest(root, manifest, report):
    if not isinstance(manifest, dict):
        report.error(MANIFEST, 'json', 'top level must be a JSON object')
        return
    version = manifest.get('schemaVersion')
    if not is_int(version) or version != SCHEMA_VERSION:
        hint = '; this tool is too old, update it' if is_int(version) and version > SCHEMA_VERSION else ''
        report.error('schemaVersion', 'schema-version', f'must be the integer {SCHEMA_VERSION}{hint}')
        return
    repo_id = manifest.get('id')
    if not isinstance(repo_id, str) or not 1 <= len(repo_id) <= 128 or not REPO_ID.fullmatch(repo_id):
        report.error('id', 'repo-id', 'must be 1-128 characters matching ^[a-z0-9]+([.-][a-z0-9]+)*$')
    elif repo_id == 'builtin':
        report.error('id', 'repo-id', '"builtin" is reserved')
    check_display_text(manifest, '', report)
    if 'author' in manifest:
        check_author(manifest['author'], 'author', report)
    if 'homepage' in manifest and not is_https_url(manifest['homepage']):
        report.error('homepage', 'homepage', 'must be an https:// URL')
    for key in manifest.keys() - TOP_FIELDS:
        report.unknown('field', key, key)
    packs = manifest.get('packs')
    if not isinstance(packs, list) or not 1 <= len(packs) <= MAX_PACKS:
        report.error('packs', 'packs', f'must be an array of 1-{MAX_PACKS} packs')
        return
    ids = [p.get('id') for p in packs if isinstance(p, dict)]
    for duplicate in sorted({i for i in ids if ids.count(i) > 1 and isinstance(i, str)}):
        report.error('packs', 'pack-id', f'duplicate pack id "{duplicate}"')
    cache, unique = {}, {}
    for index, pack in enumerate(packs):
        check_pack(root, pack, f'packs[{index}]', report, cache, unique)
    total = sum(unique.values())
    if total > MAX_TOTAL_BYTES:
        report.error('packs', 'total-size', f'{total} bytes after de-duplication exceeds the 64 MiB limit')
    report.summary = (len(packs), len(cache), total)


def check(root, previous=None):
    report = Report()
    report.summary = None
    path = root / MANIFEST
    if not path.is_file():
        report.error(MANIFEST, 'json', 'missing luan.json')
        return report
    size = path.stat().st_size
    if size > MAX_MANIFEST_BYTES:
        report.error(MANIFEST, 'manifest-size', f'{size} bytes exceeds the 1 MiB limit')
        return report
    manifest = load_json(path, report, MANIFEST)
    if manifest is None:
        return report
    check_manifest(root, manifest, report)
    if isinstance(manifest, dict) and (root / 'packs').is_dir() and any((root / 'packs').glob(f'*/{PACK_FILE}')):
        scratch = Report()
        if generate_packs(root, scratch) != manifest.get('packs'):
            report.error(MANIFEST, 'stale-manifest',
                         'packs array differs from packs/*/pack.json and audio files; run "luan_repo.py build"')
        report.errors.extend(scratch.errors)
    if previous is not None:
        old = load_json(previous, report, str(previous))
        compare_versions(old, manifest, report)
    report.flush_unknown()
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    build_parser = commands.add_parser('build', help='regenerate the packs array of luan.json, then check')
    build_parser.add_argument('root', type=Path)
    build_parser.add_argument('--skip-version-check', action='store_true',
                              help='allow changed packs to keep their version (only for never-published luan.json)')
    check_parser = commands.add_parser('check', help='validate luan.json and all referenced audio files')
    check_parser.add_argument('root', type=Path)
    check_parser.add_argument('--previous', type=Path, metavar='OLD_LUAN_JSON',
                              help='also require version bumps relative to a previously published luan.json')
    args = parser.parse_args(argv)
    if args.command == 'build':
        report = build(args.root, args.skip_version_check)
    else:
        report = check(args.root, args.previous)
    report.print()
    if report.errors:
        print(f'FAILED: {len(report.errors)} error(s), {len(report.warnings)} warning(s)')
        return 1
    summary = getattr(report, 'summary', None)
    if summary:
        packs, files, total = summary
        print(f'OK: {packs} packs, {files} files, {total / MIB:.2f} MiB after de-duplication, '
              f'{len(report.warnings)} warning(s)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
