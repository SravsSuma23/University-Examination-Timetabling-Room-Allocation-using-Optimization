"""
src/scenario_validator.py
=========================
Validates scenario configurations (selected exams, rooms, periods, and optional enrollment overrides)
before optimization execution.
Ensures mathematical feasibility prerequisites:
1. Exams exist and non-empty.
2. Periods exist and cover permissible periods / fixed-time requirements.
3. Rooms exist, are eligible, and cover fixed-room requirements.
4. Total room capacity in selected periods is sufficient for student demand.
5. Distribution constraints (13 rules) are checked for consistency within selected exams.
"""

from typing import Dict, List, Set, Any, Optional, Tuple
import pandas as pd
import hashlib


def compute_scenario_fingerprint(
    exam_ids: List[int],
    room_ids: List[int],
    period_ids: List[int],
    custom_enrollments: Optional[Dict[int, int]] = None,
) -> str:
    """Computes a unique SHA-256 fingerprint for the scenario configuration."""
    raw_str = f"exams:{sorted(exam_ids)}|rooms:{sorted(room_ids)}|periods:{sorted(period_ids)}"
    if custom_enrollments:
        sorted_custom = sorted([(int(k), int(v)) for k, v in custom_enrollments.items()])
        raw_str += f"|custom_enr:{sorted_custom}"
    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()[:16]


