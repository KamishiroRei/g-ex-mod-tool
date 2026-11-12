"""Build the self-contained player distribution; Python is only a build tool."""

from __future__ import annotations

import argparse
import importlib.metadata
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
    from gex_mod_tool.theme import ACCENT, BACKGROUND, ICON_RECTS, SURFACE
    images = []
    for size in (16, 32, 48, 256):
        pixels = bytearray()
        for row in reversed(range(size)):
            y = row * 32 // size
            for column in range(size):
                x = column * 32 // size
                color = BACKGROUND
                if 1 <= x < 31 and 1 <= y < 31:
                    color = "#284455"
                if 2 <= x < 30 and 2 <= y < 30:
                    color = SURFACE
                if any(left <= x < right and top <= y < bottom for left, top, right, bottom in ICON_RECTS):
                    color = ACCENT
                red, green, blue = bytes.fromhex(color[1:])
                pixels.extend((blue, green, red, 255))
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
        "Tcl.txt": [Path(sys.base_prefix) / "tcl/tcl8.6/license.terms", Path(sys.base_prefix) / "Library/lib/tcl8.6/license.terms"],
        "Tk.txt": [Path(sys.base_prefix) / "tcl/tk8.6/license.terms", Path(sys.base_prefix) / "Library/lib/tk8.6/license.terms"],
    }
    distribution = importlib.metadata.distribution("pyinstaller")
    for item in distribution.files or ():
        if item.name == "COPYING.txt":
            candidates["PyInstaller.txt"] = [Path(distribution.locate_file(item))]
            break
    written = []
    for name, paths in candidates.items():
        source = next((path for path in paths if path.is_file()), None)
        if source:
            destination = notices / name
            shutil.copy2(source, destination)
            written.append(destination)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", type=Path, help="Stage the tool in this game's ModTools directory")
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    if sys.platform != "win32" or struct.calcsize("P") != 8:
        parser.error("Build this Windows x64 release with 64-bit Python on Windows.")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", "--windowed", "--noupx",
        "--name", APP_NAME, "--icon", str(executable_icon()),
        "--distpath", str(output), "--workpath", str(ROOT / "build/pyinstaller"),
        "--specpath", str(ROOT / "build/spec"), str(ROOT / "gex_mod_tool.pyw"),
    ]
    subprocess.run(command, cwd=ROOT, check=True)
    executable = output / (APP_NAME + ".exe")
    instructions = ROOT / "packaging/使用说明.txt"
    notices = runtime_notices(output)
    archive = output / ARCHIVE_NAME
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as package:
        package.write(executable, executable.name)
        package.write(instructions, instructions.name)
        for notice in notices:
            package.write(notice, "third-party-notices/" + notice.name)
    if args.game_root:
        game = args.game_root.expanduser().resolve()
        if not (game / "ExtentData/Parts").is_dir() and (game / "ExceedCavalier/ExtentData/Parts").is_dir():
            game /= "ExceedCavalier"
        if not (game / "ExtentData/Parts").is_dir():
            parser.error("--game-root must contain the game's ExtentData/Parts directory.")
        destination = game / "ModTools"
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copy2(executable, destination / executable.name)
        shutil.copy2(instructions, destination / instructions.name)
        for notice in notices:
            notice_dir = destination / "third-party-notices"
            notice_dir.mkdir(exist_ok=True)
            shutil.copy2(notice, notice_dir / notice.name)
        print("Staged game tool:", destination / executable.name)
    print("Windows executable:", executable)
    print("Player download:", archive)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
