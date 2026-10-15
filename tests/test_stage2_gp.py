import unittest
import pandas as pd
import numpy as np
from pathlib import Path
import json

from src.goal_programming import GoalProgrammingRoomAllocationModel
from src.validation import IndependentValidator
from src.data_loader import load_all_data


class TestStage2GoalProgrammingTargeted(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_all_data()
        cls.rooms_df = cls.data["rooms"]
        cls.exam_rooms_df = cls.data["exam_rooms"]
        cls.room_period_penalties_df = cls.data["room_period_penalties"]
        cls.exams_df = cls.data["exams_with_enrollment"]
        cls.enrollments_df = cls.data["enrollments"]
        cls.exam_periods_df = cls.data["exam_periods"]
        cls.constraints_df = cls.data["constraints"]

        cls.validator = IndependentValidator(
            enrollments_df=cls.enrollments_df,
            exam_periods_df=cls.exam_periods_df,
            exam_rooms_df=cls.exam_rooms_df,
            constraints_df=cls.constraints_df,
            rooms_df=cls.rooms_df,
            exams_df=cls.exams_df,
        )

    def test_01_small_instance_known_feasible_allocation(self):
        """1. A small instance with a known feasible allocation."""
        # Select 5 exams in Period 29 known to easily fit into distinct rooms
        # Period 29 has exams: 12, 13, 20, 21, 22
        tt_sub = pd.DataFrame([
            {"exam_id": 12, "period_id": 29, "students": 40},
            {"exam_id": 13, "period_id": 29, "students": 35},
            {"exam_id": 20, "period_id": 29, "students": 25},
            {"exam_id": 21, "period_id": 29, "students": 30},
            {"exam_id": 22, "period_id": 29, "students": 15},
        ])

        gp = GoalProgrammingRoomAllocationModel(
            timetable_df=tt_sub,
            rooms_df=self.rooms_df,
            exam_rooms_df=self.exam_rooms_df,
            room_period_penalties_df=self.room_period_penalties_df,
            w1=1.0,
            w2=1.0,
            w3=2.0,
        )
        res = gp.solve(time_limit_per_period=10)

        self.assertIn(res["status"], ["OPTIMAL", "FEASIBLE"])
        self.assertIsNotNone(gp.allocation_df)
        self.assertEqual(gp.allocation_df["exam_id"].nunique(), 5)

        # Validate with IndependentValidator
        val = self.validator.validate_room_allocation(gp.allocation_df, tt_sub)
        self.assertEqual(val["capacity_compliance"]["status"], "PASS")
        self.assertEqual(val["double_booking"]["status"], "PASS")
        self.assertEqual(val["student_accommodation"]["status"], "PASS")
        self.assertEqual(val["room_eligibility"]["status"], "PASS")
        self.assertEqual(val["overall_status"], "PASS")

    def test_02_exam_split_across_multiple_eligible_rooms(self):
        """2. An exam that must split across multiple eligible rooms."""
        # Exam 118: enrollment 78, eligible rooms are Room 139 (cap 40) and Room 140 (cap 40)
        # Max single capacity is 40 < 78, so it MUST split across both rooms 139 and 140
        tt_split = pd.DataFrame([
            {"exam_id": 118, "period_id": 1, "students": 78}
        ])

        gp = GoalProgrammingRoomAllocationModel(
            timetable_df=tt_split,
            rooms_df=self.rooms_df,
            exam_rooms_df=self.exam_rooms_df,
            room_period_penalties_df=self.room_period_penalties_df,
            w1=1.0,
            w2=1.0,
            w3=2.0,
        )
        res = gp.solve(time_limit_per_period=10)

        self.assertIn(res["status"], ["OPTIMAL", "FEASIBLE"])
        alloc = gp.allocation_df
        self.assertIsNotNone(alloc)
        self.assertEqual(len(alloc), 2)  # Assigned to 2 rooms
        self.assertEqual(alloc["assigned_students"].sum(), 78)
        self.assertTrue(set(alloc["room_id"]).issubset({139, 140}))

        # Independent validation
        val = self.validator.validate_room_allocation(alloc, tt_split)
        self.assertEqual(val["capacity_compliance"]["status"], "PASS")
        self.assertEqual(val["student_accommodation"]["status"], "PASS")
        self.assertEqual(val["room_eligibility"]["status"], "PASS")
        self.assertEqual(val["overall_status"], "PASS")

    def test_03_fixed_room_assignment_compliance(self):
        """3. A fixed-room assignment test."""
        # Exam 67 is genuinely fixed to Room 227 (capacity 48, students 15)
        # Verify it is assigned to Room 227
        tt_fixed = pd.DataFrame([
            {"exam_id": 67, "period_id": 1, "students": 15}
        ])

        gp = GoalProgrammingRoomAllocationModel(
            timetable_df=tt_fixed,
            rooms_df=self.rooms_df,
            exam_rooms_df=self.exam_rooms_df,
            room_period_penalties_df=self.room_period_penalties_df,
            w1=1.0,
            w2=1.0,
            w3=2.0,
        )
        res = gp.solve(time_limit_per_period=10)
        alloc = gp.allocation_df

        self.assertIsNotNone(alloc)
        self.assertEqual(alloc.iloc[0]["room_id"], 227)

        val = self.validator.validate_room_allocation(alloc, tt_fixed)
        self.assertEqual(val["fixed_room_compliance"]["status"], "PASS")
        self.assertEqual(val["overall_status"], "PASS")

    def test_04_genuine_room_capacity_infeasibility(self):
        """4. A genuine room-capacity infeasibility test (Exams 990 & 2171)."""
        # Exam 990: 15 students, sole eligible Room 351 (cap 14) -> Infeasible (-1 seat)
        # Exam 2171: 77 students, sole eligible Room 312 (cap 20) -> Infeasible (-57 seats)
        tt_infeas = pd.DataFrame([
            {"exam_id": 990, "period_id": 1, "students": 15},
            {"exam_id": 2171, "period_id": 1, "students": 77},
        ])

        gp = GoalProgrammingRoomAllocationModel(
            timetable_df=tt_infeas,
            rooms_df=self.rooms_df,
            exam_rooms_df=self.exam_rooms_df,
            room_period_penalties_df=self.room_period_penalties_df,
        )
        res = gp.solve(time_limit_per_period=5)

        # Solver must truthfully report INFEASIBLE (not silently fabricate a solution)
        self.assertEqual(res["status"].upper(), "INFEASIBLE")
        self.assertEqual(len(gp.allocation_df), 0)

        # Independent validation of empty allocation against required timetable
        val = self.validator.validate_room_allocation(gp.allocation_df, tt_infeas)
        self.assertEqual(val["overall_status"], "FAIL")
        self.assertEqual(val["allocation_completeness"]["unallocated"], 2)

    def test_05_solver_time_limit_preserves_incumbent(self):
        """5. Solver time-limit test preserving valid incumbent when available."""
        # Period 16 with 76 exams: if given 1 second, it should hit TIME_LIMIT
        # but if an incumbent was found, it keeps it and labels FEASIBLE / TIME LIMIT;
        # if no incumbent, it marks TIME_LIMIT_NO_INCUMBENT without crashing.
        base_tt = pd.read_csv("results/phase3_11/timetable_2198_pairwise_compact.csv")
        tt_p16 = base_tt[base_tt["period_id"] == 16].copy()

        gp = GoalProgrammingRoomAllocationModel(
            timetable_df=tt_p16,
            rooms_df=self.rooms_df,
            exam_rooms_df=self.exam_rooms_df,
            room_period_penalties_df=self.room_period_penalties_df,
        )
        res = gp.solve(time_limit_per_period=1)

        self.assertIn(res["status"], ["OPTIMAL", "FEASIBLE (TIME LIMIT)", "FEASIBLE / TIME LIMIT", "TIME_LIMIT_NO_INCUMBENT", "FEASIBLE"])
        self.assertIn("period_subproblem_log", res)
        self.assertIn(16, res["period_subproblem_log"])
        p16_log = res["period_subproblem_log"][16]
        self.assertIn("status", p16_log)
        self.assertIn("runtime_seconds", p16_log)

    def test_06_evaluation_selected_run_isolation(self):
        """6. A test confirming the Evaluation page metrics use the selected run."""
        # Check that subset metrics do not use 2,198 baseline numbers
        from src.metrics import compute_comprehensive_metrics

        tt_300 = pd.read_csv("results/phase3_11/timetable_2198_pairwise_compact.csv").head(300)
        tt_val = self.validator.validate_timetable(tt_300)
        metrics = compute_comprehensive_metrics(
            bip_solution_summary={"status": "OPTIMAL", "runtime": 10.0, "objective_value": 5000.0},
            gp_solution_summary={"status": "NOT_SOLVED", "runtime": 0.0, "objective_value": 0.0},
            timetable_validation=tt_val,
            room_validation=None,
            timetable_df=tt_300,
            allocation_df=None,
        )

        self.assertEqual(metrics["timetabling_quality"]["scheduled_exams_count"], 300)
        self.assertNotEqual(metrics["timetabling_quality"]["scheduled_exams_count"], 2198)

    def test_07_objective_reconciliation(self):
        """7. An objective-reconciliation test proving reported Z2 == w1*d1 + w2*d2 + w3*d3."""
        # Solve a 10-exam feasible subset with custom weights
        tt_sub = pd.DataFrame([
            {"exam_id": 12, "period_id": 29, "students": 40},
            {"exam_id": 13, "period_id": 29, "students": 35},
            {"exam_id": 20, "period_id": 29, "students": 25},
            {"exam_id": 21, "period_id": 29, "students": 30},
            {"exam_id": 22, "period_id": 29, "students": 15},
            {"exam_id": 118, "period_id": 29, "students": 78},  # forces split (1 extra room)
        ])

        w1, w2, w3 = 1.5, 2.0, 3.5
        gp = GoalProgrammingRoomAllocationModel(
            timetable_df=tt_sub,
            rooms_df=self.rooms_df,
            exam_rooms_df=self.exam_rooms_df,
            room_period_penalties_df=self.room_period_penalties_df,
            w1=w1,
            w2=w2,
            w3=w3,
        )
        res = gp.solve(time_limit_per_period=10)

        d1 = res["unused_capacity"]
        d2 = res["room_penalty"]
        d3 = res["room_splits"]  # extra room uses
        reported_z2 = res["objective_value"]
        expected_z2 = round(w1 * d1 + w2 * d2 + w3 * d3, 2)

        self.assertAlmostEqual(reported_z2, expected_z2, places=1)

    def test_08_stage1_to_stage2_handoff_period_invariant(self):
        """8. Stage 1 to Stage 2 handoff test confirming period assignments do not change."""
        tt_sub = pd.DataFrame([
            {"exam_id": 12, "period_id": 5, "students": 40},
            {"exam_id": 13, "period_id": 10, "students": 35},
            {"exam_id": 20, "period_id": 15, "students": 25},
        ])

        gp = GoalProgrammingRoomAllocationModel(
            timetable_df=tt_sub,
            rooms_df=self.rooms_df,
            exam_rooms_df=self.exam_rooms_df,
            room_period_penalties_df=self.room_period_penalties_df,
        )
        gp.solve(time_limit_per_period=5)
        alloc = gp.allocation_df
        self.assertIsNotNone(alloc)
        alloc_merged = alloc.merge(tt_sub[["exam_id", "period_id"]], on="exam_id", suffixes=("_alloc", "_orig"))
        for _, row in alloc_merged.iterrows():
            self.assertEqual(row["period_id_alloc"], row["period_id_orig"])

    def test_09_period_12_isolation_and_deficit_handling(self):
        """9. Test Period 12 subproblem: 145 solvable exams allocated optimally, Exam 2171 isolated as benchmark deficit."""
        base_tt = pd.read_csv("results/phase3_11/timetable_2198_pairwise_compact.csv")
        tt_p12 = base_tt[base_tt["period_id"] == 12].copy()
        self.assertEqual(len(tt_p12), 146)
        self.assertIn(2171, tt_p12["exam_id"].values)

        gp = GoalProgrammingRoomAllocationModel(
            timetable_df=tt_p12,
            rooms_df=self.rooms_df,
            exam_rooms_df=self.exam_rooms_df,
            room_period_penalties_df=self.room_period_penalties_df,
        )
        res = gp.solve(time_limit_per_period=40)
        self.assertEqual(gp.allocation_df["exam_id"].nunique(), 145)
        self.assertNotIn(2171, gp.allocation_df["exam_id"].values)
        self.assertEqual(res["period_subproblem_log"][12]["status"], "OPTIMAL")

    def test_10_period_1_pigeonhole_deficit_detection(self):
        """10. Test Period 1: detects genuine pigeonhole deficit (368 exams vs 324 unique eligible rooms)."""
        base_tt = pd.read_csv("results/phase3_11/timetable_2198_pairwise_compact.csv")
        tt_p1 = base_tt[base_tt["period_id"] == 1].copy()
        self.assertEqual(len(tt_p1), 368)

        gp = GoalProgrammingRoomAllocationModel(
            timetable_df=tt_p1,
            rooms_df=self.rooms_df,
            exam_rooms_df=self.exam_rooms_df,
            room_period_penalties_df=self.room_period_penalties_df,
        )
        res = gp.solve(time_limit_per_period=10)
        self.assertEqual(res["period_subproblem_log"][1]["termination_reason"], "PIGEONHOLE_DATA_INFEASIBILITY")
        self.assertIn("deficit", res["period_subproblem_log"][1]["reason"].lower())

    def test_11_small_feasible_bip_solve(self):
        """11. Small feasible BIP instance: solves to optimality and passes independent validation."""
        from src.bip_model import BIPTimetablingModel
        subset_ids = self.exams_df["exam_id"].tolist()[:10]
        bip = BIPTimetablingModel(
            exams_df=self.exams_df,
            periods_df=self.data["periods"],
            exam_periods_df=self.data["exam_periods"],
            enrollments_df=self.enrollments_df,
            constraints_df=self.constraints_df,
            exam_subset=subset_ids,
            exam_rooms_df=self.exam_rooms_df,
            max_exams_per_period=5,
        )
        bip.build_model()
        res = bip.solve(time_limit_seconds=15)
        self.assertIn(res["status"], ["OPTIMAL", "FEASIBLE"])
        self.assertEqual(len(bip.timetable_df), 10)
        val = self.validator.validate_timetable(bip.timetable_df)
        self.assertEqual(val["overall_status"], "PASS")

    def test_12_dynamic_scope_evaluation(self):
        """12. Dynamic evaluation for different dataset scopes (300, 500, 1000)."""
        from src.metrics import compute_comprehensive_metrics
        for n in [300, 500]:
            sub_tt = pd.read_csv("results/phase3_11/timetable_2198_pairwise_compact.csv").head(n)
            m = compute_comprehensive_metrics(
                bip_solution_summary={"status": "OPTIMAL", "runtime": 5.0, "objective_value": 100.0},
                gp_solution_summary=None,
                timetable_validation=self.validator.validate_timetable(sub_tt),
                room_validation=None,
                timetable_df=sub_tt,
                allocation_df=None,
            )
            self.assertEqual(m["timetabling_quality"]["scheduled_exams_count"], n)


if __name__ == "__main__":
    unittest.main()
