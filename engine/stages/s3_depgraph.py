"""Stage 3 — Dependency & Call Graph.

Builds two directed graphs:
  - import_graph : file → file (which file imports which)
  - call_graph   : function → function (which function calls which)

Both are stored as a single combined nx.DiGraph where node type is
encoded as a node attribute ("file" or "function").
"""
from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import Optional

import networkx as nx

from engine.config import Config
from engine.models.file_map import FileMap
from engine import progress


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------

def run(file_maps: list[FileMap], target_path: str, cfg: Config) -> nx.DiGraph:
    stage, name = 3, "Dependency Graph"
    progress.emit(stage, name, "running", "Building import graph ...")

    # Map module name → abs file path for local resolution
    path_index = _build_path_index(file_maps, target_path)

    G = nx.DiGraph()

    # Add all file nodes
    for fm in file_maps:
        G.add_node(fm.rel_path, kind="file", abs_path=fm.path)

    # Import edges
    import_edge_count = 0
    for fm in file_maps:
        for imp in fm.imports:
            resolved = _resolve_import(imp.module, fm.path, target_path, path_index)
            if resolved:
                rel_resolved = os.path.relpath(resolved, target_path)
                if fm.rel_path != rel_resolved:
                    G.add_edge(fm.rel_path, rel_resolved, kind="import")
                    import_edge_count += 1

    progress.emit(stage, name, "running",
                  f"Import graph done ({import_edge_count} edges). Building call graph ...")

    # Call edges — use AST NodeVisitor per file
    call_edge_count = 0
    for fm in file_maps:
        if fm.parse_error:
            continue
        try:
            source = Path(fm.path).read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source)
            visitor = _CallGraphVisitor(fm.rel_path)
            visitor.visit(tree)
            for caller, callee in visitor.edges:
                if not G.has_node(caller):
                    G.add_node(caller, kind="function")
                if not G.has_node(callee):
                    G.add_node(callee, kind="function")
                G.add_edge(caller, callee, kind="call")
                call_edge_count += 1
        except Exception:
            continue

    progress.emit(
        stage, name, "done",
        f"Graph built: {G.number_of_nodes()} nodes | "
        f"{import_edge_count} import edges | {call_edge_count} call edges",
    )
    return G


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_path_index(file_maps: list[FileMap], root: str) -> dict[str, str]:
    """Map dotted module name to absolute file path for local modules."""
    index: dict[str, str] = {}
    for fm in file_maps:
        rel = fm.rel_path.replace(os.sep, ".").removesuffix(".py")
        index[rel] = fm.path
        # Also index the last component for plain 'import module' style
        parts = rel.split(".")
        index[parts[-1]] = fm.path
    return index


def _resolve_import(module: str, from_file: str, root: str,
                    index: dict[str, str]) -> Optional[str]:
    """Try to resolve a module name to a local file path."""
    if module in index:
        return index[module]
    # Try dotted sub-path
    as_path = os.path.join(root, *module.split(".")) + ".py"
    if os.path.exists(as_path):
        return as_path
    return None


# ---------------------------------------------------------------------------
# Call graph visitor
# ---------------------------------------------------------------------------

class _CallGraphVisitor(ast.NodeVisitor):
    """Walk an AST collecting (caller_qualified, callee_name) edges."""

    def __init__(self, rel_file: str):
        self.rel_file = rel_file
        self.edges: list[tuple[str, str]] = []
        self._scope_stack: list[str] = []

    def _current_scope(self) -> str:
        base = self.rel_file.removesuffix(".py").replace(os.sep, ".")
        if self._scope_stack:
            return f"{base}.{'.'.join(self._scope_stack)}"
        return base

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._scope_stack.append(node.name)
        self.generic_visit(node)
        self._scope_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node: ast.Call):
        caller = self._current_scope()
        callee: Optional[str] = None
        if isinstance(node.func, ast.Name):
            callee = node.func.id
        elif isinstance(node.func, ast.Attribute):
            callee = node.func.attr
        if callee and caller != callee:
            self.edges.append((caller, callee))
        self.generic_visit(node)
