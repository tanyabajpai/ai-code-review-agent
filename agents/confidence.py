"""
Confidence engine: categorizes review comments into confidence buckets
and computes aggregate statistics.
"""
from typing import List, Dict, Tuple
from collections import defaultdict

from models.review_schema import ReviewComment, ConfidenceLevel, RepoStats


# Confidence thresholds
HIGH_CONFIDENCE_MIN = 80
MEDIUM_CONFIDENCE_MIN = 50
# Below MEDIUM_CONFIDENCE_MIN → "Verify This"


def get_confidence_label(score: int) -> str:
    """
    Maps a numeric confidence score to a human-readable label.
    """
    if score >= HIGH_CONFIDENCE_MIN:
        return ConfidenceLevel.HIGH.value
    elif score >= MEDIUM_CONFIDENCE_MIN:
        return ConfidenceLevel.MEDIUM.value
    else:
        return ConfidenceLevel.VERIFY.value


def get_confidence_color(score: int) -> str:
    """
    Returns a hex color code for the confidence score for UI display.
    """
    if score >= HIGH_CONFIDENCE_MIN:
        return "#22c55e"   # Green
    elif score >= MEDIUM_CONFIDENCE_MIN:
        return "#f59e0b"   # Amber
    else:
        return "#ef4444"   # Red


def get_severity_color(severity: str) -> str:
    """
    Returns a hex color for severity badges.
    """
    colors = {
        "Critical": "#7c3aed",
        "High": "#ef4444",
        "Medium": "#f59e0b",
        "Low": "#3b82f6",
        "Info": "#6b7280",
    }
    return colors.get(severity, "#6b7280")


def bucket_reviews(
    reviews: List[ReviewComment],
) -> Dict[str, List[ReviewComment]]:
    """
    Separates reviews into three confidence buckets.

    Returns:
        {
            "High Confidence": [...],
            "Medium Confidence": [...],
            "Verify This": [...],
        }
    """
    buckets: Dict[str, List[ReviewComment]] = {
        ConfidenceLevel.HIGH.value: [],
        ConfidenceLevel.MEDIUM.value: [],
        ConfidenceLevel.VERIFY.value: [],
    }

    for review in reviews:
        label = get_confidence_label(review.confidence)
        buckets[label].append(review)

    return buckets


def filter_reviews(
    reviews: List[ReviewComment],
    min_confidence: int = 0,
    severities: List[str] = None,
    issue_types: List[str] = None,
) -> List[ReviewComment]:
    """
    Filters a list of reviews by confidence threshold, severity, and issue type.
    """
    filtered = reviews

    if min_confidence > 0:
        filtered = [r for r in filtered if r.confidence >= min_confidence]

    if severities:
        filtered = [r for r in filtered if r.severity in severities]

    if issue_types:
        filtered = [r for r in filtered if r.issue_type in issue_types]

    return filtered


def compute_stats_from_reviews(
    reviews: List[ReviewComment],
    repo_url: str,
    total_files: int,
    total_functions: int,
    total_classes: int,
    total_lines: int,
) -> RepoStats:
    """
    Aggregates review results into summary statistics.
    """
    severity_counts: Dict[str, int] = defaultdict(int)
    for r in reviews:
        severity_counts[r.severity] += 1

    return RepoStats(
        repo_url=repo_url,
        total_files=total_files,
        total_functions=total_functions,
        total_classes=total_classes,
        total_lines=total_lines,
        issues_found=len(reviews),
        high_severity=severity_counts.get("Critical", 0) + severity_counts.get("High", 0),
        medium_severity=severity_counts.get("Medium", 0),
        low_severity=severity_counts.get("Low", 0) + severity_counts.get("Info", 0),
    )


def sort_reviews_by_severity(reviews: List[ReviewComment]) -> List[ReviewComment]:
    """
    Sorts reviews with Critical/High issues first, then by confidence descending.
    """
    severity_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3, "Info": 4}
    return sorted(
        reviews,
        key=lambda r: (severity_order.get(r.severity, 5), -r.confidence),
    )


def get_issue_type_distribution(reviews: List[ReviewComment]) -> Dict[str, int]:
    """
    Returns a count of reviews per issue type for chart display.
    """
    dist: Dict[str, int] = defaultdict(int)
    for r in reviews:
        dist[r.issue_type] += 1
    return dict(dist)


def get_severity_distribution(reviews: List[ReviewComment]) -> Dict[str, int]:
    """
    Returns a count of reviews per severity level.
    """
    dist: Dict[str, int] = defaultdict(int)
    for r in reviews:
        dist[r.severity] += 1
    return dict(dist)
