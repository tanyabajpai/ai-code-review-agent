"""
Tests for the chunk service (services/chunk_service.py).
Run with: pytest tests/
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.chunk_service import ChunkService
from models.review_schema import ParsedFile, ParsedFunction


def make_parsed_file(functions):
    return ParsedFile(
        filepath="/repo/test_module.py",
        relative_path="test_module.py",
        functions=functions,
        imports=[],
        classes=[],
        total_lines=50,
    )


def make_function(name, is_class=False, line_start=1, line_end=5):
    return ParsedFunction(
        name=name,
        source_code=f"def {name}(): pass",
        docstring=None,
        args=[],
        line_start=line_start,
        line_end=line_end,
        is_class=is_class,
    )


def test_create_chunks_from_single_function():
    parsed_file = make_parsed_file([make_function("add")])
    service = ChunkService()
    chunks = service.create_chunks([parsed_file])

    assert len(chunks) == 1
    assert chunks[0].file_path == "test_module.py"
    assert chunks[0].chunk_type == "function"
    assert "Function: add" in chunks[0].context


def test_create_chunks_marks_class_type_correctly():
    parsed_file = make_parsed_file([make_function("Calculator", is_class=True)])
    service = ChunkService()
    chunks = service.create_chunks([parsed_file])

    assert len(chunks) == 1
    assert chunks[0].chunk_type == "class"


def test_create_chunks_across_multiple_files():
    file_a = make_parsed_file([make_function("foo")])
    file_b = make_parsed_file([make_function("bar"), make_function("baz")])
    service = ChunkService()
    chunks = service.create_chunks([file_a, file_b])

    assert len(chunks) == 3


def test_create_chunks_respects_limit():
    parsed_file = make_parsed_file([make_function(f"func_{i}") for i in range(10)])
    service = ChunkService()
    chunks = service.create_chunks([parsed_file], limit=3)

    assert len(chunks) == 3


def test_create_chunks_no_functions_returns_empty():
    parsed_file = make_parsed_file([])
    service = ChunkService()
    chunks = service.create_chunks([parsed_file])

    assert chunks == []


def test_create_chunks_empty_file_list():
    service = ChunkService()
    chunks = service.create_chunks([])

    assert chunks == []


def test_create_chunks_context_includes_line_numbers():
    parsed_file = make_parsed_file([make_function("compute", line_start=10, line_end=25)])
    service = ChunkService()
    chunks = service.create_chunks([parsed_file])

    assert "Lines: 10-25" in chunks[0].context
