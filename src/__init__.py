"""
ExamOpt — University Examination Timetabling and Room Allocation
Operations Research Project Package
"""

from src.data_loader import (
    load_all_data,
    get_dataset_validation_summary,
    get_data_dictionary,
    verify_dataset_referential_integrity,
)
from src.conflict_builder import ConflictGraph, get_conflict_graph
from src.distribution_constraints import parse_distribution_constraints, DistributionConstraint
from src.bip_model import BIPTimetablingModel
from src.goal_programming import GoalProgrammingRoomAllocationModel
from src.validation import IndependentValidator
from src.metrics import compute_comprehensive_metrics
from src.preprocessing import preprocess_exam_subsets, extract_fixed_assignments

__version__ = "1.0.0"

__all__ = [
    "load_all_data",
    "get_dataset_validation_summary",
    "get_data_dictionary",
    "verify_dataset_referential_integrity",
    "ConflictGraph",
    "get_conflict_graph",
    "parse_distribution_constraints",
    "DistributionConstraint",
    "BIPTimetablingModel",
    "GoalProgrammingRoomAllocationModel",
    "IndependentValidator",
    "compute_comprehensive_metrics",
    "preprocess_exam_subsets",
    "extract_fixed_assignments",
]
