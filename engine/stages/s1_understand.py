"""Stage 1 — Understand Codebase.

Walk all .py files in the target directory, parse each one with AST,
and build a FileMap list capturing functions, classes, imports, and LOC.
"""
from __future__ import annotations

import os
from pathlib import Path

from engine.config import Config
from engine.models.file_map import FileMap
from engine.utils.ast_helpers import (
    parse_file, read_source, extract_functions,
    extract_classes, extract_imports, annotate_parents,
)
from engine import progress


def run(target_path: str, cfg: Config) -> list[FileMap]:
    stage, name = 1, "Understand Codebase"
    progress.emit(stage, name, "running", f"Scanning {target_path} ...")

    py_files = _collect_py_files(target_path, cfg.skip_dirs)
    total = len(py_files)
    progress.emit(stage, name, "running", f"Found {total} .py files. Parsing ...")

    file_maps: list[FileMap] = []
    errors = 0

    for i, abs_path in enumerate(py_files, 1):
        rel = os.path.relpath(abs_path, target_path)
        tree, err = parse_file(abs_path)

        if err:
            errors += 1
            fm = FileMap(path=abs_path, rel_path=rel, parse_error=err)
        else:
            annotate_parents(tree)            # needed for is_method detection
            source = read_source(abs_path)
            fm = FileMap(
                path=abs_path,
                rel_path=rel,
                functions=extract_functions(tree, abs_path),
                classes=extract_classes(tree, abs_path),
                imports=extract_imports(tree),
                loc=len(source.splitlines()),
            )

        file_maps.append(fm)

        if i % 10 == 0 or i == total:
            progress.emit(stage, name, "running",
                          f"Parsed {i}/{total} files ({errors} errors so far) ...")

    func_count = sum(len(f.functions) for f in file_maps)
    class_count = sum(len(f.classes) for f in file_maps)
    method_count = sum(
        len(c.methods) for f in file_maps for c in f.classes
    )

    progress.emit(
        stage, name, "done",
        f"Parsed {total} files | {func_count} functions | "
        f"{class_count} classes | {method_count} methods | {errors} parse errors",
    )
    return file_maps


def _collect_py_files(root: str, skip_dirs: tuple[str, ...]) -> list[str]:
    """Recursively collect .py files, skipping excluded directories."""
    result = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skip dirs in-place so os.walk won't descend into them
        dirnames[:] = [
            d for d in dirnames
            if d not in skip_dirs and not d.endswith(".egg-info")
        ]
        for fn in filenames:
            if fn.endswith(".py"):
                result.append(os.path.join(dirpath, fn))
    return sorted(result)
