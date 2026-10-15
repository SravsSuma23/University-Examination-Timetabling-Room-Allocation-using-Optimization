"""
main.py
=======
ExamOpt — University Examination Timetabling and Room Allocation
Operations Research Project — Lead CLI & Execution Entrypoint
Course: 23MNG336 Operations Research
Dataset: Purdue University Fall 2008 Benchmark (examopt_data/)
"""

import argparse
import sys
import json
import subprocess
from pathlib import Path
import pandas as pd

from src.data_loader import load_all_data, get_dataset_validation_summary
from src.bip_model import BIPTimetablingModel
from src.goal_programming import GoalProgrammingRoomAllocationModel
from src.validation import IndependentValidator
from src.metrics import compute_comprehensive_metrics
from src.preprocessing import preprocess_exam_subsets


def run_pipeline(
    scope: str = "150",
    time_limit_bip: int = 30,
    time_limit_gp: int = 10,
    w1: float = 1.0,
    w2: float = 1.0,
    w3: float = 2.0,
    output_dir: Path = None,
):
    """
    Executes the complete two-stage optimization pipeline from terminal.
    Stage 1: BIP Timetabling -> Independent Audit
    Stage 2: Weighted Goal Programming Room Allocation -> Independent Audit
    Computes and saves all 4 evaluation pillars.
    """
    if output_dir is None:
        output_dir = Path(__file__).resolve().parent / "data" / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("EXAMOPT — TWO-STAGE OPERATIONS RESEARCH OPTIMIZATION PIPELINE")
    print("=" * 70)

    # 1. Load data
    print("\n[STEP 1/5] Loading Purdue Fall 2008 Benchmark from examopt_data/...")
    data = load_all_data()
    val_summary = get_dataset_validation_summary(data)
    all_match = (val_summary["Status"] == "MATCH").all()
    print(f"  -> All 11 files loaded successfully. Specification match: {'PASS (10/10)' if all_match else 'CHECK'}")

    # 2. Scope selection
    subset = preprocess_exam_subsets(data["exams"], scope=scope)
    print(f"\n[STEP 2/5] Formulating Stage 1: BIP Examination Timetabling ({len(subset)} exams)...")
    bip = BIPTimetablingModel(
        exams_df=data["exams_with_enrollment"],
        periods_df=data["periods"],
        exam_periods_df=data["exam_periods"],
        enrollments_df=data["enrollments"],
        constraints_df=data["constraints"],
        exam_subset=subset,
        exam_rooms_df=data["exam_rooms"],
    )
    bip.build_model()
    print(f"  -> Model dimensions: {bip.num_variables:,} variables, {bip.num_constraints:,} constraints")
    print(f"  -> Solving with CBC solver (time limit: {time_limit_bip}s)...")
    bip_res = bip.solve(time_limit_seconds=time_limit_bip)
    print(f"  -> BIP Status: {bip_res['status']}")
    print(f"  -> Scheduled Exams: {bip_res['scheduled_exams']}")
    print(f"  -> BIP Objective Value: {bip_res['objective_value']}")
    print(f"  -> BIP Runtime: {bip_res['runtime']}s")

    tt_path = bip.save_timetable(output_dir)
    print(f"  -> Timetable saved: {tt_path}")

    # 3. Independent Audit of Timetable
    print("\n[STEP 3/5] Independent Audit of Generated Timetable...")
    validator = IndependentValidator(
        enrollments_df=data["enrollments"],
        exam_periods_df=data["exam_periods"],
        exam_rooms_df=data["exam_rooms"],
        constraints_df=data["constraints"],
        rooms_df=data["rooms"],
        exams_df=data["exams_with_enrollment"],
    )
    tt_val = validator.validate_timetable(bip.timetable_df)
    print(f"  -> Exact-One Rule: {tt_val['exact_one_assignment']['status']}")
    print(f"  -> Direct Student Conflicts: {tt_val['student_conflicts']['violations']} (Status: {tt_val['student_conflicts']['status']})")
    print(f"  -> Fixed-Time Rule: {tt_val['fixed_time_compliance']['status']}")
    print(f"  -> Distribution Constraints: {tt_val['distribution_compliance']['status']}")

    # 4. Stage 2: Goal Programming
    print(f"\n[STEP 4/5] Formulating Stage 2: Weighted Goal Programming Room Allocation...")
    print(f"  -> Goal Weights: w1 (Unused Capacity)={w1}, w2 (Room Penalty)={w2}, w3 (Splits)={w3}")
    gp = GoalProgrammingRoomAllocationModel(
        timetable_df=bip.timetable_df,
        rooms_df=data["rooms"],
        exam_rooms_df=data["exam_rooms"],
        room_period_penalties_df=data["room_period_penalties"],
        w1=w1, w2=w2, w3=w3,
    )
    gp_res = gp.solve(time_limit_per_period=time_limit_gp)
    print(f"  -> GP Status: {gp_res['status']}")
    print(f"  -> Room Seating Utilization: {gp_res['utilization_pct']}%")
    print(f"  -> Unused Capacity: {gp_res['unused_capacity']} seats")
    print(f"  -> Room Penalties Incurred: {gp_res['room_penalty']}")
    print(f"  -> Room Splits: {gp_res['room_splits']}")
    print(f"  -> GP Runtime: {gp_res['runtime']}s")

    alloc_path = gp.save_room_allocation(output_dir)
    print(f"  -> Room allocation saved: {alloc_path}")

    # 5. Independent Audit of Room Allocation & Performance Metrics
    print("\n[STEP 5/5] Calculating Evaluation Metrics (4 Pillars)...")
    rm_val = validator.validate_room_allocation(gp.allocation_df, bip.timetable_df)
    print(f"  -> Room Capacity Violations: {rm_val['capacity_compliance']['violations']} (Status: {rm_val['capacity_compliance']['status']})")
    print(f"  -> Room Double-Booking: {rm_val['double_booking']['violations']} (Status: {rm_val['double_booking']['status']})")

    metrics = compute_comprehensive_metrics(
        bip_res, gp_res, tt_val, rm_val, bip.timetable_df, gp.allocation_df
    )
    with open(output_dir / "evaluation_metrics.json", "w") as f:
        json.dump(metrics, f, indent=4)
    print(f"  -> Metrics JSON saved: {output_dir / 'evaluation_metrics.json'}")

    print("\n" + "=" * 70)
    print("FINAL EVALUATION METRICS SUMMARY (SLIDE 10 SPECIFICATION)")
    print("=" * 70)
    print(f"1. FEASIBILITY:")
    print(f"   • Direct Conflicts:             {metrics['feasibility']['direct_conflicts']}")
    print(f"   • Hard Constraint Violations:   {metrics['feasibility']['hard_constraint_violations']}")
    print(f"   • Room Capacity Violations:     {metrics['feasibility']['room_capacity_violations']}")
    print(f"   • Overall Status:               {metrics['feasibility']['overall_status']}")
    print(f"2. TIMETABLING QUALITY:")
    print(f"   • Total Period Penalty:         {metrics['timetabling_quality']['period_penalty']}")
    print(f"   • BIP Objective Value:          {metrics['timetabling_quality']['bip_objective_value']}")
    print(f"   • Scheduled Exams:              {metrics['timetabling_quality']['scheduled_exams_count']}")
    print(f"3. ROOM QUALITY:")
    print(f"   • Room Utilization Rate:        {metrics['room_quality']['room_utilization_pct']}%")
    print(f"   • Unused Capacity:              {metrics['room_quality']['unused_capacity']} seats")
    print(f"   • Total Room Penalty:           {metrics['room_quality']['room_penalty']}")
    print(f"   • Room Splits:                  {metrics['room_quality']['room_splits']}")
    print(f"4. COMPUTATIONAL PERFORMANCE:")
    print(f"   • Stage 1 (BIP) Runtime:        {metrics['computational']['bip_runtime_seconds']}s")
    print(f"   • Stage 2 (GP) Runtime:         {metrics['computational']['gp_runtime_seconds']}s")
    print(f"   • Total Runtime:                {metrics['computational']['total_runtime_seconds']}s")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="ExamOpt: University Examination Timetabling & Room Allocation Optimization (23MNG336)"
    )
    parser.add_argument(
        "--scope",
        type=str,
        default="all",
        help="Problem scope ('all' / '2198' for Final Benchmark; '150', '350', '750' for Testing Scopes). Default: all",
    )
    parser.add_argument(
        "--time-limit-bip",
        type=int,
        default=60,
        help="CBC time limit for BIP model in seconds. Default: 60",
    )
    parser.add_argument(
        "--time-limit-gp",
        type=int,
        default=10,
        help="CBC time limit per period for Goal Programming in seconds. Default: 10",
    )
    parser.add_argument(
        "--w1",
        type=float,
        default=1.0,
        help="Weight for Goal 1 (Unused Capacity). Default: 1.0",
    )
    parser.add_argument(
        "--w2",
        type=float,
        default=1.0,
        help="Weight for Goal 2 (Room Penalty). Default: 1.0",
    )
    parser.add_argument(
        "--w3",
        type=float,
        default=2.0,
        help="Weight for Goal 3 (Room Splits). Default: 2.0",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Run only dataset validation against Purdue Fall 2008 benchmark.",
    )
    parser.add_argument(
        "--referential-integrity",
        action="store_true",
        help="Verify cross-table referential integrity and foreign keys across all 11 CSV files.",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Execute unit test suite.",
    )
    parser.add_argument(
        "--app",
        action="store_true",
        help="Launch the interactive Streamlit decision support system.",
    )

    args = parser.parse_args()

    if args.validate_only:
        data = load_all_data()
        val = get_dataset_validation_summary(data)
        print(val.to_string(index=False))
        return

    if args.referential_integrity:
        from src.data_loader import verify_dataset_referential_integrity
        data = load_all_data()
        integrity_df = verify_dataset_referential_integrity(data)
        print(integrity_df.to_string(index=False))
        return

    if args.test:
        subprocess.run([sys.executable, "-m", "unittest", "tests.test_examopt", "-v"])
        return

    if args.app:
        subprocess.run(["streamlit", "run", "app.py"])
        return

    run_pipeline(
        scope=args.scope,
        time_limit_bip=args.time_limit_bip,
        time_limit_gp=args.time_limit_gp,
        w1=args.w1,
        w2=args.w2,
        w3=args.w3,
    )


if __name__ == "__main__":
    main()
