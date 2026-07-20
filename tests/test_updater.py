import hashlib
import json
from pathlib import Path

import pytest

from src.updater import (
    ASSET_API_PREFIX,
    EXECUTABLE_ASSET_NAME,
    LATEST_RELEASE_URL,
    ReleaseInfo,
    UpdateError,
    download_release,
    fetch_latest_release,
    is_newer_version,
    parse_release,
)


class FakeResponse:
    def __init__(self, content: bytes):
        self._content = content
        self._offset = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self._content) - self._offset
        chunk = self._content[self._offset:self._offset + size]
        self._offset += len(chunk)
        return chunk


def release_payload(content: bytes = b"MZ-test executable") -> dict:
    return {
        "tag_name": "v2.1.0",
        "name": "Versão 2.1.0",
        "body": "- Melhorias importantes",
        "html_url": "https://github.com/leosgarcia/tunnel-ssh/releases/tag/v2.1.0",
        "assets": [
            {
                "name": EXECUTABLE_ASSET_NAME,
                "url": f"{ASSET_API_PREFIX}123456",
                "size": len(content),
                "digest": f"sha256:{hashlib.sha256(content).hexdigest()}",
            }
        ],
    }


def test_version_comparison():
    assert is_newer_version("2.0.0", "1.2.1")
    assert not is_newer_version("2.0.0", "2.0.0")
    assert not is_newer_version("1.9.9", "2.0.0")


def test_release_requires_official_repository_urls():
    payload = release_payload()
    payload["assets"][0]["url"] = "https://api.github.com/repos/attacker/repo/releases/assets/1"

    with pytest.raises(UpdateError, match="não autorizado"):
        parse_release(payload)


def test_release_allows_extra_assets_but_selects_exact_executable_name():
    payload = release_payload()
    payload["assets"].append(
        {
            "name": "wltech-tunnel-2.1.0.zip",
            "url": f"{ASSET_API_PREFIX}789",
            "size": 123,
            "digest": "sha256:" + "0" * 64,
        }
    )

    release = parse_release(payload)

    assert release.asset_api_url == f"{ASSET_API_PREFIX}123456"


def test_fetch_uses_only_official_latest_release_endpoint():
    payload = json.dumps(release_payload()).encode()
    requested_urls = []

    def opener(request, timeout):
        requested_urls.append(request.full_url)
        return FakeResponse(payload)

    release = fetch_latest_release(opener=opener)

    assert release.version == "2.1.0"
    assert release.notes == "- Melhorias importantes"
    assert requested_urls == [LATEST_RELEASE_URL]


def test_download_validates_size_digest_and_executable_header():
    content = b"MZ-test executable"
    payload = release_payload(content)
    release = parse_release(payload)
    progress = []

    path = download_release(
        release,
        progress=progress.append,
        opener=lambda request, timeout: FakeResponse(content),
    )
    try:
        assert Path(path).read_bytes() == content
        assert progress[-1] == 1.0
    finally:
        Path(path).unlink(missing_ok=True)


def test_download_rejects_changed_file():
    expected = b"MZ-original"
    changed = b"MZ-modified"
    release = ReleaseInfo(
        version="2.1.0",
        title="Versão 2.1.0",
        notes="Notas",
        page_url="https://github.com/leosgarcia/tunnel-ssh/releases/tag/v2.1.0",
        asset_api_url=f"{ASSET_API_PREFIX}123456",
        asset_size=len(changed),
        asset_sha256=hashlib.sha256(expected).hexdigest(),
    )

    with pytest.raises(UpdateError, match="SHA-256"):
        download_release(release, opener=lambda request, timeout: FakeResponse(changed))
