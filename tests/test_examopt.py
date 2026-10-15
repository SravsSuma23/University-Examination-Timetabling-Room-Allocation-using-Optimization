"""
test_examopt.py
===============
Automated test suite for ExamOpt Operations Research system.
Validates data loading, conflict graph logic, BIP model, Goal Programming,
validator rules, and metric calculations.
"""

import unittest
from pathlib import Path
import pandas as pd
import numpy as np

from src.data_loader import load_all_data, get_dataset_validation_summary
from src.conflict_builder import ConflictGraph
from src.distribution_constraints import parse_distribution_constraints, validate_distribution_constraints
from src.bip_model import BIPTimetablingModel
from src.goal_programming import GoalProgrammingRoomAllocationModel
from src.validation import IndependentValidator
from src.metrics import compute_comprehensive_metrics


class TestExamOptPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_all_data()

    def test_01_dataset_shapes_and_counts(self):
        """Verify all 11 files loaded and match benchmark dimensions."""
        self.assertEqual(len(self.data["exams"]), 2198)
        self.assertEqual(len(self.data["students"]), 34988)
        self.assertEqual(len(self.data["enrollments"]), 130539)
        self.assertEqual(len(self.data["periods"]), 29)
        self.assertEqual(len(self.data["rooms"]), 524)
        self.assertEqual(len(self.data["constraints"]), 13)

    def test_02_validation_summary_matches_pdf(self):
        """Verify validation summary produces 10 rows all matching PDF."""
        val_df = get_dataset_validation_summary(self.data)
        self.assertEqual(len(val_df), 10)
        self.assertTrue((val_df["Status"] == "MATCH").all())

    def test_03_conflict_graph_properties(self):
        """Verify sparse conflict graph calculations."""
        cg = ConflictGraph(self.data["enrollments"], total_exams=len(self.data["exams"]))
        stats = cg.get_summary_statistics()
        self.assertEqual(stats["total_conflict_pairs"], 72066)
        self.assertEqual(stats["max_conflict_degree"], 784)
        self.assertAlmostEqual(stats["average_conflict_degree"], 65.57, places=1)

    def test_04_distribution_constraints_parsing(self):
        """Verify distribution constraints parser."""
        parsed = parse_distribution_constraints(self.data["constraints"])
        self.assertEqual(len(parsed), 13)
        types = [c.constraint_type for c in parsed]
        self.assertIn("same-period", types)
        self.assertIn("different-period", types)
        self.assertIn("precedence", types)

    def test_05_bip_timetabling_small_scope(self):
        """Verify BIP timetabling solver enforces hard constraints and minimizes soft conflicts."""
        sample_exams = sorted(self.data["exams"]["exam_id"].head(25).tolist())
        bip = BIPTimetablingModel(
            exams_df=self.data["exams_with_enrollment"],
            periods_df=self.data["periods"],
            exam_periods_df=self.data["exam_periods"],
            enrollments_df=self.data["enrollments"],
            constraints_df=self.data["constraints"],
            exam_subset=sample_exams,
        )
        res = bip.solve(time_limit_seconds=10)
        self.assertIn(res["status"], ["OPTIMAL", "FEASIBLE"])
        self.assertIsNotNone(bip.timetable_df)
        self.assertEqual(len(bip.timetable_df), 25)
        self.assertIn("period_penalty", res)
        self.assertIn("conflict_penalty", res)

        # Validate independently
        val = IndependentValidator(
            enrollments_df=self.data["enrollments"],
            exam_periods_df=self.data["exam_periods"],
            exam_rooms_df=self.data["exam_rooms"],
            constraints_df=self.data["constraints"],
            rooms_df=self.data["rooms"],
            exams_df=self.data["exams_with_enrollment"],
        )
        tt_val = val.validate_timetable(bip.timetable_df)
        self.assertEqual(tt_val["overall_status"], "PASS")
        self.assertEqual(tt_val["exact_one_assignment"]["violations"], 0)
        self.assertEqual(tt_val["fixed_time_compliance"]["violations"], 0)
        self.assertEqual(tt_val["distribution_compliance"]["violations"], 0)
        self.assertEqual(tt_val["valid_periods"]["violations"], 0)
        self.assertIn("student_conflicts", tt_val)

    def test_06_goal_programming_room_allocation(self):
        """Verify Stage 2 Goal Programming room allocation."""
        sample_exams = sorted(self.data["exams"]["exam_id"].head(15).tolist())
        bip = BIPTimetablingModel(
            exams_df=self.data["exams_with_enrollment"],
            periods_df=self.data["periods"],
            exam_periods_df=self.data["exam_periods"],
            enrollments_df=self.data["enrollments"],
            constraints_df=self.data["constraints"],
            exam_subset=sample_exams,
        )
        bip.solve(time_limit_seconds=10)

        # Filter candidate rooms to 30 eligible rooms to stay within evaluation license size limits
        top_rooms = self.data["rooms"].head(30)
        top_er = self.data["exam_rooms"][self.data["exam_rooms"]["room_id"].isin(top_rooms["room_id"])]

        gp = GoalProgrammingRoomAllocationModel(
            timetable_df=bip.timetable_df,
            rooms_df=top_rooms,
            exam_rooms_df=top_er,
            room_period_penalties_df=self.data["room_period_penalties"],
            w1=1.0, w2=1.0, w3=1.0,
        )
        gp_res = gp.solve(time_limit_per_period=5)
        self.assertIn(gp_res["status"], ["OPTIMAL", "FEASIBLE"])
        self.assertIsNotNone(gp.allocation_df)
        self.assertGreater(len(gp.allocation_df), 0)

    def test_07_comprehensive_metrics_computation(self):
        """Verify metric calculation structure."""
        bip_res = {"status": "OPTIMAL", "objective_value": 0.0, "runtime": 1.2, "num_variables": 100, "num_constraints": 200}
        gp_res = {"status": "OPTIMAL", "objective_value": 50.0, "runtime": 2.5}
        tt_val = {"student_conflicts": {"violations": 0}, "fixed_time_compliance": {"violations": 0}, "distribution_compliance": {"violations": 0}}
        room_val = {"capacity_compliance": {"violations": 0}, "double_booking": {"violations": 0}, "fixed_room_compliance": {"violations": 0}}
        tt_df = pd.DataFrame([{"exam_id": 1, "period_penalty": 0}])
        alloc_df = pd.DataFrame([{
            "assigned_students": 50,
            "room_capacity": 60,
            "unused_capacity": 10,
            "room_penalty": 2,
            "is_split": False,
            "exam_id": 1,
        }])
        metrics = compute_comprehensive_metrics(bip_res, gp_res, tt_val, room_val, tt_df, alloc_df)
        self.assertEqual(metrics["feasibility"]["overall_status"], "FEASIBLE")
        self.assertAlmostEqual(metrics["room_quality"]["room_utilization_pct"], 83.33, places=1)

    def test_08_referential_integrity(self):
        """Verify cross-table referential integrity across all 11 CSV files."""
        from src.data_loader import verify_dataset_referential_integrity
        integrity_df = verify_dataset_referential_integrity(self.data)
        self.assertEqual(len(integrity_df), 9)
        self.assertTrue((integrity_df["Orphan Foreign Keys"] == 0).all())
        self.assertTrue((integrity_df["Status"] == "PASS").all())


if __name__ == "__main__":
    unittest.main()
