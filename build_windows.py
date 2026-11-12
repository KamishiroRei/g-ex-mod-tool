"""Build the self-contained player distribution; Python is only a build tool."""

from __future__ import annotations

import argparse
import importlib.metadata
import math
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import zipfile


ROOT = Path(__file__).resolve().parent
APP_NAME = "G-EX Mod Tool"
ARCHIVE_NAME = "G-EX-Mod-Tool-Windows-x64.zip"


def executable_icon() -> Path:
    points = ((26, 9), (16, 3), (6, 9), (6, 23), (16, 29), (26, 23), (26, 16), (16, 16))
    def on_mark(x, y):
        for (ax, ay), (bx, by) in zip(points, points[1:]):
            dx, dy = bx - ax, by - ay
            t = max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)))
            if math.hypot(x - ax - t * dx, y - ay - t * dy) <= 1.75:
                return True
        return False
    images = []
    for size in (16, 32, 48, 256):
        pixels = bytearray()
        for row in reversed(range(size)):
            for column in range(size):
                covered = sum(on_mark((column + (sx + .5) / 3) * 32 / size,
                                      (row + (sy + .5) / 3) * 32 / size)
                              for sx in range(3) for sy in range(3))
                pixels.extend((207, 208, 118, round(255 * covered / 9)))
        mask = bytes(((size + 31) // 32) * 4 * size)
        header = struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0, len(pixels), 0, 0, 0, 0)
        images.append((size, header + pixels + mask))
    offset = 6 + 16 * len(images)
    directory = bytearray(struct.pack("<HHH", 0, 1, len(images)))
    for size, payload in images:
        directory.extend(struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(payload), offset))
        offset += len(payload)
    path = ROOT / "build/app-icon.ico"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(directory + b"".join(payload for _, payload in images))
    return path


def runtime_notices(output: Path) -> list[Path]:
    notices = output / "third-party-notices"
    notices.mkdir(parents=True, exist_ok=True)
    candidates = {
        "Python.txt": [Path(sys.base_prefix) / "LICENSE_PYTHON.txt", Path(sys.base_prefix) / "LICENSE.txt"],
    }
    written = []
    for name, paths in candidates.items():
        source = next((path for path in paths if path.is_file()), None)
        if source:
            destination = notices / name
            shutil.copy2(source, destination)
            written.append(destination)
    for distribution_name in ("pyinstaller", "PySide6-Essentials", "shiboken6"):
        distribution = importlib.metadata.distribution(distribution_name)
        for item in distribution.files or ():
            parts = [part.lower() for part in item.parts]
            if ("licenses" in parts or item.name.lower().startswith(("license", "copying"))) and item.suffix.lower() in (".txt", ".md", ".rst", ""):
                source = Path(distribution.locate_file(item))
                if not source.is_file():
                    continue
                suffix = Path(*item.parts[parts.index("licenses") + 1:]) if "licenses" in parts else Path(item.name)
                destination = notices / distribution_name / suffix
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                written.append(destination)
    return written


def author_sources(release: Path) -> None:
    for directory, patterns in {
        "gex_mod_tool": ("*.py", "*.qss"),
        "schema": ("*.json",),
        "examples": ("*.json",),
        "assets": ("*.svg",),
        "design": ("approved-ui.png", "README.md"),
        "packaging": ("*.txt",),
        ".agents/skills": ("*.md", "*.yaml"),
    }.items():
        for pattern in patterns:
            for source in (ROOT / directory).rglob(pattern):
                destination = release / source.relative_to(ROOT)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
    for name in ("AGENTS.md", "README.md", "RELEASE-NOTES.md", "LICENSE", "gex_mod_tool.pyw", "build_windows.py", "requirements-build.txt"):
        shutil.copy2(ROOT / name, release / name)
    shutil.copy2(ROOT / "packaging/使用说明.txt", release / "使用说明.txt")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", type=Path, help="Stage the tool in this game's modtool directory")
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--content-only", action="store_true", help="Refresh author sources and packaging around the existing runtime build")
    args = parser.parse_args()
    if sys.platform != "win32" or struct.calcsize("P") != 8:
        parser.error("Build this Windows x64 release with 64-bit Python on Windows.")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--onedir", "--windowed", "--noupx",
        "--name", APP_NAME, "--icon", str(executable_icon()),
        "--exclude-module", "tkinter", "--exclude-module", "PyQt5", "--exclude-module", "PyQt6",
        "--add-data", str(ROOT / "gex_mod_tool/editor.qss") + ";gex_mod_tool",
        "--add-data", str(ROOT / "assets/app-icon.svg") + ";assets",
        "--distpath", str(output), "--workpath", str(ROOT / "build/pyinstaller"),
        "--specpath", str(ROOT / "build/spec"), str(ROOT / "gex_mod_tool.pyw"),
    ]
    if not args.content_only:
        subprocess.run(command, cwd=ROOT, check=True)
    release = output / APP_NAME
    executable = release / (APP_NAME + ".exe")
    runtime_notices(release)
    author_sources(release)
    archive = output / ARCHIVE_NAME
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as package:
        for source in release.rglob("*"):
            if source.is_file():
                package.write(source, source.relative_to(release))
    if args.game_root:
        game = args.game_root.expanduser().resolve()
        if not (game / "ExtentData/Parts").is_dir() and (game / "ExceedCavalier/ExtentData/Parts").is_dir():
            game /= "ExceedCavalier"
        if not (game / "ExtentData/Parts").is_dir():
            parser.error("--game-root must contain the game's ExtentData/Parts directory.")
        destination = game / "modtool"
        destination.mkdir(parents=True, exist_ok=True)
        for source in release.rglob("*"):
            if source.is_file():
                relative = source.relative_to(release)
                # The source module already owns these author files in an
                # in-project build; only copy runtime outputs into that root.
                target = destination / relative
                runtime_file = relative.parts[0] in ("_internal", "third-party-notices") or relative.name in (APP_NAME + ".exe", "使用说明.txt")
                if destination == ROOT and not runtime_file:
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        print("Staged game tool:", destination / executable.name)
    print("Windows executable:", executable)
    print("Distribution archive:", archive)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
