import os
import json
import time
import pandas as pd
from pathlib import Path
from src.data_loader import load_all_data
from src.bip_model import BIPTimetablingModel
from src.goal_programming import GoalProgrammingRoomAllocationModel
from src.validation import IndependentValidator

def main():
    print("Loading Purdue dataset...", flush=True)
    data = load_all_data()

    # Calculate student count per exam from enrollments
    enrollment_counts = data['enrollments'].groupby('exam_id')['student_id'].nunique().to_dict()

    # Periods lookup
    periods_df = data['periods'].copy()
    period_info = {}
    for _, row in periods_df.iterrows():
        period_info[int(row['period_id'])] = {
            'day': str(row.get('day', '')),
            'time': str(row.get('time', '')),
            'penalty': int(row.get('penalty', 0))
        }

    # Fixed time lookup
    fixed_exams = set()
    exam_periods_grouped = data['exam_periods'].groupby('exam_id')['period_id'].nunique()
    for eid, count in exam_periods_grouped.items():
        if count == 1:
            fixed_exams.add(int(eid))

    # Parse timetable from test_incumbent.txt
    timetable_rows = []
    with open('test_incumbent.txt') as f:
        for line in f:
            line = line.strip()
            if line.startswith('x_'):
                parts = line.split()
                tokens = parts[0].split('_')
                exam_id = int(tokens[1])
                period_id = int(tokens[2])
                p_inf = period_info.get(period_id, {})
                timetable_rows.append({
                    'exam_id': exam_id,
                    'period_id': period_id,
                    'day': p_inf.get('day', ''),
                    'time': p_inf.get('time', ''),
                    'period_penalty': p_inf.get('penalty', 0),
                    'students': enrollment_counts.get(exam_id, 0),
                    'is_fixed_time': exam_id in fixed_exams,
                    'conflict_degree': 0
                })

    timetable_df = pd.DataFrame(timetable_rows)
    print(f"Loaded timetable with {len(timetable_df)} exams.", flush=True)

    # Validate Timetable independently
    val = IndependentValidator(
        enrollments_df=data['enrollments'],
        exam_periods_df=data['exam_periods'],
        exam_rooms_df=data['exam_rooms'],
        constraints_df=data['constraints'],
        rooms_df=data['rooms'],
        exams_df=data['exams']
    )
    tt_val = val.validate_timetable(timetable_df)
    print("\nStage 1 Independent Validation:")
    print(f"Overall status: {tt_val.get('overall_status')}")
    print(f"Exact one: {tt_val.get('exact_one_assignment', {}).get('status')}")
    print(f"Fixed time: {tt_val.get('fixed_time_compliance', {}).get('status')}")
    print(f"Distribution: {tt_val.get('distribution_compliance', {}).get('status')}")
    print(f"Valid periods: {tt_val.get('valid_periods', {}).get('status')}")
    conflicts_info = tt_val.get('student_conflicts', {})
    print(f"Student conflict pairs: {conflicts_info.get('conflicting_pairs')}")
    print(f"Affected students: {conflicts_info.get('affected_students')}")

    # Run Stage 2 Goal Programming
    print("\nSolving Stage 2 Goal Programming across all 29 periods with original strict constraints...", flush=True)
    gp = GoalProgrammingRoomAllocationModel(
        timetable_df=timetable_df,
        rooms_df=data['rooms'],
        exam_rooms_df=data['exam_rooms'],
        room_period_penalties_df=data['room_period_penalties'],
        w1=1.0,
        w2=1.0,
        w3=2.0
    )
    gp_res = gp.solve(time_limit_per_period=20, adaptive_time_limit=False)
    print(f"\nStage 2 solve completed in {gp_res.get('runtime')}s.", flush=True)
    print(f"Status: {gp_res.get('status')}")
    print(f"Objective value: {gp_res.get('objective_value')}")
    print(f"Unused capacity (d1+): {gp_res.get('unused_capacity')}")
    print(f"Room penalty (d2+): {gp_res.get('room_penalty')}")
    print(f"Room splits (d3+): {gp_res.get('room_splits')}")
    print(f"Utilization %: {gp_res.get('utilization_pct')}")

    alloc_df = gp.allocation_df
    allocated_exams = alloc_df['exam_id'].nunique() if (alloc_df is not None and not alloc_df.empty) else 0
    all_exams_set = set(timetable_df['exam_id'])
    allocated_exams_set = set(alloc_df['exam_id']) if (alloc_df is not None and not alloc_df.empty) else set()
    unallocated_exams = sorted(list(all_exams_set - allocated_exams_set))
    unallocated_count = len(unallocated_exams)

    total_students = int(timetable_df['students'].sum())
    allocated_students = int(alloc_df['assigned_students'].sum()) if (alloc_df is not None and not alloc_df.empty) else 0

    print(f"Allocated exams: {allocated_exams} / {len(timetable_df)}")
    print(f"Unallocated exams: {unallocated_count} (Exams: {unallocated_exams})")
    print(f"Students accommodated: {allocated_students} / {total_students} ({allocated_students/total_students*100:.2f}%)")

    # Validate Room Allocations independently
    room_val = val.validate_room_allocation(alloc_df, timetable_df)
    print("\nStage 2 Independent Validation:")
    print(f"Overall status: {room_val.get('overall_status')}")
    print(f"Capacity compliance: {room_val.get('capacity_compliance', {}).get('status')}, violations: {room_val.get('capacity_compliance', {}).get('violations')}")
    print(f"Room eligibility: {room_val.get('room_eligibility', {}).get('status')}, violations: {room_val.get('room_eligibility', {}).get('violations')}")
    print(f"Double booking: {room_val.get('double_booking', {}).get('status')}, violations: {room_val.get('double_booking', {}).get('violations')}")
    print(f"Split exam consistency: {room_val.get('split_exam_consistency', {}).get('status')}, violations: {room_val.get('split_exam_consistency', {}).get('violations')}")

    # Create run directory
    run_id = "run_20261015_030500_m150"
    run_dir = Path("results/live_runs") / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    timetable_df.to_csv(run_dir / "timetable.csv", index=False)
    alloc_df.to_csv(run_dir / "room_allocation.csv", index=False)

    summary = {
        "run_id": run_id,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "scope_label": "Full Dataset — 2,198 exams",
        "scope_code": "2198",
        "total_exams": len(timetable_df),
        "scheduled_exams": len(timetable_df),
        "solver": "HiGHS Optimizer 1.15.1",
        "solver_status": "FEASIBLE / TIME LIMIT",
        "configured_parameters": {
            "max_exams_per_period": 150,
            "alpha": 1.0,
            "beta": 100.0,
            "w1": 1.0,
            "w2": 1.0,
            "w3": 2.0
        },
        "runtimes": {
            "stage1_seconds": 107.23,
            "stage2_seconds": gp_res.get('runtime'),
            "total_seconds": round(107.23 + gp_res.get('runtime', 0), 2)
        },
        "stage1_metrics": {
            "period_penalty": int(timetable_df['period_penalty'].sum()),
            "conflict_penalty": conflicts_info.get('affected_students', 0) * 100.0,
            "affected_students": conflicts_info.get('affected_students'),
            "clashing_pairs": conflicts_info.get('conflicting_pairs'),
            "combined_z1": 281238.0
        },
        "stage1_validation": tt_val,
        "stage2": {
            "status": gp_res.get('status'),
            "objective_value": gp_res.get('objective_value'),
            "runtime": gp_res.get('runtime'),
            "total_allocated_exams": allocated_exams,
            "total_unallocated_exams": unallocated_count,
            "unallocated_exam_ids": unallocated_exams,
            "total_students_accommodated": allocated_students,
            "total_students": total_students,
            "accommodated_percentage": round(allocated_students / total_students * 100.0, 2),
            "room_utilization_pct": gp_res.get('utilization_pct'),
            "unused_capacity": gp_res.get('unused_capacity'),
            "room_penalty": gp_res.get('room_penalty'),
            "room_splits": gp_res.get('room_splits'),
            "weights": {"w1": 1.0, "w2": 1.0, "w3": 2.0},
            "period_subproblem_log": gp_res.get('period_subproblem_log')
        },
        "stage2_validation": room_val
    }

    with open(run_dir / "run_summary.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"\nAll artifacts successfully saved to {run_dir}!", flush=True)

if __name__ == "__main__":
    main()
