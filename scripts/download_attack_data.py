"""Download MITRE ATT&CK Enterprise STIX bundles used for VERIS mappings."""

from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass

from paths import ATTACK_DIR, ATTACK_GIT_TAGS, ATTACK_VERSIONS, attack_bundle_path

CTI_BASE = "https://raw.githubusercontent.com/mitre/cti"


@dataclass
class DownloadResult:
    downloaded: int = 0
    skipped: int = 0
    failed: int = 0


def download_file(url: str, dest) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=180) as response:
        dest.write_bytes(response.read())


def attack_bundle_url(git_tag: str) -> str:
    encoded_tag = git_tag.replace("&", "%26")
    return f"{CTI_BASE}/{encoded_tag}/enterprise-attack/enterprise-attack.json"


def download_all(force: bool = False) -> DownloadResult:
    result = DownloadResult()
    print(f"Output directory: {ATTACK_DIR}\n")

    for version in ATTACK_VERSIONS:
        git_tag = ATTACK_GIT_TAGS[version]
        dest = attack_bundle_path(version)
        url = attack_bundle_url(git_tag)
        print(f"[ATT&CK {version} <- {git_tag}]")

        if dest.exists() and not force:
            print("  skip enterprise-attack.json")
            result.skipped += 1
            continue

        try:
            download_file(url, dest)
            print(f"  ok   enterprise-attack.json ({dest.stat().st_size:,} bytes)")
            result.downloaded += 1
        except urllib.error.HTTPError as exc:
            print(f"  fail enterprise-attack.json (HTTP {exc.code})")
            result.failed += 1
        except urllib.error.URLError as exc:
            print(f"  fail enterprise-attack.json ({exc.reason})")
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
