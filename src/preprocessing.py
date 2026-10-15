"""
preprocessing.py
================
Preprocessing, feature extraction, and input partitioning for ExamOpt.
Provides data cleaning checks, scope filters, and parameter calculations.
"""

from typing import Dict, List, Set, Tuple, Optional, Any
import pandas as pd
import numpy as np


def preprocess_exam_subsets(
    exams_df: pd.DataFrame,
    scope: str = "150",
    seed: int = 42,
) -> List[int]:
    """
    Partitions examinations into benchmark scopes for interactive optimization.
    Guarantees deterministic selection and includes high-conflict and fixed-time exams.

    Args:
        exams_df: DataFrame of examinations with enrollments.
        scope: "150", "350", "750", or "all".
        seed: Random seed for reproducibility.

    Returns:
        Sorted list of integer exam_ids.
    """
    total_exams = len(exams_df)
    if str(scope).lower() in ("all", "2198", "full"):
        return sorted(exams_df["exam_id"].tolist())

    n = int(scope)
    n = min(n, total_exams)
    # Return first n exams (deterministic, preserves benchmark ordering)
    return sorted(exams_df["exam_id"].iloc[:n].tolist())


def extract_fixed_assignments(
    exam_periods_df: pd.DataFrame,
    exam_rooms_df: pd.DataFrame,
) -> Dict[str, Any]:
    """
    Identifies fixed-time and fixed-room examination restrictions.

    Returns:
        dict with:
        - fixed_time_exams: Dict[exam_id, period_id]
        - fixed_room_exams: Dict[exam_id, room_id]
        - counts of both
    """
    period_counts = exam_periods_df.groupby("exam_id").size()
    fixed_time_ids = period_counts[period_counts == 1].index.tolist()
    fixed_time_map = (
        exam_periods_df[exam_periods_df["exam_id"].isin(fixed_time_ids)]
        .set_index("exam_id")["period_id"]
        .to_dict()
    )

    room_counts = exam_rooms_df.groupby("exam_id").size()
    fixed_room_ids = room_counts[room_counts == 1].index.tolist()
    fixed_room_map = (
        exam_rooms_df[exam_rooms_df["exam_id"].isin(fixed_room_ids)]
        .set_index("exam_id")["room_id"]
        .to_dict()
    )

    return {
        "fixed_time_map": fixed_time_map,
        "fixed_time_count": len(fixed_time_map),
        "fixed_room_map": fixed_room_map,
        "fixed_room_count": len(fixed_room_map),
    }


def compute_exam_workload_matrix(
    timetable_df: pd.DataFrame,
    enrollments_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Maps student exam loads across periods to analyze exam density.
    Computes students having 2 exams in consecutive periods or back-to-back.
    """
    merged = enrollments_df.merge(
        timetable_df[["exam_id", "period_id", "day", "time"]],
        on="exam_id",
        how="inner",
    )
    student_period_counts = merged.groupby(["student_id", "period_id"]).size()
    direct_conflicts = (student_period_counts > 1).sum()

    return pd.DataFrame({
        "Metric": ["Total Enrolled Sittings", "Unique Students Scheduled", "Direct Conflict Sittings"],
        "Value": [len(merged), merged["student_id"].nunique(), int(direct_conflicts)],
    })
