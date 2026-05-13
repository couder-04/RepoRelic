"""AST utilities shared across all stages."""
import ast
import textwrap
from pathlib import Path
from typing import Optional

from engine.models.file_map import FunctionInfo, ClassInfo, ImportInfo


# ---------------------------------------------------------------------------
# Safe parsing
# ---------------------------------------------------------------------------

def parse_file(path: str) -> tuple[Optional[ast.Module], Optional[str]]:
    """Parse a Python file into an AST module.

    Returns
    -------
    (tree, None)   on success
    (None, error_msg) on failure
    """
    try:
        source = Path(path).read_text(encoding="utf-8", errors="replace")
        return ast.parse(source, filename=path), None
    except SyntaxError as e:
        return None, f"SyntaxError at line {e.lineno}: {e.msg}"
    except Exception as e:
        return None, str(e)


def read_source(path: str) -> str:
    """Read raw source of a file, replacing unreadable bytes."""
    return Path(path).read_text(encoding="utf-8", errors="replace")


def get_function_source(path: str, lineno: int, end_lineno: int) -> str:
    """Extract and dedent a function's source lines from a file."""
    lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    # lineno is 1-indexed
    snippet = lines[lineno - 1 : end_lineno]
    return textwrap.dedent("\n".join(snippet))


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

def _get_docstring(node: ast.AST) -> Optional[str]:
    return ast.get_docstring(node)


def _decorator_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    names = []
    for dec in node.decorator_list:
        if isinstance(dec, ast.Name):
            names.append(dec.id)
        elif isinstance(dec, ast.Attribute):
            names.append(f"{ast.unparse(dec)}")
        else:
            names.append(ast.unparse(dec))
    return names


def _arg_names(args: ast.arguments) -> list[str]:
    all_args = (
        args.posonlyargs + args.args + args.kwonlyargs
        + ([args.vararg] if args.vararg else [])
        + ([args.kwarg] if args.kwarg else [])
    )
    return [a.arg for a in all_args]


def extract_functions(tree: ast.Module, path: str) -> list[FunctionInfo]:
    """Return all top-level (non-method) function definitions."""
    results = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Skip methods — they'll be captured via extract_classes
            parent = getattr(node, "_parent", None)
            if isinstance(parent, ast.ClassDef):
                continue
            results.append(FunctionInfo(
                name=node.name,
                lineno=node.lineno,
                end_lineno=node.end_lineno or node.lineno,
                args=_arg_names(node.args),
                docstring=_get_docstring(node),
                decorators=_decorator_names(node),
                is_method=False,
                source=get_function_source(path, node.lineno, node.end_lineno or node.lineno),
            ))
    return results


def extract_classes(tree: ast.Module, path: str) -> list[ClassInfo]:
    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            methods = []
            for child in ast.walk(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.append(FunctionInfo(
                        name=child.name,
                        lineno=child.lineno,
                        end_lineno=child.end_lineno or child.lineno,
                        args=_arg_names(child.args),
                        docstring=_get_docstring(child),
                        decorators=_decorator_names(child),
                        is_method=True,
                        class_name=node.name,
                        source=get_function_source(path, child.lineno, child.end_lineno or child.lineno),
                    ))
            bases = [ast.unparse(b) for b in node.bases]
            results.append(ClassInfo(
                name=node.name,
                lineno=node.lineno,
                end_lineno=node.end_lineno or node.lineno,
                bases=bases,
                methods=methods,
                docstring=_get_docstring(node),
            ))
    return results


def extract_imports(tree: ast.Module) -> list[ImportInfo]:
    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                results.append(ImportInfo(
                    module=alias.name,
                    names=[],
                    is_from=False,
                    lineno=node.lineno,
                ))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = [alias.name for alias in node.names]
            results.append(ImportInfo(
                module=module,
                names=names,
                is_from=True,
                lineno=node.lineno,
            ))
    return results


def annotate_parents(tree: ast.AST) -> ast.AST:
    """Annotate every AST node with a _parent attribute (needed for method detection)."""
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child._parent = node  # type: ignore[attr-defined]
    return tree
