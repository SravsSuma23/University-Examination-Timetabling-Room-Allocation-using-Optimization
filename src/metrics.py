"""
metrics.py
==========
Computes the four pillars of evaluation metrics specified in ExamOpt_Presentation.pdf:
1. FEASIBILITY (Direct conflicts, Hard constraint violations, Room capacity violations)
2. TIMETABLING QUALITY (Period penalty, Objective value)
3. ROOM QUALITY (Room utilization, Unused capacity, Room penalty, Room splits)
4. COMPUTATIONAL PERFORMANCE (Solver runtime, Model dimensions, Status)
"""

from typing import Dict, Any, Optional
import pandas as pd


def compute_comprehensive_metrics(
    bip_solution_summary: Dict[str, Any],
    gp_solution_summary: Optional[Dict[str, Any]],
    timetable_validation: Dict[str, Any],
    room_validation: Optional[Dict[str, Any]],
    timetable_df: pd.DataFrame,
    allocation_df: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    """
    Consolidates and computes all official performance evaluation metrics.
    """
    bip_solution_summary = bip_solution_summary or {}
    gp_solution_summary = gp_solution_summary or {}

    # 1. Feasibility
    direct_conflicts = timetable_validation.get("student_conflicts", {}).get("violations", 0)
    preassigned_overlaps = timetable_validation.get("dataset_preassignment_overlaps", {}).get("count", 0)
    fixed_time_viol = timetable_validation.get("fixed_time_compliance", {}).get("violations", 0)
    dist_viol = timetable_validation.get("distribution_compliance", {}).get("violations", 0)
    hard_viol = fixed_time_viol + dist_viol

    room_cap_viol = 0
    double_book_viol = 0
    if room_validation is not None:
        room_cap_viol = room_validation.get("capacity_compliance", {}).get("violations", 0)
        double_book_viol = room_validation.get("double_booking", {}).get("violations", 0)
        hard_viol += (double_book_viol + room_validation.get("fixed_room_compliance", {}).get("violations", 0))

    # 2. Timetabling Quality
    period_penalty_total = int(timetable_df["period_penalty"].sum()) if "period_penalty" in timetable_df else 0
    bip_obj = bip_solution_summary.get("objective_value", 0.0)

    # 3. Room Quality
    room_utilization_pct = 0.0
    unused_capacity_total = 0
    room_penalty_total = 0
    room_splits_total = 0
    gp_obj = 0.0

    if allocation_df is not None and not allocation_df.empty:
        s_col = "assigned_students" if "assigned_students" in allocation_df.columns else (
            "allocated_students" if "allocated_students" in allocation_df.columns else (
                "required_capacity" if "required_capacity" in allocation_df.columns else None
            )
        )
        c_col = "room_capacity" if "room_capacity" in allocation_df.columns else (
            "allocated_capacity" if "allocated_capacity" in allocation_df.columns else None
        )
        total_seated = allocation_df[s_col].sum() if s_col else 0
        total_cap = allocation_df[c_col].sum() if c_col else 0
        room_utilization_pct = round((total_seated / total_cap * 100.0), 2) if total_cap > 0 else 0.0
        
        unused_capacity_total = int(allocation_df["unused_capacity"].sum()) if "unused_capacity" in allocation_df.columns else 0
        room_penalty_total = int(allocation_df["room_penalty"].sum()) if "room_penalty" in allocation_df.columns else 0
        
        if "is_split" in allocation_df.columns:
            room_splits_total = int(allocation_df[allocation_df["is_split"]]["exam_id"].nunique())
        elif "split_status" in allocation_df.columns:
            room_splits_total = int((allocation_df["split_status"] == "SPLIT").sum())
        elif "rooms_used" in allocation_df.columns:
            room_splits_total = int((allocation_df["rooms_used"] > 1).sum())

        if gp_solution_summary:
            gp_obj = gp_solution_summary.get("objective_value", 0.0)

    # 4. Computational
    bip_runtime = bip_solution_summary.get("runtime", 0.0)
    gp_runtime = gp_solution_summary.get("runtime", 0.0) if gp_solution_summary else 0.0
    total_runtime = round(bip_runtime + gp_runtime, 2)

    return {
        "feasibility": {
            "enforced_direct_conflicts": direct_conflicts,
            "documented_preassignment_overlaps": preassigned_overlaps,
            "hard_constraint_violations": hard_viol,
            "room_capacity_violations": room_cap_viol,
            "double_booking_violations": double_book_viol,
            "overall_status": "FEASIBLE" if (direct_conflicts == 0 and hard_viol == 0 and room_cap_viol == 0) else "PENALIZED/VIOLATED",
        },
        "timetabling_quality": {
            "period_penalty": period_penalty_total,
            "bip_objective_value": bip_obj,
            "scheduled_exams_count": len(timetable_df),
        },
        "room_quality": {
            "room_utilization_pct": room_utilization_pct,
            "unused_capacity": unused_capacity_total,
            "room_penalty": room_penalty_total,
            "room_splits": room_splits_total,
            "gp_objective_value": gp_obj,
        },
        "computational": {
            "bip_runtime_seconds": bip_runtime,
            "gp_runtime_seconds": gp_runtime,
            "total_runtime_seconds": total_runtime,
            "bip_status": bip_solution_summary.get("status", "UNKNOWN"),
            "gp_status": gp_solution_summary.get("status", "UNKNOWN") if gp_solution_summary else "N/A",
            "bip_variables": bip_solution_summary.get("num_variables", 0),
            "bip_constraints": bip_solution_summary.get("num_constraints", 0),
        },
    }
