"""Shared helper for writing PR file contents to a temp dir for CLI tools to scan."""
from pathlib import Path


def write_files(tmp_path: Path, files: list[dict]) -> dict[str, str]:
    """Write each file's content under tmp_path, returning {tmp_relpath: original_filename}."""
    written = {}
    for f in files:
        rel = f["filename"].lstrip("/").replace("..", "_")
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(f["content"], encoding="utf-8")
        written[rel] = f["filename"]
    return written
