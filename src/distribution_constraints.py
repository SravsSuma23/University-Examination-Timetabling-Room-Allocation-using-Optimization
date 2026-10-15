"""
distribution_constraints.py
===========================
Parses and enforces institutional distribution constraints from constraints.csv.
Supports:
1. 'same-period': Multiple exams must take place simultaneously.
2. 'different-period': Certain exams cannot be scheduled in the same time slot.
3. 'precedence': Chronological sequencing where Exam A must precede Exam B.
"""

from typing import List, Dict, Any, Tuple
import pandas as pd


class DistributionConstraint:
    def __init__(self, constraint_id: int, constraint_type: str, exam_ids: List[int]):
        self.constraint_id = constraint_id
        self.constraint_type = constraint_type
        self.exam_ids = exam_ids

    def __repr__(self):
        return f"<DistributionConstraint #{self.constraint_id} [{self.constraint_type}] exams={self.exam_ids}>"


def parse_distribution_constraints(constraints_df: pd.DataFrame) -> List[DistributionConstraint]:
    """
    Parses constraints.csv into a structured list of DistributionConstraint objects.
    """
    parsed = []
    for _, row in constraints_df.iterrows():
        cid = int(row["constraint_id"])
        ctype = str(row["constraint_type"]).strip()
        raw_exams = str(row["exam_ids"]).strip()
        if raw_exams and raw_exams.lower() != "nan":
            eids = [int(x.strip()) for x in raw_exams.split(",") if x.strip()]
        else:
            eids = []
        parsed.append(DistributionConstraint(cid, ctype, eids))
    return parsed


def get_distribution_constraints_table(constraints_df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns a comprehensive documentation table explaining each distribution constraint,
    its meaning, affected exams, and mathematical formulation.
    """
    records = []
    for _, row in constraints_df.iterrows():
        cid = int(row["constraint_id"])
        ctype = str(row["constraint_type"]).strip()
        eids_str = str(row["exam_ids"]).strip()
        eids = [int(x.strip()) for x in eids_str.split(",") if x.strip()]

        if ctype == "same-period":
            meaning = f"Exams {eids_str} must be scheduled in the EXACT SAME period."
            math_form = "x[e_i, t] = x[e_j, t]  ∀ t ∈ T, ∀ i, j"
        elif ctype == "different-period":
            if len(eids) >= 2:
                meaning = f"Exams {eids_str} cannot share the same period."
                math_form = "x[e_i, t] + x[e_j, t] ≤ 1  ∀ t ∈ T"
            else:
                meaning = f"Isolated exam rule for Exam {eids_str}."
                math_form = "Redundant / single-exam specification"
        elif ctype == "precedence":
            meaning = f"Exam {eids[0]} must finish BEFORE Exam {eids[1]} begins."
            math_form = "∑ t · x[e_1, t] ≤ ∑ t · x[e_2, t] - 1"
        else:
            meaning = "General institutional rule"
            math_form = "Custom linear relation"

        records.append({
            "Constraint ID": cid,
            "Type": ctype,
            "Affected Exams": eids_str,
            "Number of Exams": len(eids),
            "Operational Meaning": meaning,
            "Mathematical Formulation": math_form,
        })

    return pd.DataFrame(records)


def validate_distribution_constraints(
    timetable_dict: Dict[int, int],
    constraints: List[DistributionConstraint]
) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Independently validates whether a generated timetable satisfies all distribution constraints.
    Returns (all_passed, list_of_violations).
    """
    violations = []
    for c in constraints:
        # Filter exams that are in the timetable
        relevant_exams = [e for e in c.exam_ids if e in timetable_dict]
        
        # If not all exams in this constraint are scheduled, validate scheduled subset
        if len(relevant_exams) < 2:
            continue

        if c.constraint_type == "same-period":
            periods = {timetable_dict[e] for e in relevant_exams}
            if len(periods) > 1:
                violations.append({
                    "constraint_id": c.constraint_id,
                    "type": c.constraint_type,
                    "affected_exams": c.exam_ids,
                    "scheduled_periods": [timetable_dict[e] for e in relevant_exams],
                    "message": f"Exams {relevant_exams} scheduled in different periods: {periods}",
                })

        elif c.constraint_type == "different-period":
            period_counts = {}
            for e in relevant_exams:
                p = timetable_dict[e]
                period_counts.setdefault(p, []).append(e)
            for p, exams in period_counts.items():
                if len(exams) > 1:
                    violations.append({
                        "constraint_id": c.constraint_id,
                        "type": c.constraint_type,
                        "affected_exams": exams,
                        "scheduled_periods": [p],
                        "message": f"Exams {exams} violate different-period rule by sharing period {p}",
                    })

        elif c.constraint_type == "precedence":
            e1, e2 = relevant_exams[0], relevant_exams[1]
            p1, p2 = timetable_dict[e1], timetable_dict[e2]
            if p1 >= p2:
                violations.append({
                    "constraint_id": c.constraint_id,
                    "type": c.constraint_type,
                    "affected_exams": [e1, e2],
                    "scheduled_periods": [p1, p2],
                    "message": f"Precedence violated: Exam {e1} (period {p1}) does not precede Exam {e2} (period {p2})",
                })

    is_valid = len(violations) == 0
    return is_valid, violations
