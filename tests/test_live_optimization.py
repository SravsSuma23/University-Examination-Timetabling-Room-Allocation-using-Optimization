"""
tests/test_live_optimization.py
===============================
Integration and safety tests for Phase 5.2 Live Optimization.

Verifies:
1. Orchestrator executes Stage 1 -> Validation -> Stage 2 -> Validation without error.
2. An isolated run directory is created under results/live_runs/.
3. Baseline benchmark artifacts (Phase 3.11 and Phase 4.4) remain strictly untouched.
4. Newly generated results can be loaded and formatted cleanly by dashboard_data.py.
"""

import unittest
import shutil
from pathlib import Path
import pandas as pd

from src.optimization_pipeline import execute_live_run, LIVE_RUNS_DIR
from src.dashboard_data import list_completed_runs, load_integrated_results, verify_benchmark_identities

BASE_DIR = Path(__file__).resolve().parent.parent
BASELINE_S1_PATH = BASE_DIR / "results" / "phase3_11" / "timetable_2198_pairwise_compact.csv"
BASELINE_S2_PATH = BASE_DIR / "results" / "phase4_stage2_final" / "stage2_2198_room_allocation.csv"


class TestLiveOptimizationPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Record mtime and size of audited baseline files before testing
        cls.s1_mtime_before = BASELINE_S1_PATH.stat().st_mtime
        cls.s1_size_before = BASELINE_S1_PATH.stat().st_size
        cls.s2_mtime_before = BASELINE_S2_PATH.stat().st_mtime
        cls.s2_size_before = BASELINE_S2_PATH.stat().st_size
        cls.test_run_id = "test_unit_run_scope15"

    @classmethod
    def tearDownClass(cls):
        # Clean up test run directory to keep workspace tidy
        test_dir = LIVE_RUNS_DIR / cls.test_run_id
        if test_dir.exists():
            shutil.rmtree(test_dir)

    def test_01_execute_live_run_small_scope(self):
        """Execute a lightweight live optimization run on small scope (15 exams) to verify integration."""
        progress_events = []

        def callback(msg, prog, extra):
            progress_events.append((msg, prog))

        summary = execute_live_run(
            scope="15",
            bip_time_limit=10,
            gp_time_limit_per_period=5,
            w1=1.0,
            w2=1.0,
            w3=2.0,
            progress_callback=callback,
            run_id=self.test_run_id,
        )

        self.assertEqual(summary["status"], "COMPLETED")
        self.assertEqual(summary["total_exams"], 15)
        self.assertGreater(len(progress_events), 3)

        # Check isolated run artifacts exist
        run_dir = LIVE_RUNS_DIR / self.test_run_id
        self.assertTrue((run_dir / "timetable.csv").exists())
        self.assertTrue((run_dir / "room_allocation.csv").exists())
        self.assertTrue((run_dir / "run_summary.json").exists())
        self.assertTrue((run_dir / "room_validation.json").exists())
        self.assertTrue((run_dir / "metrics.json").exists())

    def test_02_baseline_benchmark_untouched(self):
        """Verify audited benchmark files were never modified."""
        self.assertEqual(BASELINE_S1_PATH.stat().st_mtime, self.s1_mtime_before)
        self.assertEqual(BASELINE_S1_PATH.stat().st_size, self.s1_size_before)
        self.assertEqual(BASELINE_S2_PATH.stat().st_mtime, self.s2_mtime_before)
        self.assertEqual(BASELINE_S2_PATH.stat().st_size, self.s2_size_before)

    def test_03_load_live_run_in_dashboard_data(self):
        """Verify load_integrated_results loads both baseline and live run smoothly."""
        # 1. Baseline
        base_data = load_integrated_results("baseline_benchmark")
        self.assertEqual(len(base_data["timetable_df"]), 2198)
        self.assertTrue(base_data["is_baseline"])

        # 2. Live run
        live_data = load_integrated_results(self.test_run_id)
        self.assertEqual(len(live_data["timetable_df"]), 15)
        self.assertFalse(live_data["is_baseline"])
        self.assertIn("integrated_df", live_data)
        self.assertIn("allocation_df", live_data)

        # Verify identities function works on both
        base_checks = verify_benchmark_identities(base_data)
        self.assertTrue(all(p[0] for p in base_checks.values()))

        live_checks = verify_benchmark_identities(live_data)
        self.assertTrue(all(p[0] for p in live_checks.values()))

    def test_04_list_completed_runs(self):
        """Verify run discovery lists baseline and the completed test run."""
        runs = list_completed_runs()
        run_ids = [r["run_id"] for r in runs]
        self.assertIn("baseline_benchmark", run_ids)
        self.assertIn(self.test_run_id, run_ids)


if __name__ == "__main__":
    unittest.main()
