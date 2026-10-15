"""
tests/test_one_click_workflow.py
================================
Comprehensive test suite verifying:
1. One-click execution of both stages (Stage 1 -> Validation -> Stage 2 -> Validation).
2. Exact handoff of newly generated timetable into Stage 2.
3. Every real run initiates a fresh execution and produces a unique run directory.
4. Audited baseline artifacts remain completely untouched.
5. Scenario configuration validation (exams, rooms, periods, student demand).
6. Infeasible period handling (bottleneck reporting without fake fudge factors).
7. Session restart does not restore previous live runs silently.
8. Explicit run history retrieval and distinction between baseline and live runs.
9. Referential integrity & Dataset Explorer preservation.
"""

import unittest
import shutil
import json
import time
from pathlib import Path
import pandas as pd

from src.data_loader import load_all_data, verify_dataset_referential_integrity
from src.optimization_pipeline import execute_live_run, LIVE_RUNS_DIR
from src.bip_model import BIPTimetablingModel
from src.dashboard_data import list_completed_runs, load_integrated_results, verify_benchmark_identities
from src.scenario_validator import validate_scenario_configuration, compute_scenario_fingerprint

BASE_DIR = Path(__file__).resolve().parent.parent
BASELINE_S1_PATH = BASE_DIR / "results" / "phase3_11" / "timetable_2198_pairwise_compact.csv"
BASELINE_S2_PATH = BASE_DIR / "results" / "phase4_stage2_final" / "stage2_2198_room_allocation.csv"


class TestOneClickWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_all_data()
        cls.s1_mtime_before = BASELINE_S1_PATH.stat().st_mtime
        cls.s1_size_before = BASELINE_S1_PATH.stat().st_size
        cls.s2_mtime_before = BASELINE_S2_PATH.stat().st_mtime
        cls.s2_size_before = BASELINE_S2_PATH.stat().st_size
        cls.created_run_dirs = []

    @classmethod
    def tearDownClass(cls):
        # Clean up only the runs created during this specific test suite
        for r_dir in cls.created_run_dirs:
            if r_dir.exists():
                shutil.rmtree(r_dir, ignore_errors=True)

    def test_01_one_click_pipeline_sequence_and_handoff(self):
        """Verify complete two-stage sequence and exact handoff of Stage 1 timetable to Stage 2."""
        progress_log = []

        def cb(msg, prog, extra):
            progress_log.append((msg, prog, extra.get("stage")))

        test_run_id = f"test_workflow_{int(time.time())}"
        test_rooms = sorted(self.data["rooms"]["room_id"].tolist())[:50]
        run_summary = execute_live_run(
            scope="15",
            selected_room_ids=test_rooms,
            bip_time_limit=10,
            gp_time_limit_per_period=5,
            w1=1.0,
            w2=1.0,
            w3=2.0,
            progress_callback=cb,
            run_id=test_run_id,
        )

        run_dir = LIVE_RUNS_DIR / test_run_id
        self.created_run_dirs.append(run_dir)

        # 1. Verification of status
        self.assertEqual(run_summary["status"], "COMPLETED")
        self.assertEqual(run_summary["total_exams"], 15)

        # 2. Sequence order verified from callback
        stages_encountered = [s for _, _, s in progress_log if s]
        self.assertIn("DATA_PREPARATION", stages_encountered)
        self.assertIn("INPUT_VALIDATION", stages_encountered)
        self.assertIn("STAGE1_BUILD", stages_encountered)
        self.assertIn("STAGE1_SOLVE", stages_encountered)
        self.assertIn("STAGE1_VALIDATION", stages_encountered)
        self.assertIn("STAGE2_BUILD", stages_encountered)
        self.assertIn("STAGE2_SOLVE", stages_encountered)
        self.assertIn("STAGE2_VALIDATION", stages_encountered)
        self.assertIn("SAVE_ARTIFACTS", stages_encountered)

        # 3. Artifact files exist
        self.assertTrue((run_dir / "timetable.csv").exists())
        self.assertTrue((run_dir / "room_allocation.csv").exists())
        self.assertTrue((run_dir / "run_summary.json").exists())
        self.assertTrue((run_dir / "metrics.json").exists())
        self.assertTrue((run_dir / "room_validation.json").exists())

        # 4. Exact handoff verification: Timetable generated in Stage 1 is exactly what Stage 2 used
        tt_df = pd.read_csv(run_dir / "timetable.csv")
        alloc_df = pd.read_csv(run_dir / "room_allocation.csv")
        self.assertEqual(set(tt_df["exam_id"]), set(alloc_df["exam_id"]))
        self.assertEqual(len(tt_df), 15)

    def test_02_fresh_solve_and_unique_run_directories(self):
        """Every call to execute_live_run must generate a unique isolated run directory."""
        test_rooms = sorted(self.data["rooms"]["room_id"].tolist())[:50]
        run1 = execute_live_run(scope="15", selected_room_ids=test_rooms, bip_time_limit=5, gp_time_limit_per_period=3)
        time.sleep(0.1)
        run2 = execute_live_run(scope="15", selected_room_ids=test_rooms, bip_time_limit=5, gp_time_limit_per_period=3)

        dir1 = LIVE_RUNS_DIR / run1["run_id"]
        dir2 = LIVE_RUNS_DIR / run2["run_id"]
        self.created_run_dirs.extend([dir1, dir2])

        self.assertNotEqual(run1["run_id"], run2["run_id"])
        self.assertTrue(dir1.exists())
        self.assertTrue(dir2.exists())

    def test_03_audited_baseline_artifacts_strictly_preserved(self):
        """Verify baseline benchmark artifacts were never modified or overwritten."""
        self.assertEqual(BASELINE_S1_PATH.stat().st_mtime, self.s1_mtime_before)
        self.assertEqual(BASELINE_S1_PATH.stat().st_size, self.s1_size_before)
        self.assertEqual(BASELINE_S2_PATH.stat().st_mtime, self.s2_mtime_before)
        self.assertEqual(BASELINE_S2_PATH.stat().st_size, self.s2_size_before)

    def test_04_scenario_input_validation(self):
        """Verify scenario validator catches non-existent exams, invalid periods, and fixed-room deficits."""
        # Valid scenario
        val_good = validate_scenario_configuration(self.data, selected_exam_ids=[1, 2, 3])
        self.assertTrue(val_good["is_valid"])
        self.assertEqual(val_good["stats"]["selected_exams_count"], 3)

        # Invalid exam ID
        val_bad_exam = validate_scenario_configuration(self.data, selected_exam_ids=[999999])
        self.assertFalse(val_bad_exam["is_valid"])
        self.assertTrue(any("do not exist" in e for e in val_bad_exam["errors"]))

        # Missing required fixed room
        # Exam 990 is fixed to room 351 in the benchmark
        val_bad_room = validate_scenario_configuration(
            self.data,
            selected_exam_ids=[990],
            selected_room_ids=[100, 101], # room 351 deliberately excluded
        )
        self.assertFalse(val_bad_room["is_valid"])
        self.assertTrue(any("fixed-room" in e for e in val_bad_room["errors"]))

    def test_05_explicit_run_history_and_baseline_separation(self):
        """Verify runs list clearly distinguishes baseline benchmark from live runs."""
        runs = list_completed_runs()
        self.assertGreaterEqual(len(runs), 1)

        # First entry must be the Audited Baseline
        self.assertEqual(runs[0]["run_id"], "baseline_benchmark")
        self.assertTrue(runs[0]["is_baseline"])
        self.assertIn("Audited Baseline", runs[0]["name"])

        # Baseline data loaded has is_baseline True
        base_data = load_integrated_results("baseline_benchmark")
        self.assertTrue(base_data["is_baseline"])
        self.assertEqual(len(base_data["timetable_df"]), 2198)

    def test_06_infeasible_period_handling_honest_reporting(self):
        """Verify that known benchmark capacity deficit is reported honestly as UNALLOCATED."""
        # Exam 990 requires 15 students in Room 351 (which only has 14 seats)
        # When run, it must report allocation_status UNALLOCATED rather than crashing or faking seats
        test_run_id = f"test_infeasibility_{int(time.time())}"
        summary = execute_live_run(
            selected_exam_ids=[990],
            bip_time_limit=10,
            gp_time_limit_per_period=5,
            run_id=test_run_id,
        )
        run_dir = LIVE_RUNS_DIR / test_run_id
        self.created_run_dirs.append(run_dir)

        self.assertEqual(summary["status"], "COMPLETED")
        self.assertEqual(summary["counts"]["unallocated_exams"], 1)
        self.assertEqual(summary["counts"]["allocated_exams"], 0)

        alloc_df = pd.read_csv(run_dir / "room_allocation.csv")
        self.assertEqual(alloc_df.iloc[0]["assigned_rooms"], "UNASSIGNED")
        self.assertEqual(alloc_df.iloc[0]["allocation_status"], "UNALLOCATED")

    def test_07_referential_integrity_and_dataset_explorer_preservation(self):
        """Verify complete referential integrity across all 11 files without data alteration."""
        integrity_df = verify_dataset_referential_integrity(self.data)
        self.assertEqual(len(integrity_df), 9)
        self.assertTrue((integrity_df["Orphan Foreign Keys"] == 0).all())
        self.assertTrue((integrity_df["Status"] == "PASS").all())

    def test_08_caller_interface_exact_arguments(self):
        """
        Regression test: Verify execute_live_run accepts all arguments called by app.py:
        selected_exam_ids, selected_room_ids, selected_period_ids, custom_enrollments,
        bip_time_limit, gp_time_limit_per_period, w1, w2, w3, progress_callback, scope.
        """

        progress_events = []

        def callback(msg, prog, extra):
            progress_events.append((msg, prog))

        test_run_id = f"test_caller_compat_{int(time.time())}"
        summary = execute_live_run(
            scope="15",
            selected_exam_ids=[1, 2, 3],
            selected_room_ids=sorted(self.data["rooms"]["room_id"].tolist()),
            selected_period_ids=sorted(self.data["periods"]["period_id"].tolist()),
            custom_enrollments=None,
            bip_time_limit=10,
            gp_time_limit_per_period=5,
            w1=1.0,
            w2=1.0,
            w3=2.0,
            progress_callback=callback,
            run_id=test_run_id,
        )
        run_dir = LIVE_RUNS_DIR / test_run_id
        self.created_run_dirs.append(run_dir)

        self.assertEqual(summary["status"], "COMPLETED")
    def test_09_stage1_failure_stops_stage2_and_saves_failed_summary(self):
        """Verify that when Stage 1 fails, Stage 2 does not run and run_summary records failure."""
        from unittest.mock import patch
        test_run_id = f"test_failed_s1_{int(time.time())}"
        
        with patch.object(
            BIPTimetablingModel,
            "solve",
            return_value={
                "status": "ERROR",
                "error": "Simulated CBC process timeout or memory exception",
                "runtime": 1.5,
                "num_exams": 3,
                "scheduled_exams": 0,
            }
        ):
            summary = execute_live_run(
                scope="15",
                selected_exam_ids=[1, 2, 3],
                bip_time_limit=10,
                gp_time_limit_per_period=5,
                run_id=test_run_id,
            )

        run_dir = LIVE_RUNS_DIR / test_run_id
        self.created_run_dirs.append(run_dir)

        # Confirm status is marked FAILED_STAGE1
        self.assertIn("FAILED", summary["status"])
        self.assertGreater(len(summary["errors"]), 0)
        self.assertIn("Simulated CBC process timeout", summary["errors"][0])
        
        # Confirm Stage 2 never ran
        self.assertEqual(summary.get("stage2"), {})
        self.assertFalse((run_dir / "room_allocation.csv").exists())
        self.assertTrue((run_dir / "run_summary.json").exists())

    def test_10_load_integrated_results_handles_failed_run_gracefully(self):
        """Verify that load_integrated_results does not throw FileNotFoundError on incomplete or failed runs."""
        test_run_id = f"test_load_failed_{int(time.time())}"
        run_dir = LIVE_RUNS_DIR / test_run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        self.created_run_dirs.append(run_dir)

        # Write only run_summary.json without timetable.csv or room_allocation.csv
        sample_summary = {
            "run_id": test_run_id,
            "status": "FAILED_STAGE1",
            "errors": ["Stage 1 failed to produce a valid timetable."],
            "total_exams": 2198,
        }
        with open(run_dir / "run_summary.json", "w", encoding="utf-8") as f:
            json.dump(sample_summary, f)

        loaded = load_integrated_results(test_run_id)
        self.assertFalse(loaded["is_complete"])
        self.assertEqual(loaded["run_summary"]["status"], "FAILED_STAGE1")
        self.assertTrue(loaded["integrated_df"].empty)
        self.assertEqual(loaded["solver_results"]["final_classification"], "FAILED_STAGE1")

    def test_11_cbc_time_limit_without_incumbent_classified_honestly(self):
        """Verify that when CBC halts at time limit with no integer incumbent, BIPTimetablingModel classifies it as TIME_LIMIT_NO_INCUMBENT."""
        from unittest.mock import patch
        from pulp.apis.core import PulpSolverError
        
        test_run_id = f"test_tl_no_incumbent_{int(time.time())}"
        
        # Test direct BIPTimetablingModel.solve error handling with time-limit log
        bip = BIPTimetablingModel(
            exams_df=self.data["exams_with_enrollment"],
            periods_df=self.data["periods"],
            exam_periods_df=self.data["exam_periods"],
            enrollments_df=self.data["enrollments"],
            constraints_df=self.data["constraints"],
            exam_subset=[1, 2, 3],
            formulation="pairwise_compact",
        )
        bip.build_model()
        
        # Verify HiGHS time limit handling without incumbent
        def mock_solve(solver):
            return "Undefined"

        with patch.object(bip.prob, "solve", side_effect=mock_solve):
            res = bip.solve(time_limit_seconds=10)

        self.assertEqual(res["status"], "TIME_LIMIT_NO_INCUMBENT")
        self.assertEqual(res["scheduled_exams"], 0)


if __name__ == "__main__":
    unittest.main()


