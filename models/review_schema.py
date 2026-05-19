"""
Data models for parsed code structures
"""
from typing import List, Optional
from pydantic import BaseModel


class ParsedFunction(BaseModel):
    """Represents a parsed function or method"""
    name: str
    source_code: str
    docstring: Optional[str] = None
    args: List[str] = []
    line_start: int
    line_end: int
    is_class: bool = False


class ParsedFile(BaseModel):
    """Represents a parsed Python file"""
    filepath: str
    relative_path: str
    functions: List[ParsedFunction] = []
    imports: List[str] = []
    classes: List[str] = []
    total_lines: int = 0


class CodeChunk(BaseModel):
    """Represents a chunk of code for review"""
    file_path: str
    chunk_content: str
    chunk_type: str  # 'function', 'class', 'module'
    context: Optional[str] = None


class ReviewResult(BaseModel):
    """Represents the result of a code review"""
    file_path: str
    chunk: str
    review: str
    confidence: Optional[str] = None
    issues_found: List[str] = []
    suggestions: List[str] = []