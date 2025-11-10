from __future__ import annotations

import argparse
import fnmatch
import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

import yaml

# --- Constants ---
DOC_HEADER = "\n---\n\n## FILE: {rel_path}\n\n{content}\n\n"
CODE_BLOCK = "```{lang}\n# FILE: {rel_path}\n\n{content}\n```\n\n"


def get_git_sha() -> str:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).decode("utf-8").strip()
        )
    except Exception:
        return "N/A (Not in a git repo)"


def sha256_file(file_path: Path) -> str:
    sha256 = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def is_excluded(path: Path, globs: Iterable[str]) -> bool:
    rel = str(path.as_posix())
    for pat in globs:
        if fnmatch.fnmatch(rel, pat):
            return True
    return False


def language_for(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in {".py"}:
        return "python"
    if ext in {".toml"}:
        return "toml"
    if ext in {".yaml", ".yml"}:
        return "yaml"
    if ext in {".json"}:
        return "json"
    if ext in {".md"}:
        return ""  # plain fenced block
    return ""


def add_doc_file(parts: List[str], checksums: List[str], rel_path: str) -> None:
    p = Path(rel_path)
    if not p.exists():
        print(f"  -> WARNING: File not found, skipping: {rel_path}")
        return
    content = p.read_text(encoding="utf-8")
    parts.append(DOC_HEADER.format(rel_path=rel_path, content=content))
    checksums.append(f"{sha256_file(p)}  {rel_path}")


def add_code_root(
    parts: List[str], checksums: List[str], root: Path, exclude_globs: Iterable[str]
) -> None:
    if not root.exists():
        print(f"  -> WARNING: Code root not found, skipping: {root}")
        return
    for path in sorted(root.rglob("*")):
        if path.is_dir() or is_excluded(path, exclude_globs):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue  # skip binaries
        rel_path = str(path.as_posix())
        lang = language_for(path)
        parts.append(CODE_BLOCK.format(lang=lang, rel_path=rel_path, content=content))
        checksums.append(f"{sha256_file(path)}  {rel_path}")


def main() -> None:
    print("--- [PK0 BUILDER] STARTING ---")  # --- Parse command-line args ---
    parser = argparse.ArgumentParser(description="Build the PK0 Superdoc from a manifest")
    parser.add_argument(
        "--manifest",
        default="pk0_manifest.yaml",
        help="Path to manifest YAML file (default: pk0_manifest.yaml)",
    )
    args = parser.parse_args()
    manifest_path = Path(args.manifest)

    if not manifest_path.exists():
        print(f"FATAL: Cannot find manifest file at {manifest_path}")
        return
    manifest: Dict[str, Any] = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    out_path = Path(manifest.get("superdoc_output", "build/PK0_SUPERDOC.md"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    parts: List[str] = []
    checksums: List[str] = []

    parts.append("# OM LEAGUE — PK0 SUPERDOC\n\n")

    for section in manifest.get("sections", []):
        heading = section.get("heading", "").strip()
        print(f"Processing Section: {heading or '(unnamed)'}")
        if heading:
            parts.append(f"# {heading}\n\n")

        for file_str in section.get("files", []) or []:
            add_doc_file(parts, checksums, file_str)
        for code_root_str in section.get("code_roots", []) or []:
            add_code_root(
                parts, checksums, Path(code_root_str), section.get("exclude_globs", []) or []
            )

    if manifest.get("provenance_footer", True):
        print("Adding provenance footer...")
        parts.append("\n---\n\n# PROVENANCE FOOTER\n")
        parts.append(f"- **Build Date:** {datetime.now(timezone.utc).isoformat()}Z\n")
        parts.append(f"- **Git SHA:** {get_git_sha()}\n")
        parts.append("- **File Checksums:**\n```\n")
        parts.append("\n".join(checksums))
        parts.append("\n```\n")

    out_path.write_text("".join(parts), encoding="utf-8")
    print("\n--- [PK0 BUILDER] SUCCESS ---")
    print(f"Superdoc written to: {out_path.resolve()}")


if __name__ == "__main__":
    main()
