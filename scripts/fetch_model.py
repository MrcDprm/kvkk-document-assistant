"""Download the trained name model at image build time and verify it before use.

    python scripts/fetch_model.py <url> <sha256> <target dir>

The model is too large for the git repository, so it is attached to a GitHub Release.
The SHA-256 check makes the build fail if the file was changed or corrupted on the way.
"""

import hashlib
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

EXPECTED_FILES = {"model.onnx", "tokenizer.json", "labels.json", "preprocess.json", "metrics.json"}
MAX_BYTES = 200 * 1024 * 1024


def fetch(url: str, sha256: str, target: Path) -> None:
    with urllib.request.urlopen(url, timeout=120) as response:
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise SystemExit("model archive is larger than expected")

    digest = hashlib.sha256(data).hexdigest()
    if digest != sha256.lower():
        raise SystemExit(f"SHA-256 mismatch: expected {sha256}, got {digest}")

    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = set(archive.namelist())
        if names != EXPECTED_FILES:  # also rules out paths like ../../etc
            raise SystemExit(f"unexpected files in model archive: {sorted(names ^ EXPECTED_FILES)}")
        target.mkdir(parents=True, exist_ok=True)
        archive.extractall(target)
    print(f"model ready in {target} ({len(data) / 1e6:.1f} MB, sha256 ok)")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    fetch(sys.argv[1], sys.argv[2], Path(sys.argv[3]))
