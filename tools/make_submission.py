"""Build the team zip the organisers ask for, from a fresh clone of the committed code.

    python tools/make_submission.py --team 1058          # -> dist/1058_H4.zip

The pack's README ("What to submit") wants one zip of the whole project holding, at its top, only
README.md, submission/ (H4_predictions.csv and H4_resolution.csv), FULL_CODE/ (all the code: the
pipeline that wrote submission/ and the demo app) and .gitignore. The repository keeps its working
layout, because the GitHub Pages and Vercel builds, the tests and the docs all point into it; this
script makes the submitted layout from it, so the two cannot drift:

1. ``git clone`` the committed HEAD into a temporary folder, so nothing uncommitted ships.
2. Run that clone's ``run.py`` on the test split, writing the two submission files.
3. Check them with ``eval.validate_submission`` (the organisers' own validators, plus every test
   patient and every written line present), and require them to equal the committed submission/.
4. Zip README.md and .gitignore at the top, the two files under submission/ and every other
   committed file under FULL_CODE/. The pack's data is not in git, so it cannot ship.

Never on the scoring path. Standard library only. The same commit gives a byte-identical zip:
entries are sorted and carry a fixed timestamp.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Iterable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACK = REPO_ROOT / "data" / "pack"
TOP_LEVEL = ("README.md", ".gitignore")       # the only committed files kept at the top of the zip
CODE_FOLDER = "FULL_CODE"
SUBMISSION_FOLDER = "submission"
SUBMISSION_FILES = ("H4_predictions.csv", "H4_resolution.csv")
MAX_FILE_BYTES = 10_000_000                   # nothing this large belongs in a code zip...
ALLOWED_LARGE = frozenset({"ui/public/data/pipeline.json"})   # ...except the demo app's data file (tools/export_ui.py)
ZIP_TIME = (2026, 1, 1, 0, 0, 0)
TEAM_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")


def layout(paths: Iterable[str]) -> dict[str, str]:
    """Where each committed file goes in the zip: README.md and .gitignore at the top, everything
    else under FULL_CODE/. Files under submission/ are left out here; the zip carries the ones
    this script regenerated and checked."""
    placed = {}
    for path in paths:
        if path.startswith(f"{SUBMISSION_FOLDER}/"):
            continue
        placed[path] = path if path in TOP_LEVEL else f"{CODE_FOLDER}/{path}"
    return placed


def too_large(clone: Path, paths: Iterable[str]) -> list[str]:
    """Committed files over MAX_FILE_BYTES that are not in ALLOWED_LARGE."""
    return [p for p in paths if p not in ALLOWED_LARGE and (clone / p).stat().st_size > MAX_FILE_BYTES]


def git(args: list[str], cwd: Path) -> str:
    """Run git and return its standard output; raises on failure."""
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def uncommitted(repo: Path) -> list[str]:
    """Tracked files with changes that are not committed, which the zip will not contain."""
    return [line[3:] for line in git(["status", "--porcelain", "--untracked-files=no"], repo).splitlines()]


def run_pipeline(clone: Path, pack: Path, out: Path) -> None:
    """The clone's run.py on the test split, writing the two submission files into ``out``."""
    env = {**os.environ, "MEDSAFE_DATA_DIR": str(pack)}
    subprocess.run([sys.executable, "run.py", "--split", "test", "--output", str(out)], cwd=clone, env=env, check=True)


def validate(clone: Path, pack: Path, folder: Path) -> bool:
    """The clone's eval.validate_submission on ``folder``; True if it reports no problem."""
    env = {**os.environ, "MEDSAFE_DATA_DIR": str(pack)}
    return subprocess.run([sys.executable, "-m", "eval.validate_submission", str(folder)], cwd=clone, env=env).returncode == 0


def same_files(a: Path, b: Path) -> bool:
    """Whether both folders hold the two submission files with identical bytes."""
    return all((a / f).is_file() and (b / f).is_file() and (a / f).read_bytes() == (b / f).read_bytes()
               for f in SUBMISSION_FILES)


def write_zip(zip_path: Path, clone: Path, placed: dict[str, str], submission: Path) -> int:
    """Write the zip, entries sorted, every timestamp fixed. Returns the number of files in it."""
    entries = sorted([(clone / src, dst) for src, dst in placed.items()]
                     + [(submission / f, f"{SUBMISSION_FOLDER}/{f}") for f in SUBMISSION_FILES], key=lambda e: e[1])
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for source, name in entries:
            info = zipfile.ZipInfo(name, date_time=ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, source.read_bytes())
    return len(entries)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """``--team`` (the organisers' team id; names the zip), ``--out``, ``--pack``."""
    parser = argparse.ArgumentParser(description="Build <team>_H4.zip in the layout the pack's README asks for.")
    parser.add_argument("--team", required=True, help="the team id: the zip is <team>_H4.zip")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "dist", help="folder for the zip")
    parser.add_argument("--pack", type=Path, default=DEFAULT_PACK, help="the organisers' pack (holds data/ and evaluate.py)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Clone, regenerate, validate, zip. Returns 0 on success, 1 if anything is wrong."""
    args = parse_args(argv)
    if not TEAM_ID.fullmatch(args.team):
        print(f"--team must be letters, digits, - or _ (got {args.team!r})")
        return 1
    pack = args.pack.resolve()
    if not (pack / "data").is_dir():
        print(f"no pack at {pack}: pass --pack, the folder holding data/ and evaluate.py")
        return 1
    pending = uncommitted(REPO_ROOT)
    if pending:
        print(f"note: {len(pending)} tracked file(s) have uncommitted changes and will not be in the zip: {', '.join(pending[:5])}")

    with tempfile.TemporaryDirectory() as tmp:
        clone = Path(tmp) / "clone"
        git(["clone", "--quiet", "--no-hardlinks", str(REPO_ROOT), str(clone)], REPO_ROOT)
        head = git(["rev-parse", "--short", "HEAD"], clone).strip()
        files = [f for f in git(["ls-files", "-z"], clone).split("\0") if f]
        large = too_large(clone, files)
        if large:
            print(f"files over {MAX_FILE_BYTES // 1_000_000} MB: {large}")
            return 1

        regenerated = Path(tmp) / SUBMISSION_FOLDER
        print(f"commit {head}: running run.py on the test split")
        run_pipeline(clone, pack, regenerated)
        if not validate(clone, pack, regenerated):
            print("the submission files did not validate; no zip written")
            return 1
        if not same_files(clone / SUBMISSION_FOLDER, regenerated):
            print("the committed submission/ differs from what run.py writes now: regenerate and commit it first")
            return 1

        zip_path = args.out / f"{args.team}_H4.zip"
        count = write_zip(zip_path, clone, layout(files), regenerated)

    with zipfile.ZipFile(zip_path) as archive:
        top = sorted({name.split("/", 1)[0] + ("/" if "/" in name else "") for name in archive.namelist()})
    print(f"wrote {zip_path} ({zip_path.stat().st_size / 1e6:.1f} MB, {count} files, commit {head})")
    print(f"top level: {', '.join(top)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
