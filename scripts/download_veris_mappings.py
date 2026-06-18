"""Download VERIS <-> ATT&CK enterprise mapping versions from Mappings Explorer."""

from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass

from paths import MAPPING_DIR, MAPPING_SETS, mapping_set_dir

BASE_URL = (
    "https://center-for-threat-informed-defense.github.io/mappings-explorer/data/veris"
)

FILE_SUFFIXES = [
    ".csv",
    "_json.json",
    ".yaml",
    "_stix.json",
    "_navigator_layer.json",
    ".xlsx",
]


@dataclass
class DownloadResult:
    downloaded: int = 0
    skipped: int = 0
    failed: int = 0


def download_file(url: str, dest) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as response:
        dest.write_bytes(response.read())


def download_all(force: bool = False) -> DownloadResult:
    result = DownloadResult()
    print(f"Output directory: {MAPPING_DIR}\n")

    for attack_version, veris_version, stem in MAPPING_SETS:
        dest_dir = mapping_set_dir(attack_version, veris_version)
        attack = f"attack-{attack_version}"
        veris = f"veris-{veris_version}"
        domain = "enterprise"
        print(f"[VERIS {veris_version} / ATT&CK {attack_version} / {domain}]")

        for suffix in FILE_SUFFIXES:
            filename = f"{stem}{suffix}"
            dest = dest_dir / filename
            url = f"{BASE_URL}/{attack}/{veris}/{domain}/{filename}"

            if dest.exists() and not force:
                print(f"  skip {filename} (already exists)")
                result.skipped += 1
                continue

            try:
                download_file(url, dest)
                print(f"  ok   {filename} ({dest.stat().st_size:,} bytes)")
                result.downloaded += 1
            except urllib.error.HTTPError as exc:
                print(f"  fail {filename} (HTTP {exc.code})")
                result.failed += 1
            except urllib.error.URLError as exc:
                print(f"  fail {filename} ({exc.reason})")
                result.failed += 1

        print()

    print(
        f"Done. downloaded={result.downloaded}, "
        f"skipped={result.skipped}, failed={result.failed}"
    )
    return result


def main() -> None:
    download_all(force=False)


if __name__ == "__main__":
    main()
