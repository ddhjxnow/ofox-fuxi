#!/usr/bin/env python3
"""Normalize a known optional-check return status in OrangeFox's envsetup hook.

OrangeFox/sync's patch-manifest-fox_12.1.diff ends orangefox_envsetup with
`[ -s optional_file ] && empty_file`. When the file is absent/already empty,
that returns 1 even though initialization succeeded. An equivalent `if` block
returns 0 when the optional action is unnecessary, while retaining a real
write failure. Do not mask source/lunch/build errors in the workflow.
"""
from pathlib import Path
import argparse


OPTIONAL_FILE = "frameworks/base/services/core/xsd/vts/Android.mk"
LEGACY_CHECK = (
    f"[ -s $FOX_MANIFEST_ROOT/{OPTIONAL_FILE} ]"
    f' && echo -n "" > $FOX_MANIFEST_ROOT/{OPTIONAL_FILE}'
)
SAFE_CHECK = (
    f'if [ -s "$FOX_MANIFEST_ROOT/{OPTIONAL_FILE}" ]; then '
    f'echo -n "" > "$FOX_MANIFEST_ROOT/{OPTIONAL_FILE}"; fi'
)


def normalize_envsetup(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    count = text.count(LEGACY_CHECK)
    if count == 0:
        return False
    if count != 1:
        raise ValueError("Multiple legacy optional checks found; refusing ambiguous edit")
    path.write_text(text.replace(LEGACY_CHECK, SAFE_CHECK), encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("envsetup", type=Path, help="build/envsetup.sh (symlink allowed)")
    args = parser.parse_args()
    try:
        changed = normalize_envsetup(args.envsetup)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    if changed:
        print("envsetup: normalized known optional XSD check; real failures remain fatal")
    else:
        print("envsetup: legacy optional check absent or already normalized; no change")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
