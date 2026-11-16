# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Assemble the GitHub Pages site for the browser converter.

    uv run scripts/build_site.py            # writes _site/
    python -m http.server -d _site 8000     # try it at http://localhost:8000

The site is web/ plus two things the page loads at runtime, both served from
the site itself so nothing comes from a third party:

* pyodide/  the Pyodide runtime (Python compiled to WebAssembly), pinned by
            version and SHA-256 below.
* wheels/   this project's wheel and its runtime dependencies, pinned by the
            versions and SHA-256 hashes in uv.lock.

Downloads are cached in .site-cache/ and every file is hash-checked, cached or not.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
LOCK_FILE = ROOT / "uv.lock"
CACHE_DIR = ROOT / ".site-cache"
PROJECT_NAME = "water-report"

# To upgrade Pyodide: change the version, run the script once, and paste the
# new hash from the error message after checking it against the release page.
PYODIDE_VERSION = "314.0.8"
PYODIDE_SHA256 = "ff3e5f9d9bc8e98ff30b99515535fc24d375994f47a978c61975d653e162ca37"
PYODIDE_URL = (
    "https://github.com/pyodide/pyodide/releases/download/"
    f"{PYODIDE_VERSION}/pyodide-core-{PYODIDE_VERSION}.tar.bz2"
)
# Only what the page needs from the core bundle (no CLI or type stubs).
PYODIDE_FILES = (
    "pyodide.mjs",
    "pyodide.asm.mjs",
    "pyodide.asm.wasm",
    "python_stdlib.zip",
    "pyodide-lock.json",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=ROOT / "_site", help="output folder")
    args = parser.parse_args()

    out: Path = args.out.resolve()
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(WEB_DIR, out)

    install_pyodide(out / "pyodide")
    wheels = install_wheels(out / "wheels")
    (out / ".nojekyll").touch()  # serve files as-is; don't run Jekyll

    print(f"Built {out} with Pyodide {PYODIDE_VERSION} and {', '.join(wheels)}")
    return 0


def install_pyodide(destination: Path) -> None:
    archive = download(PYODIDE_URL, PYODIDE_SHA256)
    destination.mkdir(parents=True)
    with tarfile.open(archive) as tar:
        for name in PYODIDE_FILES:
            member = tar.getmember(f"pyodide/{name}")
            source = tar.extractfile(member)
            if source is None:
                raise RuntimeError(f"{name} is missing from {archive.name}")
            (destination / name).write_bytes(source.read())


def install_wheels(destination: Path) -> list[str]:
    """Copy the project wheel and its locked runtime dependencies into place."""
    destination.mkdir(parents=True)
    names = []

    for url, sha256 in locked_runtime_wheels():
        wheel = download(url, sha256)
        shutil.copy(wheel, destination / wheel.name)
        names.append(wheel.name)

    project_wheel = build_project_wheel(destination)
    names.append(project_wheel.name)

    (destination / "manifest.json").write_text(json.dumps(names, indent=2) + "\n")
    return names


def locked_runtime_wheels() -> list[tuple[str, str]]:
    """(url, sha256) of a pure-Python wheel for each runtime dependency in uv.lock."""
    packages = {p["name"]: p for p in tomllib.loads(LOCK_FILE.read_text())["package"]}

    needed: list[str] = []
    pending = [dep["name"] for dep in packages[PROJECT_NAME].get("dependencies", [])]
    while pending:
        name = pending.pop()
        if name not in needed:
            needed.append(name)
            pending.extend(dep["name"] for dep in packages[name].get("dependencies", []))

    wheels = []
    for name in sorted(needed):
        pure = [w for w in packages[name].get("wheels", []) if w["url"].endswith("-none-any.whl")]
        if not pure:
            raise RuntimeError(
                f"{name} has no pure-Python wheel in uv.lock; Pyodide can't load it from here."
            )
        wheel = pure[0]
        wheels.append((wheel["url"], wheel["hash"].removeprefix("sha256:")))
    return wheels


def build_project_wheel(destination: Path) -> Path:
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            ["uv", "build", "--wheel", "--out-dir", tmp, str(ROOT)],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        (built,) = Path(tmp).glob("*.whl")
        return Path(shutil.copy(built, destination / built.name))


def download(url: str, sha256: str) -> Path:
    """Fetch ``url`` into the cache (once) and verify its SHA-256."""
    CACHE_DIR.mkdir(exist_ok=True)
    path = CACHE_DIR / url.rsplit("/", 1)[-1]
    if not path.exists():
        print(f"Downloading {url}", file=sys.stderr)
        with urllib.request.urlopen(url) as response, open(path, "wb") as file:
            shutil.copyfileobj(response, file)

    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != sha256:
        path.unlink()
        raise RuntimeError(f"Hash mismatch for {url}\n  expected {sha256}\n  got      {actual}")
    return path


if __name__ == "__main__":
    sys.exit(main())
