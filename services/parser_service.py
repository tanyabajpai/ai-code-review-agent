"""
AST parser service: scans Python files and extracts structured code information.
"""
import ast
import os
import logging
from pathlib import Path
from typing import List, Optional

from models.review_schema import ParsedFile, ParsedFunction

logger = logging.getLogger(__name__)

# Files larger than this threshold are skipped
MAX_FILE_SIZE_BYTES = 100_000  # 100 KB

# Directories to skip during scanning
SKIP_DIRS = {
    ".git", ".hg", ".svn",
    "venv", ".venv", "env", ".env",
    "node_modules", "__pycache__",
    ".tox", ".mypy_cache", ".pytest_cache",
    "dist", "build", "eggs", ".eggs",
    "site-packages",
}


def should_skip_path(path: str) -> bool:
    """
    Returns True if the given path should be excluded from scanning.
    Skips hidden directories, virtual environments, and build artifacts.
    """
    parts = Path(path).parts
    for part in parts:
        if part in SKIP_DIRS or part.startswith("."):
            return True
    return False


def collect_python_files(root_dir: str) -> List[str]:
    """
    Recursively collects all .py files from a directory,
    skipping excluded directories and oversized files.

    Returns a list of absolute file paths.
    """
    python_files = []
    root = Path(root_dir)

    for filepath in root.rglob("*.py"):
        abs_path = str(filepath)

        # Skip excluded directories
        rel_path = str(filepath.relative_to(root))
        if should_skip_path(rel_path):
            continue

        # Skip files that are too large
        try:
            size = os.path.getsize(abs_path)
            if size > MAX_FILE_SIZE_BYTES:
                logger.warning(f"Skipping large file ({size} bytes): {rel_path}")
                continue
        except OSError:
            continue

        python_files.append(abs_path)

    return sorted(python_files)


def extract_docstring(node: ast.AST) -> Optional[str]:
    """
    Extracts the docstring from a function or class AST node.
    Returns None if no docstring is present.
    """
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return None
    try:
        docstring = ast.get_docstring(node)
        return docstring
    except Exception:
        return None


def get_source_segment(source_lines: List[str], line_start: int, line_end: int) -> str:
    """
    Extracts a segment of source code by line numbers (1-indexed).
    Truncates to 150 lines max to avoid token overflow.
    """
    MAX_LINES = 150
    start = max(0, line_start - 1)
    end = min(len(source_lines), line_end)

    if (end - start) > MAX_LINES:
        half = MAX_LINES // 2
        head = source_lines[start : start + half]
        tail = source_lines[end - half : end]
        truncated_notice = [f"    # ... [{end - start - MAX_LINES} lines truncated] ...\n"]
        return "".join(head + truncated_notice + tail)

    return "".join(source_lines[start:end])


def parse_python_file(filepath: str, repo_root: str) -> Optional[ParsedFile]:
    """
    Parses a single Python file using the AST module.

    Extracts:
    - Functions (including async) with args, docstrings, line numbers
    - Classes with their methods
    - Import statements
    - Module-level statistics

    Returns a ParsedFile object, or None if parsing fails.
    """
    rel_path = os.path.relpath(filepath, repo_root)

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
            source_lines = source.splitlines(keepends=True)
    except OSError as e:
        logger.error(f"Cannot read {filepath}: {e}")
        return None

    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as e:
        logger.warning(f"Syntax error in {rel_path}: {e}")
        return None

    imports: List[str] = []
    functions: List[ParsedFunction] = []
    classes: List[str] = []

    for node in ast.walk(tree):
        # Collect import statements
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)

        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append(f"{module}.{alias.name}")

    # Walk top-level nodes for classes and functions
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            classes.append(node.name)
            class_source = get_source_segment(source_lines, node.lineno, node.end_lineno or node.lineno)

            # Add the class itself as a reviewable chunk
            functions.append(
                ParsedFunction(
                    name=node.name,
                    source_code=class_source,
                    docstring=extract_docstring(node),
                    args=[],
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                    is_class=True,
                )
            )

            # Also extract individual methods
            for item in ast.iter_child_nodes(node):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_source = get_source_segment(source_lines, item.lineno, item.end_lineno or item.lineno)
                    args = [arg.arg for arg in item.args.args]
                    functions.append(
                        ParsedFunction(
                            name=f"{node.name}.{item.name}",
                            source_code=method_source,
                            docstring=extract_docstring(item),
                            args=args,
                            line_start=item.lineno,
                            line_end=item.end_lineno or item.lineno,
                            is_class=False,
                        )
                    )

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_source = get_source_segment(source_lines, node.lineno, node.end_lineno or node.lineno)
            args = [arg.arg for arg in node.args.args]
            functions.append(
                ParsedFunction(
                    name=node.name,
                    source_code=func_source,
                    docstring=extract_docstring(node),
                    args=args,
                    line_start=node.lineno,
                    line_end=node.end_lineno or item.lineno,
                    is_class=False,
                )
            )

    return ParsedFile(
        filepath=filepath,
        relative_path=rel_path,
        functions=functions,
        imports=list(set(imports)),
        classes=classes,
        total_lines=len(source_lines),
    )


class ParserService:
    """Service for parsing Python repositories"""
    
    def __init__(self):
        """Initialize parser service"""
        pass
    
    def parse_repository(self, repo_root: str) -> List[ParsedFile]:
        """
        Scans and parses all Python files in a cloned repository.

        Args:
            repo_root: Root directory of the repository

        Returns:
            List of ParsedFile objects for each successfully parsed file.
        """
        python_files = collect_python_files(repo_root)

        if not python_files:
            logger.warning(f"No Python files found in {repo_root}")
            return []

        logger.info(f"Found {len(python_files)} Python files to parse")
        parsed_files = []

        for filepath in python_files:
            parsed = parse_python_file(filepath, repo_root)
            if parsed is not None:
                parsed_files.append(parsed)

        logger.info(f"Successfully parsed {len(parsed_files)} files")
        return parsed_files