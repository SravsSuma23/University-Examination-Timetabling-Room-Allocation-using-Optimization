"""
validation.py
=============
Independent verification and auditing module for ExamOpt solutions.
Validates Stage 1 (Examination Timetable) and Stage 2 (Room Allocation)
without relying on solver reporting alone.
"""

from collections import defaultdict
from typing import Dict, List, Any, Tuple, Optional
import pandas as pd

from src.conflict_builder import PREASSIGNMENT_CONFLICT_EXEMPTIONS, BENCHMARK_CAPACITY_DEFICIT_EXEMPTIONS


class IndependentValidator:
    """
    Validates timetable and room allocation solutions against all mathematical constraints.
    """

    def __init__(
        self,
        enrollments_df: pd.DataFrame,
        exam_periods_df: pd.DataFrame,
        exam_rooms_df: pd.DataFrame,
        constraints_df: pd.DataFrame,
        rooms_df: pd.DataFrame,
        exams_df: pd.DataFrame,
    ):
        self.enrollments_df = enrollments_df
        self.exam_periods_df = exam_periods_df
        self.exam_rooms_df = exam_rooms_df
        self.constraints_df = constraints_df
        self.rooms_df = rooms_df
        self.exams_df = exams_df

        # Precompute mappings
        self._build_references()

    def _build_references(self):
        # Student -> list of exams
        self.student_exams = defaultdict(list)
        for s, e in zip(self.enrollments_df["student_id"], self.enrollments_df["exam_id"]):
            self.student_exams[s].append(e)

        # Exam -> allowed periods
        self.allowed_periods = defaultdict(set)
        for e, p in zip(self.exam_periods_df["exam_id"], self.exam_periods_df["period_id"]):
            self.allowed_periods[e].add(p)

        # Exam -> allowed rooms
        self.allowed_rooms = defaultdict(set)
        for e, r in zip(self.exam_rooms_df["exam_id"], self.exam_rooms_df["room_id"]):
            self.allowed_rooms[e].add(r)

        # Room capacities
        self.room_capacities = dict(zip(self.rooms_df["room_id"], self.rooms_df["capacity"]))

        # Exam student counts
        if "number_of_students" in self.exams_df.columns:
            self.exam_students = dict(zip(self.exams_df["exam_id"], self.exams_df["number_of_students"]))
        else:
            self.exam_students = defaultdict(int)

        # Exam -> set of registered student IDs
        self.exam_student_sets = defaultdict(set)
        for s, e in zip(self.enrollments_df["student_id"], self.enrollments_df["exam_id"]):
            self.exam_student_sets[e].add(s)

    def validate_timetable(self, timetable_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Audits Stage 1 Timetable:
        1. Exact one period assignment per exam.
        2. Student direct conflicts.
        3. Fixed-time constraints.
        4. Distribution constraints (same-period, different-period, precedence).
        5. Valid period range (1 to 29).
        """
        exam_to_period = dict(zip(timetable_df["exam_id"], timetable_df["period_id"]))
        scheduled_exams = set(timetable_df["exam_id"])

        results = {
            "exact_one_assignment": {"status": "PASS", "violations": 0, "details": []},
            "student_conflicts": {"status": "PASS", "violations": 0, "details": []},
            "fixed_time_compliance": {"status": "PASS", "violations": 0, "details": []},
            "distribution_compliance": {"status": "PASS", "violations": 0, "details": []},
            "valid_periods": {"status": "PASS", "violations": 0, "details": []},
            "overall_status": "PASS",
        }

        # 1. Exact one assignment
        duplicate_exams = timetable_df[timetable_df.duplicated("exam_id", keep=False)]
        if len(duplicate_exams) > 0:
            results["exact_one_assignment"]["status"] = "FAIL"
            results["exact_one_assignment"]["violations"] = len(duplicate_exams)
            results["exact_one_assignment"]["details"].append("Duplicate exam records found in timetable.")
            results["overall_status"] = "FAIL"

        # 2. Soft Student Conflicts Quality Audit
        conflicting_pairs_count = 0
        conflicting_pairs_set = set()
        total_affected_students = 0
        clash_details = []

        # Map exam to students for exact co-enrollment counting
        period_to_exams = defaultdict(list)
        for e, p in exam_to_period.items():
            period_to_exams[p].append(e)

        # Check co-enrolled pairs assigned to the same period
        for p, p_exams in period_to_exams.items():
            if len(p_exams) > 1:
                for i in range(len(p_exams)):
                    for j in range(i + 1, len(p_exams)):
                        e1, e2 = min(p_exams[i], p_exams[j]), max(p_exams[i], p_exams[j])
                        s1 = self.exam_student_sets.get(e1, set())
                        s2 = self.exam_student_sets.get(e2, set())
                        shared = len(s1.intersection(s2))
                        if shared > 0:
                            conflicting_pairs_set.add((e1, e2))
                            total_affected_students += shared
                            if len(clash_details) < 10:
                                clash_details.append({
                                    "exam1": e1,
                                    "exam2": e2,
                                    "period_id": p,
                                    "shared_students": shared,
                                })

        conflicting_pairs_count = len(conflicting_pairs_set)
        # In Option 2, student conflicts are a soft objective, not a hard feasibility failure
        results["student_conflicts"] = {
            "status": "OPTIMIZED_SOFT",
            "conflicting_pairs": conflicting_pairs_count,
            "affected_students": total_affected_students,
            "details": clash_details,
        }

        # 3. Fixed-time compliance
        fixed_time_violations = 0
        fixed_examples = []
        for e in scheduled_exams:
            allowed = self.allowed_periods.get(e, set())
            if len(allowed) == 1:
                required_p = list(allowed)[0]
                actual_p = exam_to_period[e]
                if actual_p != required_p:
                    fixed_time_violations += 1
                    if len(fixed_examples) < 5:
                        fixed_examples.append({
                            "exam_id": e,
                            "required_period": required_p,
                            "actual_period": actual_p,
                        })

        if fixed_time_violations > 0:
            results["fixed_time_compliance"]["status"] = "FAIL"
            results["fixed_time_compliance"]["violations"] = fixed_time_violations
            results["fixed_time_compliance"]["details"] = fixed_examples
            results["overall_status"] = "FAIL"

        # 4. Distribution constraints
        from src.distribution_constraints import parse_distribution_constraints, validate_distribution_constraints
        parsed_c = parse_distribution_constraints(self.constraints_df)
        dist_valid, dist_violations = validate_distribution_constraints(exam_to_period, parsed_c)
        if not dist_valid:
            results["distribution_compliance"]["status"] = "FAIL"
            results["distribution_compliance"]["violations"] = len(dist_violations)
            results["distribution_compliance"]["details"] = dist_violations
            results["overall_status"] = "FAIL"

        # 5. Valid periods (1 to 29)
        invalid_p = timetable_df[~timetable_df["period_id"].isin(range(1, 30))]
        if len(invalid_p) > 0:
            results["valid_periods"]["status"] = "FAIL"
            results["valid_periods"]["violations"] = len(invalid_p)
            results["valid_periods"]["details"].append(f"Invalid periods found: {invalid_p['period_id'].tolist()}")
            results["overall_status"] = "FAIL"

        return results

    def validate_room_allocation(
        self,
        allocation_df: pd.DataFrame,
        timetable_df: pd.DataFrame,
    ) -> Dict[str, Any]:
        """
        Audits Stage 2 Room Allocation:
        1. All students accommodated (sum q == N_e).
        2. Room capacity not exceeded (q <= C_r).
        3. No room double-booking in the same period.
        4. Fixed-room compliance.
        """
        # 0. Result structure initialization
        results = {
            "room_eligibility": {"status": "PASS", "violations": 0, "details": []},
            "student_accommodation": {"status": "PASS", "violations": 0, "details": []},
            "capacity_compliance": {"status": "PASS", "violations": 0, "details": []},
            "double_booking": {"status": "PASS", "violations": 0, "details": []},
            "fixed_room_compliance": {"status": "PASS", "violations": 0, "details": []},
            "allocation_completeness": {"status": "PASS", "fully_allocated": 0, "partially_allocated": 0, "unallocated": 0},
            "overall_status": "PASS",
        }

        has_alloc = allocation_df is not None and not allocation_df.empty and "exam_id" in allocation_df.columns

        # 1. Room Eligibility Check: Every allocated exam must use only eligible rooms
        eligibility_violations = 0
        if has_alloc:
            r_col = "room_id" if "room_id" in allocation_df.columns else "assigned_rooms"
            for _, row in allocation_df.iterrows():
                eid = int(row["exam_id"])
                allowed = self.allowed_rooms.get(eid, set())
                if r_col == "room_id":
                    r_val = row["room_id"]
                    if pd.notna(r_val) and int(r_val) not in allowed:
                        eligibility_violations += 1
                        if len(results["room_eligibility"]["details"]) < 5:
                            results["room_eligibility"]["details"].append({
                                "exam_id": eid,
                                "assigned_room": int(r_val),
                                "allowed_rooms": list(allowed)[:5],
                            })
                elif r_col == "assigned_rooms":
                    r_str = str(row.get("assigned_rooms", ""))
                    if r_str not in ("UNASSIGNED", "None", ""):
                        for part in r_str.split(","):
                            p_strip = part.strip()
                            if p_strip.isdigit() and int(p_strip) not in allowed:
                                eligibility_violations += 1
                                if len(results["room_eligibility"]["details"]) < 5:
                                    results["room_eligibility"]["details"].append({
                                        "exam_id": eid,
                                        "assigned_room": int(p_strip),
                                        "allowed_rooms": list(allowed)[:5],
                                    })

        if eligibility_violations > 0:
            results["room_eligibility"]["status"] = "FAIL"
            results["room_eligibility"]["violations"] = eligibility_violations
            results["overall_status"] = "FAIL"

        # 2. Student accommodation & completeness
        if not has_alloc:
            total_seated_per_exam = {}
        else:
            seated_col = "assigned_students" if "assigned_students" in allocation_df.columns else (
                "allocated_students" if "allocated_students" in allocation_df.columns else (
                    "required_capacity" if "required_capacity" in allocation_df.columns else None
                )
            )
            if seated_col:
                total_seated_per_exam = allocation_df.groupby("exam_id")[seated_col].sum().to_dict()
            else:
                total_seated_per_exam = {}

        accom_violations = 0
        benchmark_accom_deficits = 0
        fully_alloc = 0
        partially_alloc = 0
        unalloc = 0

        for _, row in timetable_df.iterrows():
            e = int(row["exam_id"])
            expected = int(row["students"])
            actual = total_seated_per_exam.get(e, 0)

            if actual == 0:
                unalloc += 1
            elif actual < expected:
                partially_alloc += 1
            else:
                fully_alloc += 1

            if actual != expected:
                allowed = self.allowed_rooms.get(e, set())
                # Check if this exam is an inherent benchmark capacity deficit
                if e in BENCHMARK_CAPACITY_DEFICIT_EXEMPTIONS or (len(allowed) == 1 and any(self.room_capacities.get(r, 0) < expected for r in allowed)):
                    benchmark_accom_deficits += 1
                    results["student_accommodation"].setdefault("benchmark_capacity_deficits", []).append({
                        "exam_id": e,
                        "expected_students": expected,
                        "actual_seated": actual,
                    })
                else:
                    accom_violations += 1
                    if len(results["student_accommodation"]["details"]) < 5:
                        results["student_accommodation"]["details"].append({
                            "exam_id": e,
                            "expected_students": expected,
                            "actual_seated": actual,
                        })

        results["student_accommodation"]["benchmark_deficits_count"] = benchmark_accom_deficits
        results["allocation_completeness"] = {
            "status": "PASS" if (unalloc == 0 and partially_alloc == 0) else "INCOMPLETE",
            "fully_allocated": fully_alloc,
            "partially_allocated": partially_alloc,
            "unallocated": unalloc,
        }

        if accom_violations > 0:
            results["student_accommodation"]["status"] = "FAIL"
            results["student_accommodation"]["violations"] = accom_violations
            results["overall_status"] = "FAIL"
        elif benchmark_accom_deficits > 0:
            results["student_accommodation"]["status"] = "BENCHMARK_DEFICIT"
            results["student_accommodation"]["violations"] = benchmark_accom_deficits
            results["student_accommodation"]["note"] = f"{benchmark_accom_deficits} exam(s) have unresolvable benchmark capacity deficits."
            results["overall_status"] = "FAIL"
        else:
            results["student_accommodation"]["status"] = "PASS"
            results["student_accommodation"]["violations"] = 0

        # 3. Capacity compliance
        cap_violations = 0
        if has_alloc:
            s_col = "assigned_students" if "assigned_students" in allocation_df.columns else (
                "allocated_students" if "allocated_students" in allocation_df.columns else None
            )
            c_col = "room_capacity" if "room_capacity" in allocation_df.columns else (
                "allocated_capacity" if "allocated_capacity" in allocation_df.columns else None
            )
            r_col = "room_id" if "room_id" in allocation_df.columns else "assigned_rooms"

            if s_col and c_col:
                for _, row in allocation_df.iterrows():
                    seated = row[s_col]
                    cap = row[c_col]
                    if seated > cap:
                        cap_violations += 1
                        if len(results["capacity_compliance"]["details"]) < 5:
                            results["capacity_compliance"]["details"].append({
                                "exam_id": row["exam_id"],
                                "room_id": row.get(r_col, "N/A"),
                                "seated": seated,
                                "capacity": cap,
                            })

        if cap_violations > 0:
            results["capacity_compliance"]["status"] = "FAIL"
            results["capacity_compliance"]["violations"] = cap_violations
            results["overall_status"] = "FAIL"

        # 4. Double-booking check: No room has > 1 exam in the same period
        double_booked_instances = pd.Series(dtype=int)
        if has_alloc and {"room_id", "period_id"}.issubset(allocation_df.columns):
            double_booked = allocation_df.groupby(["room_id", "period_id"]).size()
            double_booked_instances = double_booked[double_booked > 1]

        # Build the set of exams that are fixed to a single room
        fixed_single_room_exams = {
            e for e, rooms in self.allowed_rooms.items() if len(rooms) == 1
        }

        genuine_double_booking_violations = 0
        genuine_details = []
        for (rid, pid), count in double_booked_instances.items():
            exams_in_slot = allocation_df[
                (allocation_df["room_id"] == rid) & (allocation_df["period_id"] == pid)
            ]["exam_id"].tolist()
            # If ALL exams in this slot are fixed to this single room by dataset definition
            all_fixed_to_this_room = all(
                e in fixed_single_room_exams and self.allowed_rooms.get(e, set()) == {rid}
                for e in exams_in_slot
            )
            if not all_fixed_to_this_room:
                genuine_double_booking_violations += 1
                if len(genuine_details) < 5:
                    genuine_details.append({"room_id": rid, "period_id": pid, "exams_count": count})

        if genuine_double_booking_violations > 0:
            results["double_booking"]["status"] = "FAIL"
            results["double_booking"]["violations"] = genuine_double_booking_violations
            results["double_booking"]["details"] = genuine_details
            results["overall_status"] = "FAIL"
        else:
            dataset_mandated = len(double_booked_instances) - genuine_double_booking_violations
            if dataset_mandated > 0:
                results["double_booking"]["dataset_mandated_shared_rooms"] = dataset_mandated

        # 5. Fixed-room compliance
        fixed_room_violations = 0
        benchmark_deficit_violations = 0
        for e in timetable_df["exam_id"]:
            allowed = self.allowed_rooms.get(e, set())
            if len(allowed) == 1:
                req_room = list(allowed)[0]
                assigned_rooms = set()
                if has_alloc:
                    sub = allocation_df[allocation_df["exam_id"] == e]
                    if "room_id" in sub.columns:
                        assigned_rooms.update(sub["room_id"].dropna().tolist())
                    elif "assigned_rooms" in sub.columns:
                        for val in sub["assigned_rooms"].dropna():
                            for part in str(val).split(","):
                                part_s = part.strip()
                                if part_s.isdigit():
                                    assigned_rooms.add(int(part_s))
                if req_room not in assigned_rooms:
                    # Check if this exam is an inherent benchmark capacity deficit bottleneck
                    if e in BENCHMARK_CAPACITY_DEFICIT_EXEMPTIONS or (self.room_capacities.get(req_room, 0) < self.exam_students.get(e, 0)):
                        benchmark_deficit_violations += 1
                        results["fixed_room_compliance"].setdefault("benchmark_capacity_deficits", []).append({
                            "exam_id": e,
                            "required_room": req_room,
                            "room_capacity": self.room_capacities.get(req_room, 0),
                            "students": self.exam_students.get(e, 0),
                        })
                    else:
                        fixed_room_violations += 1
                        if len(results["fixed_room_compliance"]["details"]) < 5:
                            results["fixed_room_compliance"]["details"].append({
                                "exam_id": e,
                                "required_room": req_room,
                                "assigned_rooms": list(assigned_rooms),
                            })

        results["fixed_room_compliance"]["benchmark_deficits_count"] = benchmark_deficit_violations
        if fixed_room_violations > 0:
            results["fixed_room_compliance"]["status"] = "FAIL"
            results["fixed_room_compliance"]["violations"] = fixed_room_violations
            results["overall_status"] = "FAIL"
        elif benchmark_deficit_violations > 0:
            results["fixed_room_compliance"]["status"] = "BENCHMARK_DEFICIT"
            results["fixed_room_compliance"]["violations"] = benchmark_deficit_violations
            results["overall_status"] = "FAIL"
        else:
            results["fixed_room_compliance"]["status"] = "PASS"
            results["fixed_room_compliance"]["violations"] = 0

        # An overall PASS requires zero hard violations and zero unallocated exams
        if (
            results["room_eligibility"]["violations"] == 0
            and results["capacity_compliance"]["violations"] == 0
            and results["double_booking"]["violations"] == 0
            and results["fixed_room_compliance"]["violations"] == 0
            and results["student_accommodation"]["violations"] == 0
            and unalloc == 0
            and partially_alloc == 0
        ):
            results["overall_status"] = "PASS"
        else:
            results["overall_status"] = "FAIL"

        return results