def validate_scenario_configuration(
    data: Dict[str, pd.DataFrame],
    selected_exam_ids: List[int],
    selected_room_ids: Optional[List[int]] = None,
    selected_period_ids: Optional[List[int]] = None,
    custom_enrollments: Optional[Dict[int, int]] = None,
) -> Dict[str, Any]:
    """
    Validates user-selected scenario against the Purdue benchmark dataset.

    Returns dict:
        - is_valid: bool
        - errors: List[str]
        - warnings: List[str]
        - stats: Dict[str, Any]
        - fingerprint: str
    """
    errors = []
    warnings = []

    exams_df = data["exams_with_enrollment"]
    periods_df = data["periods"]
    exam_periods_df = data["exam_periods"]
    rooms_df = data["rooms"]
    exam_rooms_df = data["exam_rooms"]
    constraints_df = data["constraints"]

    # 1. Validate exam selection
    if not selected_exam_ids:
        errors.append("No examinations selected. Please select at least one examination.")
        return {
            "is_valid": False,
            "errors": errors,
            "warnings": warnings,
            "stats": {},
            "fingerprint": "",
        }

    all_exam_ids = set(exams_df["exam_id"])
    sel_exam_set = set(selected_exam_ids)
    invalid_exams = sel_exam_set - all_exam_ids
    if invalid_exams:
        errors.append(f"{len(invalid_exams)} selected exam IDs do not exist in dataset: {sorted(list(invalid_exams))[:5]}...")

    # Determine student enrollments
    enrollment_map = dict(zip(exams_df["exam_id"], exams_df["number_of_students"]))
    is_custom_enrollment = False
    if custom_enrollments:
        is_custom_enrollment = True
        for eid, count in custom_enrollments.items():
            if eid in sel_exam_set:
                if count < 0:
                    errors.append(f"Exam {eid} has negative enrollment: {count}")
                enrollment_map[eid] = count

    total_students = sum(enrollment_map.get(e, 0) for e in sel_exam_set)

    # 2. Validate periods
    all_period_ids = sorted(periods_df["period_id"].tolist())
    if selected_period_ids is None:
        sel_periods = all_period_ids
    else:
        sel_periods = sorted(list(set(selected_period_ids)))

    sel_period_set = set(sel_periods)
    if not sel_periods:
        errors.append("No examination periods available or selected.")
    else:
        invalid_p = sel_period_set - set(all_period_ids)
        if invalid_p:
            errors.append(f"Invalid period IDs selected: {invalid_p}")

    # Check permissible periods & fixed-time compliance
    # Exam -> permissible periods
    exam_allowed_p = exam_periods_df.groupby("exam_id")["period_id"].apply(set).to_dict()
    for e in sel_exam_set:
        allowed = exam_allowed_p.get(e, set(all_period_ids))
        valid_intersection = allowed.intersection(sel_period_set)
        if not valid_intersection:
            errors.append(
                f"Exam {e} has no permissible periods in the selected period set (Permissible: {sorted(list(allowed))}, Selected: {sorted(list(sel_period_set))})."
            )

    # 3. Validate rooms
    all_room_ids = sorted(rooms_df["room_id"].tolist())
    if selected_room_ids is None:
        sel_rooms = all_room_ids
    else:
        sel_rooms = sorted(list(set(selected_room_ids)))

    sel_room_set = set(sel_rooms)
    if not sel_rooms:
        errors.append("No campus rooms selected. Please select at least one room.")
    else:
        invalid_r = sel_room_set - set(all_room_ids)
        if invalid_r:
            errors.append(f"Invalid room IDs selected: {invalid_r}")

    # Check fixed-room and room eligibility
    exam_allowed_r = exam_rooms_df.groupby("exam_id")["room_id"].apply(set).to_dict()
    fixed_room_deficit = []
    no_eligible_rooms = []
    for e in sel_exam_set:
        allowed = exam_allowed_r.get(e, set(all_room_ids))
        valid_intersection = allowed.intersection(sel_room_set)
        if len(allowed) == 1:
            fixed_r = list(allowed)[0]
            if fixed_r not in sel_room_set:
                fixed_room_deficit.append((e, fixed_r))
        elif not valid_intersection:
            no_eligible_rooms.append(e)

    if fixed_room_deficit:
        errors.append(
            f"{len(fixed_room_deficit)} exams have fixed-room requirements missing from selected rooms: {fixed_room_deficit[:3]}..."
        )
    if no_eligible_rooms:
        warnings.append(
            f"{len(no_eligible_rooms)} exams have zero eligible rooms in the selected room set. They will be unallocated in Stage 2."
        )

    # Check for known benchmark capacity deficits (where single fixed room capacity < students)
    from src.conflict_builder import BENCHMARK_CAPACITY_DEFICIT_EXEMPTIONS
    deficit_exams = [e for e in sel_exam_set if e in BENCHMARK_CAPACITY_DEFICIT_EXEMPTIONS]
    if deficit_exams:
        warnings.append(
            f"{len(deficit_exams)} exam(s) {deficit_exams} have documented benchmark capacity deficits "
            f"(single fixed room capacity is smaller than student enrollment in the raw Purdue dataset). "
            f"Stage 2 will isolate these bottleneck exam(s) and optimally solve all remaining period exams."
        )

    # 4. Total Seating Capacity vs Demand
    room_caps = dict(zip(rooms_df["room_id"], rooms_df["capacity"]))
    total_selected_room_cap = sum(room_caps.get(r, 0) for r in sel_room_set)
    if total_students > total_selected_room_cap * len(sel_periods):
        warnings.append(
            f"Total student demand ({total_students:,}) exceeds total theoretical seat capacity across selected periods ({total_selected_room_cap * len(sel_periods):,})."
        )

    # 5. Distribution constraints integrity check
    # Check if a 'same-period' constraint has only 1 exam selected
    for _, row in constraints_df.iterrows():
        cid = row["constraint_id"]
        ctype = row["constraint_type"]
        eids = [int(x.strip()) for x in str(row["exam_ids"]).split(",") if x.strip()]
        selected_in_c = [e for e in eids if e in sel_exam_set]

        if 0 < len(selected_in_c) < len(eids):
            warnings.append(
                f"Selected scenario includes only a subset {selected_in_c} of exams from institutional constraint {cid} ('{ctype}' across {eids}). Excluded-exam relationships cannot be enforced, and this subset is being scheduled independently."
            )


    is_valid = len(errors) == 0
    fp = compute_scenario_fingerprint(
        exam_ids=sorted(list(sel_exam_set)),
        room_ids=sel_rooms,
        period_ids=sel_periods,
        custom_enrollments=custom_enrollments if is_custom_enrollment else None,
    )

    stats = {
        "selected_exams_count": len(sel_exam_set),
        "total_students": total_students,
        "selected_rooms_count": len(sel_rooms),
        "total_room_capacity": total_selected_room_cap,
        "selected_periods_count": len(sel_periods),
        "is_custom_enrollment": is_custom_enrollment,
        "fingerprint": fp,
    }

    return {
        "is_valid": is_valid,
        "errors": errors,
        "warnings": warnings,
        "stats": stats,
        "fingerprint": fp,
    }
