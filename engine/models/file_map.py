from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ImportInfo:
    module: str
    names: list[str]        # specific names imported, empty = "import module"
    is_from: bool           # True if `from X import Y`
    lineno: int
    resolved_path: Optional[str] = None   # resolved to a file path if local


@dataclass
class FunctionInfo:
    name: str
    lineno: int
    end_lineno: int
    args: list[str]                       # parameter names
    docstring: Optional[str]
    decorators: list[str]
    is_method: bool                       # True if defined inside a class
    class_name: Optional[str] = None      # parent class if is_method
    source: str = ""                      # raw source text


@dataclass
class ClassInfo:
    name: str
    lineno: int
    end_lineno: int
    bases: list[str]
    methods: list[FunctionInfo] = field(default_factory=list)
    docstring: Optional[str] = None


@dataclass
class FileMap:
    path: str                             # absolute path
    rel_path: str                         # relative to target root
    functions: list[FunctionInfo] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)
    imports: list[ImportInfo] = field(default_factory=list)
    loc: int = 0                          # lines of code
    parse_error: Optional[str] = None     # if AST failed
