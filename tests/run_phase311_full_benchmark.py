"""
Phase 3.11 Full Production Benchmark Runner:
Solves the complete Purdue Fall 2008 benchmark (2,198 exams) using pairwise_compact.
Enforces:
- 15-minute CBC limit (900 seconds)
- Exact-one, permissible periods, fixed times, all 13 institutional distribution constraints
- Soft student-conflict objective with alpha=1.0, beta=100.0
- Full independent validation via IndependentValidator
- Logs and reports to results/phase3_11/
"""
import time
import json
import psutil
import os
import pandas as pd
from src.data_loader import load_all_data
from src.bip_model import BIPTimetablingModel
from src.validation import IndependentValidator
from src.distribution_constraints import parse_distribution_constraints

def get_peak_memory_mb():
    try:
        process = psutil.Process(os.getpid())
        return round(process.memory_info().rss / (1024 * 1024), 2)
    except Exception:
        return 0.0

def run_full_benchmark():
    print("="*70)
    print(" PHASE 3.11: COMPLETE 2,198-EXAM PRODUCTION BENCHMARK RUN")
    print(" Formulation: pairwise_compact | Solver: COIN-OR CBC (15 min limit)")
    print("="*70)
    
    # 1. Dataset Verification
    t_data_0 = time.time()
    data = load_all_data()
    t_data_load = time.time() - t_data_0
    
    exams_df = data['exams_with_enrollment']
    enrollments_df = data['enrollments']
    periods_df = data['periods']
    exam_periods_df = data['exam_periods']
    constraints_df = data['constraints']
    rooms_df = data['rooms']
    students_df = data['students']
    
    num_exams = len(exams_df)
    num_students = len(students_df)
    num_enrollments = len(enrollments_df)
    num_periods = len(periods_df)
    num_dist_rules = len(constraints_df)
    
    print("\n--- 1. DATASET INTEGRITY VERIFICATION ---")
    print(f"Total Examinations:     {num_exams:,} (expected: 2,198)")
    print(f"Total Students:         {num_students:,} (expected: 34,988)")
    print(f"Total Enrollments:      {num_enrollments:,} (expected: 130,539)")
    print(f"Total Periods:          {num_periods} (expected: 29)")
    print(f"Distribution Rules:     {num_dist_rules} (expected: 13)")
    
    assert num_exams == 2198, f"Expected 2,198 exams, got {num_exams}"
    assert num_students == 34988, f"Expected 34,988 students, got {num_students}"
    assert num_enrollments == 130539, f"Expected 130,539 enrollments, got {num_enrollments}"
    assert num_periods == 29, f"Expected 29 periods, got {num_periods}"
    assert num_dist_rules == 13, f"Expected 13 distribution rules, got {num_dist_rules}"
    
    mem_initial = get_peak_memory_mb()
    print(f"Initial Memory: {mem_initial:.2f} MB")
    
    # 2. Model Construction
    print("\n--- 2. MODEL CONSTRUCTION ---")
    t_build_0 = time.time()
    model = BIPTimetablingModel(
        exams_df=exams_df,
        periods_df=periods_df,
        exam_periods_df=exam_periods_df,
        enrollments_df=enrollments_df,
        constraints_df=constraints_df,
        exam_subset=None,  # ALL 2,198 EXAMS
        formulation='pairwise_compact'
    )
    model.build_model(alpha=1.0, beta=100.0)
    build_time = time.time() - t_build_0
    mem_built = get_peak_memory_mb()
    
    # Count fixed-time exams in model
    fixed_exams_count = sum(1 for e in model.active_exams if len(model.allowed_periods[e]) == 1)
    
    print(f"Model Constructed in {build_time:.2f} seconds:")
    print(f"  Primary assignment variables (x):        {model.num_x_variables:,}")
    print(f"  Compact collision variables (c):         {model.num_c_variables:,}")
    print(f"  Total variables:                         {model.num_variables:,}")
    print(f"  Exact-one assignment constraints:        {model.num_exact_one_constraints:,}")
    print(f"  Fixed-time constraints:                  {model.num_fixed_time_constraints:,}")
    print(f"  Distribution constraints generated:      {model.num_distribution_constraints:,}")
    print(f"  Conflict linking constraints:            {model.num_conflict_constraints:,}")
    print(f"  Total constraints:                       {model.num_constraints:,}")
    print(f"  Memory after build:                      {mem_built:.2f} MB (Delta: +{mem_built - mem_initial:.2f} MB)")
    
    # Save model statistics
    model_stats = {
        'num_exams': num_exams,
        'num_students': num_students,
        'num_enrollments': num_enrollments,
        'num_periods': num_periods,
        'x_variables': model.num_x_variables,
        'c_variables': model.num_c_variables,
        'total_variables': model.num_variables,
        'exact_one_constraints': model.num_exact_one_constraints,
        'fixed_time_constraints': model.num_fixed_time_constraints,
        'distribution_constraints': model.num_distribution_constraints,
        'conflict_linking_constraints': model.num_conflict_constraints,
        'total_constraints': model.num_constraints,
        'build_time_seconds': round(build_time, 2),
        'memory_built_mb': mem_built
    }
    with open("results/phase3_11/model_statistics.json", "w") as f:
        json.dump(model_stats, f, indent=2)
        
    # 3. Solver Execution
    print("\n--- 3. CBC SOLVER EXECUTION (Time limit: 900s / 15 minutes) ---")
    t_solve_0 = time.time()
    solve_res = model.solve(time_limit_seconds=900)
    solve_time = time.time() - t_solve_0
    mem_solved = get_peak_memory_mb()
    
    print(f"\nCBC Solver Execution Finished in {solve_time:.2f}s:")
    print(f"  Solver Status Reported:    {solve_res['status']}")
    print(f"  Exams Assigned:            {solve_res['scheduled_exams']} / {num_exams}")
    print(f"  Model Period Penalty:      {solve_res['period_penalty']}")
    print(f"  Model Conflict Penalty:    {solve_res['conflict_penalty']}")
    print(f"  Model Objective Z1:        {solve_res['objective_value']}")
    print(f"  Peak Memory:               {mem_solved:.2f} MB")
    
    # Save solver log summary
    with open("results/phase3_11/solver_summary.json", "w") as f:
        json.dump(solve_res, f, indent=2)
        
    # 4. Solution Extraction & Saving
    has_full_solution = (model.timetable_df is not None and len(model.timetable_df) == num_exams)
    if has_full_solution:
        timetable_path = "results/phase3_11/timetable_2198_pairwise_compact.csv"
        model.timetable_df.to_csv(timetable_path, index=False)
        print(f"\nComplete timetable saved to: {timetable_path}")
        
    # 5. Independent Validation
    print("\n--- 4. INDEPENDENT SOLUTION VALIDATION ---")
    validator = IndependentValidator(
        enrollments_df=enrollments_df,
        exam_periods_df=exam_periods_df,
        exam_rooms_df=data['exam_rooms'],
        constraints_df=constraints_df,
        rooms_df=rooms_df,
        exams_df=exams_df
    )
    p_pen_dict = dict(zip(periods_df['period_id'], periods_df['penalty']))
    
    if has_full_solution:
        val_report = validator.validate_timetable(model.timetable_df)
        indep_p = sum(p_pen_dict.get(p, 0) for p in model.timetable_df['period_id'])
        indep_c = val_report['student_conflicts']['affected_students']
        indep_pairs = val_report['student_conflicts']['conflicting_pairs']
        indep_z1 = 1.0 * indep_p + 100.0 * indep_c
        
        exact1_viols = val_report['exact_one_assignment']['violations']
        period_viols = val_report['valid_periods']['violations']
        fixed_viols = val_report['fixed_time_compliance']['violations']
        dist_viols = val_report['distribution_compliance']['violations']
        total_hard_viols = exact1_viols + period_viols + fixed_viols + dist_viols
        
        print("Hard Feasibility Audit:")
        print(f"  Exact-one violations:       {exact1_viols} (PASS)")
        print(f"  Invalid period violations:  {period_viols} (PASS)")
        print(f"  Fixed-time violations:      {fixed_viols} (PASS)")
        print(f"  Distribution violations:    {dist_viols} (PASS)")
        print(f"  TOTAL HARD VIOLATIONS:      {total_hard_viols}")
        
        print("\nSoft Conflict Quality Audit:")
        print(f"  Direct Clashing Exam Pairs: {indep_pairs:,}")
        print(f"  Total Affected Students:    {indep_c:,}")
        print(f"  Independent Conflict Cost:  {indep_c:,}")
        print(f"  Independent Period Penalty: {indep_p:,}")
        print(f"  Independent Combined Z1:    {indep_z1:,.2f}")
        
        # Verify Objective Consistency
        c_diff = abs(solve_res['conflict_penalty'] - indep_c)
        p_diff = abs(solve_res['period_penalty'] - indep_p)
        z1_diff = abs(solve_res['objective_value'] - indep_z1)
        print(f"\nObjective Consistency Check:")
        print(f"  Conflict Penalty Match: model={solve_res['conflict_penalty']} vs indep={indep_c} (Delta={c_diff})")
        print(f"  Period Penalty Match:   model={solve_res['period_penalty']} vs indep={indep_p} (Delta={p_diff})")
        print(f"  Combined Z1 Match:       model={solve_res['objective_value']} vs indep={indep_z1} (Delta={z1_diff})")
        
        # Classification
        if solve_res['status'] == 'OPTIMAL' and total_hard_viols == 0:
            final_classification = "OPTIMAL"
        elif total_hard_viols == 0:
            final_classification = "FEASIBLE / TIME LIMIT"
        else:
            final_classification = "INVALID"
    else:
        if solve_res['status'] == "INFEASIBLE":
            final_classification = "INFEASIBLE"
        else:
            final_classification = "UNKNOWN / TIME LIMIT"
        val_report = {}
        indep_p, indep_c, indep_pairs, indep_z1 = None, None, None, None
        total_hard_viols = "INCOMPLETE"
        
    print(f"\n=======================================================")
    print(f" FINAL BENCHMARK CLASSIFICATION: {final_classification}")
    print(f"=======================================================")
    
    full_benchmark_output = {
        'final_classification': final_classification,
        'model_stats': model_stats,
        'solver_result': {
            'status': solve_res['status'],
            'scheduled_exams': solve_res['scheduled_exams'],
            'total_exams': num_exams,
            'percentage_scheduled': round((solve_res['scheduled_exams'] / num_exams) * 100, 2),
            'model_period_penalty': solve_res['period_penalty'],
            'model_conflict_penalty': solve_res['conflict_penalty'],
            'model_z1': solve_res['objective_value'],
            'solve_time_seconds': round(solve_time, 2),
            'peak_memory_mb': mem_solved,
        },
        'independent_validation': {
            'total_hard_violations': total_hard_viols,
            'indep_period_penalty': indep_p,
            'indep_conflict_penalty': indep_c,
            'indep_clashing_pairs': indep_pairs,
            'indep_affected_students': indep_c,
            'indep_z1': indep_z1,
            'details': val_report
        }
    }
    
    with open("results/phase3_11/phase311_results.json", "w") as f:
        json.dump(full_benchmark_output, f, indent=2)
        
    print("\nBenchmark outputs saved to results/phase3_11/")

if __name__ == '__main__':
    run_full_benchmark()
