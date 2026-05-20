"""
Data models for parsed code structures and reviews
"""
from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class Severity(str, Enum):
    """Issue severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Category(str, Enum):
    """Review comment categories"""
    BUG = "bug"
    SECURITY = "security"
    PERFORMANCE = "performance"
    STYLE = "style"
    DOCUMENTATION = "documentation"
    BEST_PRACTICE = "best_practice"
    MAINTAINABILITY = "maintainability"


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


class ReviewComment(BaseModel):
    """Single review comment with confidence scoring"""
    category: Category
    severity: Severity
    line_start: int
    line_end: int
    issue: str = Field(..., description="Clear description of the issue")
    suggestion: str = Field(..., description="Specific suggestion to fix the issue")
    confidence: int = Field(..., ge=0, le=100, description="Confidence score 0-100")
    
    @property
    def needs_verification(self) -> bool:
        """Returns True if confidence is below threshold"""
        return self.confidence < 70


class ReviewResult(BaseModel):
    """Complete review result for a code chunk"""
    file_path: str
    chunk_type: str
    line_start: int
    line_end: int
    comments: List[ReviewComment] = []
    summary: str
    overall_quality: int = Field(..., ge=1, le=10, description="Overall code quality 1-10")
    
    @property
    def high_confidence_comments(self) -> List[ReviewComment]:
        """Returns comments with confidence >= 70"""
        return [c for c in self.comments if c.confidence >= 70]
    
    @property
    def low_confidence_comments(self) -> List[ReviewComment]:
        """Returns comments with confidence < 70 that need verification"""
        return [c for c in self.comments if c.confidence < 70]