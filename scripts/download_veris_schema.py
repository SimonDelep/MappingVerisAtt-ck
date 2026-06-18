"""Download VERIS schema and enumeration data used for ATT&CK mappings."""

from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass

from paths import VERIS_DIR, VERIS_ENUM_DIR, VERIS_GIT_REFS, VERIS_VERSIONS, veris_schema_dir

VERIS_REPO = "https://raw.githubusercontent.com/vz-risk/veris"
MAPEX_REPO = (
    "https://raw.githubusercontent.com/center-for-threat-informed-defense"
    "/mappings-explorer/main/src/mapex_convert/mappings/Veris"
)

SCHEMA_FILES = ["verisc.json", "verisc-labels.json", "verisc-enum.json"]

ENUMERATION_FILES = [
    (
        "veris135-enumerations.csv",
        f"{MAPEX_REPO}/enumeration/veris135-enumerations.csv",
    ),
    (
        "veris1_3_7-enumerations-groups.csv",
        f"{MAPEX_REPO}/enumeration/veris1_3_7-enumerations-groups.csv",
    ),
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
    print(f"Output directory: {VERIS_DIR}\n")

    for veris_version in VERIS_VERSIONS:
        git_ref = VERIS_GIT_REFS[veris_version]
        dest_dir = veris_schema_dir(veris_version)
        print(f"[VERIS {veris_version} <- git ref {git_ref}]")

        for filename in SCHEMA_FILES:
            dest = dest_dir / filename
            url = f"{VERIS_REPO}/{git_ref}/{filename}"

            if dest.exists() and not force:
                print(f"  skip {filename}")
                result.skipped += 1
                continue

            try:
                download_file(url, dest)
                print(f"  ok   {filename} ({dest.stat().st_size:,} bytes)")
                result.downloaded += 1
            except urllib.error.HTTPError as exc:
                print(f"  fail {filename} (HTTP {exc.code})")
                result.failed += 1

        print()

    print("[CTID enumeration files]")
    for filename, url in ENUMERATION_FILES:
        dest = VERIS_ENUM_DIR / filename
        if dest.exists() and not force:
            print(f"  skip {filename}")
            result.skipped += 1
            continue
        try:
            download_file(url, dest)
            print(f"  ok   {filename} ({dest.stat().st_size:,} bytes)")
            result.downloaded += 1
        except urllib.error.HTTPError as exc:
            print(f"  fail {filename} (HTTP {exc.code})")
            result.failed += 1

    print(
        f"\nDone. downloaded={result.downloaded}, "
        f"skipped={result.skipped}, failed={result.failed}"
    )
    return result


def main() -> None:
    download_all(force=False)


if __name__ == "__main__":
    main()
