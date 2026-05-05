"""Compute a stable fingerprint for the pipeline inputs.

This is used by GitHub Actions to skip expensive processing, embedding,
and model calls when the raw dataset and pipeline code have not changed.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


DEFAULT_PATTERNS = [
    "src/data/raw",
    "src/rag_pipeline.py",
    "src/knowledge/data_processor.py",
    "src/knowledge/embedder.py",
    "src/knowledge/loader.py",
    "src/inference/predictor.py",
    "src/model/model_train.py",
    "requirements.txt",
]


def _normalize_bytes(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def _iter_files(root: Path, patterns: list[str]) -> list[Path]:
    files: list[Path] = []
    for pattern in patterns:
        candidate = root / pattern
        if candidate.is_file():
            files.append(candidate)
            continue

        if candidate.is_dir():
            files.extend(sorted(path for path in candidate.rglob("*") if path.is_file()))
            continue

        matches = sorted(path for path in root.glob(pattern) if path.is_file())
        files.extend(matches)

    unique_files = []
    seen = set()
    for path in sorted(files):
        if path in seen:
            continue
        seen.add(path)
        unique_files.append(path)
    return unique_files


def compute_fingerprint(root: Path, patterns: list[str]) -> str:
    digest = hashlib.sha256()

    for file_path in _iter_files(root, patterns):
        relative_path = file_path.relative_to(root).as_posix()
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(_normalize_bytes(file_path.read_bytes()))
        digest.update(b"\0")

    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute a stable pipeline fingerprint")
    parser.add_argument("--root", default=".", help="Repository root directory")
    parser.add_argument(
        "--pattern",
        action="append",
        dest="patterns",
        help="Additional file or directory pattern to include",
    )
    parser.add_argument(
        "--output",
        help="Optional file path to write the fingerprint to",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    patterns = DEFAULT_PATTERNS + (args.patterns or [])
    fingerprint = compute_fingerprint(root, patterns)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(f"{fingerprint}\n", encoding="utf-8")

    print(fingerprint)


if __name__ == "__main__":
    main()
