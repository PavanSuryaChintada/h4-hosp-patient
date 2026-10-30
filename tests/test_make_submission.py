"""The team zip has the layout the pack's README asks for: README.md, .gitignore, submission/ and
FULL_CODE/ at the top, and nothing else; and the same inputs give the same bytes."""

from __future__ import annotations

import zipfile
from pathlib import Path

from tools.make_submission import CODE_FOLDER, SUBMISSION_FILES, layout, too_large, write_zip

COMMITTED = ["README.md", ".gitignore", "run.py", "src/medsafe/pipeline.py", "ui/src/main.tsx",
             ".github/workflows/pages.yml", "submission/H4_predictions.csv"]


def test_only_readme_and_gitignore_stay_at_the_top() -> None:
    placed = layout(COMMITTED)
    assert placed["README.md"] == "README.md" and placed[".gitignore"] == ".gitignore"
    assert placed["run.py"] == f"{CODE_FOLDER}/run.py"
    assert placed[".github/workflows/pages.yml"] == f"{CODE_FOLDER}/.github/workflows/pages.yml"
    assert "submission/H4_predictions.csv" not in placed        # the zip carries the checked, regenerated files


def test_large_files_need_to_be_allowed(tmp_path: Path) -> None:
    (tmp_path / "big.bin").write_bytes(b"0" * 10_000_001)
    (tmp_path / "small.txt").write_text("ok")
    assert too_large(tmp_path, ["big.bin", "small.txt"]) == ["big.bin"]


def test_zip_top_level_and_determinism(tmp_path: Path) -> None:
    clone, submission = tmp_path / "clone", tmp_path / "submission"
    committed = ["README.md", ".gitignore", "run.py", "src/medsafe/pipeline.py"]
    for path in committed:
        (clone / path).parent.mkdir(parents=True, exist_ok=True)
        (clone / path).write_text(path)
    submission.mkdir()
    for name in SUBMISSION_FILES:
        (submission / name).write_text("patient_id\n")
    one, two = tmp_path / "one.zip", tmp_path / "two.zip"
    write_zip(one, clone, layout(committed), submission)
    write_zip(two, clone, layout(committed), submission)
    assert one.read_bytes() == two.read_bytes()
    with zipfile.ZipFile(one) as archive:
        top = {name.split("/", 1)[0] for name in archive.namelist()}
    assert top == {"README.md", ".gitignore", "submission", CODE_FOLDER}
