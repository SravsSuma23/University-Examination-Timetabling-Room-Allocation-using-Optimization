"""
conflict_builder.py
===================
Constructs and analyzes the student examination conflict graph.
Two examinations are in conflict if they share at least one registered student.
Uses an efficient sparse adjacency representation without large dense matrices.
"""

from collections import defaultdict
from typing import Dict, Tuple, List, Set, Any, Optional
import pandas as pd
import numpy as np


# Centralized constant for the three documented dataset-level preassignment overlaps
PREASSIGNMENT_CONFLICT_EXEMPTIONS: Set[Tuple[int, int]] = {
    (708, 720),
    (1037, 1283),
    (1259, 1263),
}

# Centralized constant for documented dataset-level capacity deficit bottlenecks:
# Examinations with strict single-room assignments where room capacity < registered students.
# - Exam 990: 15 students enrolled, strictly restricted to Room 351 (capacity 14, deficit -1).
# - Exam 2171: 77 students enrolled, strictly restricted to Room 312 (capacity 20, deficit -57).
BENCHMARK_CAPACITY_DEFICIT_EXEMPTIONS: Set[int] = {
    990,
    2171,
}


class ConflictGraph:
    """
    Sparse representation of student examination conflicts.
    """

    def __init__(self, enrollments_df: pd.DataFrame, total_exams: int = 2198):
        self.total_exams = total_exams
        self.student_to_exams: Dict[int, List[int]] = defaultdict(list)
        self.exam_to_students: Dict[int, List[int]] = defaultdict(list)
        
        # Raw Conflict pairs: (min(e1, e2), max(e1, e2)) -> shared_count
        self.conflict_pairs: Dict[Tuple[int, int], int] = defaultdict(int)
        
        # Adjacency list: e1 -> list of (e2, shared_count)
        self.adjacency: Dict[int, List[Tuple[int, int]]] = defaultdict(list)
        
        # Conflict degree per exam: exam_id -> degree
        self.degree: Dict[int, int] = defaultdict(int)

        self._build_graph(enrollments_df)

    def _build_graph(self, enrollments_df: pd.DataFrame):
        # 1. Map students to exams
        for student_id, exam_id in zip(enrollments_df["student_id"], enrollments_df["exam_id"]):
            self.student_to_exams[student_id].append(exam_id)
            self.exam_to_students[exam_id].append(student_id)

        # 2. Count pairwise co-enrollments
        for student_id, exams in self.student_to_exams.items():
            k = len(exams)
            if k > 1:
                for i in range(k):
                    for j in range(i + 1, k):
                        e1, e2 = exams[i], exams[j]
                        if e1 != e2:
                            pair = (min(e1, e2), max(e1, e2))
                            self.conflict_pairs[pair] += 1

        # 3. Build adjacency and degree structures
        for (e1, e2), weight in self.conflict_pairs.items():
            self.adjacency[e1].append((e2, weight))
            self.adjacency[e2].append((e1, weight))
            self.degree[e1] += 1
            self.degree[e2] += 1

        # Sort adjacency lists by descending weight
        for e in self.adjacency:
            self.adjacency[e].sort(key=lambda item: item[1], reverse=True)

    def get_summary_statistics(self) -> Dict[str, Any]:
        """Returns macro statistics of the conflict graph."""
        total_pairs = len(self.conflict_pairs)
        total_shared_instances = sum(self.conflict_pairs.values())
        max_deg = max(self.degree.values()) if self.degree else 0
        avg_deg = sum(self.degree.values()) / self.total_exams if self.total_exams > 0 else 0
        zero_conflict_exams = self.total_exams - len(self.degree)

        return {
            "total_conflict_pairs": total_pairs,
            "total_shared_student_instances": total_shared_instances,
            "max_conflict_degree": max_deg,
            "average_conflict_degree": round(avg_deg, 2),
            "zero_conflict_exams": zero_conflict_exams,
            "active_exams_in_conflicts": len(self.degree),
        }

    def get_top_conflicting_exams(self, top_n: int = 20) -> pd.DataFrame:
        """Returns the top N exams ranked by conflict degree."""
        sorted_exams = sorted(self.degree.items(), key=lambda x: x[1], reverse=True)[:top_n]
        records = []
        for rank, (exam_id, deg) in enumerate(sorted_exams, 1):
            records.append({
                "Rank": rank,
                "Exam ID": exam_id,
                "Conflict Degree": deg,
                "Total Students": len(self.exam_to_students[exam_id]),
                "Top Conflicting Partner": self.adjacency[exam_id][0][0] if self.adjacency[exam_id] else None,
                "Max Shared with One Exam": self.adjacency[exam_id][0][1] if self.adjacency[exam_id] else 0,
            })
        return pd.DataFrame(records)

    def get_conflicts_for_exam(self, exam_id: int) -> pd.DataFrame:
        """Returns all conflicting exams and shared student counts for a specific exam."""
        neighbors = self.adjacency.get(exam_id, [])
        records = []
        for other_exam, shared in neighbors:
            records.append({
                "Target Exam": exam_id,
                "Conflicting Exam ID": other_exam,
                "Shared Students": shared,
                "Partner Exam Size": len(self.exam_to_students.get(other_exam, [])),
            })
        return pd.DataFrame(records)

    def get_subgraph_edges(self, exam_ids: Set[int]) -> List[Tuple[int, int, int]]:
        """Returns edge tuples (e1, e2, weight) for a given subset of exam IDs."""
        edges = []
        for (e1, e2), weight in self.conflict_pairs.items():
            if e1 in exam_ids and e2 in exam_ids:
                edges.append((e1, e2, weight))
        return edges

    def get_schedulable_conflict_pairs(self, exam_ids: Optional[Set[int]] = None, exclude_exemptions: bool = False) -> Dict[Tuple[int, int], int]:
        """
        Returns conflict pairs (min(e1, e2), max(e1, e2)) -> shared_student_count.
        Optionally filtered by a subset of active exam IDs.
        Under Option 2, exclude_exemptions defaults to False so all student conflicts are modeled as soft penalties.
        """
        conflicts = {}
        for (e1, e2), weight in self.conflict_pairs.items():
            pair = (min(e1, e2), max(e1, e2))
            if exclude_exemptions and pair in PREASSIGNMENT_CONFLICT_EXEMPTIONS:
                continue
            if exam_ids is None or (e1 in exam_ids and e2 in exam_ids):
                conflicts[pair] = weight
        return conflicts


_CACHED_CONFLICT_GRAPH = None

def get_conflict_graph(enrollments_df: pd.DataFrame, total_exams: int = 2198) -> ConflictGraph:
    """Singleton getter to prevent re-building the graph on Streamlit re-runs."""
    global _CACHED_CONFLICT_GRAPH
    if _CACHED_CONFLICT_GRAPH is None:
        _CACHED_CONFLICT_GRAPH = ConflictGraph(enrollments_df, total_exams)
    return _CACHED_CONFLICT_GRAPH
