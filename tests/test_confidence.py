"""
Tests for the confidence engine.
Run with: pytest tests/
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.confidence import (
    get_confidence_label, bucket_reviews, sort_reviews_by_severity, filter_reviews
)
from models.review_schema import ReviewComment


def make_review(confidence: int, severity: str = "Medium", issue_type: str = "Bug Risk") -> ReviewComment:
    return ReviewComment(
        file="test.py",
        function="my_func",
        issue_type=issue_type,
        severity=severity,
        confidence=confidence,
        comment="Test comment.",
        suggestion="Test suggestion.",
    )


def test_confidence_labels():
    assert get_confidence_label(95) == "High Confidence"
    assert get_confidence_label(80) == "High Confidence"
    assert get_confidence_label(79) == "Medium Confidence"
    assert get_confidence_label(50) == "Medium Confidence"
    assert get_confidence_label(49) == "Verify This"
    assert get_confidence_label(0) == "Verify This"


def test_bucket_reviews():
    reviews = [
        make_review(90),
        make_review(65),
        make_review(30),
    ]
    buckets = bucket_reviews(reviews)
    assert len(buckets["High Confidence"]) == 1
    assert len(buckets["Medium Confidence"]) == 1
    assert len(buckets["Verify This"]) == 1


def test_sort_by_severity():
    reviews = [
        make_review(70, severity="Low"),
        make_review(85, severity="Critical"),
        make_review(60, severity="Medium"),
    ]
    sorted_r = sort_reviews_by_severity(reviews)
    assert sorted_r[0].severity == "Critical"
    assert sorted_r[-1].severity == "Low"


def test_filter_by_confidence():
    reviews = [make_review(30), make_review(60), make_review(90)]
    filtered = filter_reviews(reviews, min_confidence=50)
    assert len(filtered) == 2
    assert all(r.confidence >= 50 for r in filtered)


def test_filter_by_severity():
    reviews = [
        make_review(80, severity="High"),
        make_review(80, severity="Low"),
        make_review(80, severity="Medium"),
    ]
    filtered = filter_reviews(reviews, severities=["High", "Medium"])
    assert len(filtered) == 2
    assert all(r.severity in ["High", "Medium"] for r in filtered)
