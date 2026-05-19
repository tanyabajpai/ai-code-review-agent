"""
Tests for the AST parser service.
Run with: pytest tests/
"""
import os
import sys
import textwrap
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.parser_service import parse_python_file, collect_python_files, should_skip_path


def write_temp_py(content: str) -> tuple:
    """Helper: write Python content to a temp file, return (dir, filepath)."""
    tmpdir = tempfile.mkdtemp()
    filepath = os.path.join(tmpdir, "test_module.py")
    with open(filepath, "w") as f:
        f.write(textwrap.dedent(content))
    return tmpdir, filepath


def test_parse_simple_function():
    tmpdir, filepath = write_temp_py("""
        def add(a, b):
            \"\"\"Add two numbers.\"\"\"
            return a + b
    """)
    result = parse_python_file(filepath, tmpdir)
    assert result is not None
    assert len(result.functions) == 1
    assert result.functions[0].name == "add"
    assert result.functions[0].docstring == "Add two numbers."
    assert "a" in result.functions[0].args


def test_parse_class_with_methods():
    tmpdir, filepath = write_temp_py("""
        class Calculator:
            def multiply(self, x, y):
                return x * y
    """)
    result = parse_python_file(filepath, tmpdir)
    assert result is not None
    assert "Calculator" in result.classes
    method_names = [f.name for f in result.functions]
    assert any("multiply" in name for name in method_names)


def test_parse_imports():
    tmpdir, filepath = write_temp_py("""
        import os
        from pathlib import Path
        
        def dummy():
            pass
    """)
    result = parse_python_file(filepath, tmpdir)
    assert result is not None
    assert "os" in result.imports
    assert any("Path" in imp for imp in result.imports)


def test_skip_venv_directories():
    assert should_skip_path("venv/lib/python.py") is True
    assert should_skip_path(".git/config.py") is True
    assert should_skip_path("src/main.py") is False


def test_parse_invalid_syntax_returns_none():
    tmpdir, filepath = write_temp_py("def broken( :\n    pass")
    result = parse_python_file(filepath, tmpdir)
    assert result is None


def test_collect_python_files_skips_venv(tmp_path):
    # Create a .py file in venv (should be skipped)
    venv_dir = tmp_path / "venv" / "lib"
    venv_dir.mkdir(parents=True)
    (venv_dir / "skipped.py").write_text("x = 1")

    # Create a .py file in src (should be included)
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "included.py").write_text("x = 1")

    files = collect_python_files(str(tmp_path))
    assert not any("venv" in f for f in files)
    assert any("included.py" in f for f in files)
