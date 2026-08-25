"""
Tests for Pydantic schema validation (models/review_schema.py).
Run with: pytest tests/
"""
import os
import sys

import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.review_schema import ReviewComment, ReviewResult, Severity, Category


def make_comment(confidence: int) -> ReviewComment:
    return ReviewComment(
        category=Category.BUG,
        severity=Severity.MEDIUM,
        line_start=1,
        line_end=5,
        issue="Possible off-by-one error",
        suggestion="Use range(n) instead of range(n+1)",
        confidence=confidence,
    )


def test_confidence_accepts_boundary_values():
    assert make_comment(0).confidence == 0
    assert make_comment(100).confidence == 100


def test_confidence_rejects_out_of_range():
    with pytest.raises(ValidationError):
        make_comment(101)
    with pytest.raises(ValidationError):
        make_comment(-1)


def test_needs_verification_threshold():
    assert make_comment(69).needs_verification is True
    assert make_comment(70).needs_verification is False


def test_invalid_category_rejected():
    with pytest.raises(ValidationError):
        ReviewComment(
            category="not_a_real_category",
            severity=Severity.LOW,
            line_start=1,
            line_end=2,
            issue="x",
            suggestion="y",
            confidence=50,
        )


def make_result(comments):
    return ReviewResult(
        file_path="test.py",
        chunk_type="function",
        line_start=1,
        line_end=10,
        comments=comments,
        summary="Looks mostly fine.",
        overall_quality=7,
    )


def test_overall_quality_rejects_out_of_range():
    with pytest.raises(ValidationError):
        ReviewResult(
            file_path="test.py",
            chunk_type="function",
            line_start=1,
            line_end=10,
            comments=[],
            summary="x",
            overall_quality=11,
        )
    with pytest.raises(ValidationError):
        ReviewResult(
            file_path="test.py",
            chunk_type="function",
            line_start=1,
            line_end=10,
            comments=[],
            summary="x",
            overall_quality=0,
        )


def test_high_and_low_confidence_comment_split():
    result = make_result([make_comment(90), make_comment(50), make_comment(75)])

    high = result.high_confidence_comments
    low = result.low_confidence_comments

    assert len(high) == 2
    assert len(low) == 1
    assert all(c.confidence >= 70 for c in high)
    assert all(c.confidence < 70 for c in low)


def test_review_result_with_no_comments():
    result = make_result([])
    assert result.high_confidence_comments == []
    assert result.low_confidence_comments == []
