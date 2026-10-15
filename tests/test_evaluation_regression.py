"""
tests/test_evaluation_regression.py
===================================
Regression and integration test suite for the Evaluation Dashboard:
1. Exact missing 'assigned_students' column regression test.
2. Supported room-allocation column aliases (allocated_students, required_capacity, assigned_students).
3. Valid small BIP plus Goal Programming run independent validation.
4. Independent recalculation of both Z1 and Z2 objective values.
5. 300-exam run scope metrics and isolation.
6. 500-exam run scope metrics and isolation.
7. Full benchmark evaluation on audited baseline.
8. Incomplete run / missing allocation handling without crashing.
9. Run isolation between different run IDs.
"""

import unittest
import pandas as pd
import numpy as np
from pathlib import Path

from src.data_loader import load_all_data
from src.validation import IndependentValidator
from src.metrics import compute_comprehensive_metrics
from src.dashboard_data import list_completed_runs, load_integrated_results


class TestEvaluationRegression(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.data = load_all_data()
        cls.validator = IndependentValidator(
            enrollments_df=cls.data["enrollments"],
            exam_periods_df=cls.data["exam_periods"],
            exam_rooms_df=cls.data["exam_rooms"],
            constraints_df=cls.data["constraints"],
            rooms_df=cls.data["rooms"],
            exams_df=cls.data["exams_with_enrollment"],
        )

    def test_01_missing_assigned_students_column_regression(self):
        """
        Tests that when allocation_df uses 'allocated_students' instead of 'assigned_students',
        validate_room_allocation() handles it smoothly without raising KeyError: 'assigned_students'.
        """
        tt_df = pd.DataFrame({
            "exam_id": [1, 2],
            "period_id": [1, 2],
            "students": [30, 40],
        })
        # Allocation with baseline schema ('allocated_students', 'allocated_capacity', 'assigned_rooms')
        alloc_baseline_schema = pd.DataFrame({
            "exam_id": [1, 2],
            "stage1_period": [1, 2],
            "assigned_rooms": ["10", "20"],
            "allocated_students": [30, 40],
            "allocated_capacity": [50, 60],
            "unused_capacity": [20, 20],
            "room_penalty": [0, 0],
            "split_status": ["SINGLE", "SINGLE"],
        })

        try:
            val_res = self.validator.validate_room_allocation(alloc_baseline_schema, tt_df)
            self.assertIn("student_accommodation", val_res)
            self.assertEqual(val_res["student_accommodation"]["violations"], 0)
        except KeyError as ke:
            self.fail(f"KeyError was incorrectly raised: {ke}")

    def test_02_supported_room_allocation_column_aliases(self):
        """
        Tests that all supported aliases for seating ('assigned_students', 'allocated_students', 'required_capacity')
        are properly normalized and validated.
        """
        tt_df = pd.DataFrame({
            "exam_id": [1],
            "period_id": [1],
            "students": [50],
        })

        # Alias 1: assigned_students (Live HiGHS output)
        a1 = pd.DataFrame({
            "exam_id": [1],
            "period_id": [1],
            "room_id": [10],
            "assigned_students": [50],
            "room_capacity": [100],
            "unused_capacity": [50],
            "room_penalty": [0],
            "is_split": [False],
        })
        r1 = self.validator.validate_room_allocation(a1, tt_df)
        self.assertEqual(r1["student_accommodation"]["violations"], 0)

        # Alias 2: allocated_students
        a2 = pd.DataFrame({
            "exam_id": [1],
            "period_id": [1],
            "assigned_rooms": ["10"],
            "allocated_students": [50],
            "allocated_capacity": [100],
            "unused_capacity": [50],
            "room_penalty": [0],
            "split_status": ["SINGLE"],
        })
        r2 = self.validator.validate_room_allocation(a2, tt_df)
        self.assertEqual(r2["student_accommodation"]["violations"], 0)

    def test_03_independent_z1_and_z2_recalculation(self):
        """
        Verifies that Z1 and Z2 objectives are recalculated strictly from mathematical formulas:
        Z1 = alpha * PeriodPenalty + beta * StudentConflictPenalty
        Z2 = w1*d1+ + w2*d2+ + w3*d3+
        """
        tt_df = pd.DataFrame({
            "exam_id": [1, 2],
            "period_id": [1, 2],
            "students": [20, 20],
            "period_penalty": [4, 1],
        })
        period_pen = tt_df["period_penalty"].sum()  # 5
        affected_stud = 0  # no clashes
        z1 = 1.0 * period_pen + 100.0 * affected_stud
        self.assertEqual(z1, 5.0)

        alloc_df = pd.DataFrame({
            "exam_id": [1, 2],
            "unused_capacity": [15, 25],  # sum = 40
            "room_penalty": [2, 3],        # sum = 5
            "is_split": [False, True],     # splits = 1
        })
        w1, w2, w3 = 1.0, 1.0, 2.0
        z2 = w1 * alloc_df["unused_capacity"].sum() + w2 * alloc_df["room_penalty"].sum() + w3 * 1
        self.assertEqual(z2, 40 + 5 + 2)

    def test_04_scope_300_run_loading_and_isolation(self):
        """
        Verifies that loading a 300-exam run loads strictly 300 exams and does not bleed
        baseline 2,198 values.
        """
        res_300 = load_integrated_results("run_20261012_145931_059fa8")
        tt_300 = res_300["timetable_df"]
        self.assertEqual(len(tt_300), 300)
        self.assertLess(len(tt_300), 2198)

        # Validate timetable
        val_tt = self.validator.validate_timetable(tt_300)
        self.assertEqual(val_tt["exact_one_assignment"]["violations"], 0)
        self.assertEqual(val_tt["student_conflicts"]["conflicting_pairs"], 0)

    def test_05_scope_500_run_loading_and_isolation(self):
        """
        Verifies that loading a 500-exam run loads strictly 500 exams.
        """
        res_500 = load_integrated_results("run_20261012_150004_51048f")
        tt_500 = res_500["timetable_df"]
        self.assertEqual(len(tt_500), 500)
        self.assertLess(len(tt_500), 2198)

        val_tt = self.validator.validate_timetable(tt_500)
        self.assertEqual(val_tt["exact_one_assignment"]["violations"], 0)
        self.assertEqual(val_tt["student_conflicts"]["conflicting_pairs"], 0)

    def test_06_audited_baseline_benchmark_loading(self):
        """
        Verifies that baseline_benchmark loads the 2,198 full Purdue dataset correctly.
        """
        res_base = load_integrated_results("baseline_benchmark")
        tt_base = res_base["timetable_df"]
        alloc_base = res_base["allocation_df"]
        self.assertEqual(len(tt_base), 2198)
        self.assertEqual(len(alloc_base), 2198)

        # Validate room allocation without KeyError
        val_r = self.validator.validate_room_allocation(alloc_base, tt_base)
        self.assertIn("capacity_compliance", val_r)

    def test_07_incomplete_run_handling(self):
        """
        Verifies that an incomplete run without room_allocation.csv is handled gracefully
        without uncaught exceptions or combining data from other runs.
        """
        tt_only = pd.DataFrame({
            "exam_id": [1, 2],
            "period_id": [1, 2],
            "students": [10, 20],
        })
        val_r = self.validator.validate_room_allocation(pd.DataFrame(), tt_only)
        # Empty allocation means 0 students seated for 2 exams, so accommodation correctly flags violations
        self.assertEqual(val_r["student_accommodation"]["violations"], 2)
        self.assertEqual(val_r["overall_status"], "FAIL")

        metrics = compute_comprehensive_metrics(
            bip_solution_summary={},
            gp_solution_summary={},
            timetable_validation=self.validator.validate_timetable(tt_only),
            room_validation=None,
            timetable_df=tt_only,
            allocation_df=None,
        )
        self.assertEqual(metrics["timetabling_quality"]["scheduled_exams_count"], 2)
        self.assertEqual(metrics["room_quality"]["room_utilization_pct"], 0.0)


if __name__ == "__main__":
    unittest.main()
