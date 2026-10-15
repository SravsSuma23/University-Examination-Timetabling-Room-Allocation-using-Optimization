"""
Phase 3.10 Scale-Up Runner:
Executes:
1. Phase 3.10A: 750 exams using pairwise_compact with 15-minute time limit (900s).
   - Independent validation.
   - If complete valid timetable produced, proceed to Phase 3.10B.
2. Phase 3.10B: 1,000 exams using pairwise_compact with 15-minute time limit (900s).
   - Independent validation.
Saves all timetables, validation reports, and JSON summaries to results/phase3_10/
"""
import time
import json
import psutil
import os
import pandas as pd
from src.data_loader import load_all_data
from src.bip_model import BIPTimetablingModel
from src.validation import IndependentValidator

def get_peak_memory_mb():
    try:
        process = psutil.Process(os.getpid())
        return round(process.memory_info().rss / (1024 * 1024), 2)
    except Exception:
        return 0.0

def run_scale_up():
    data = load_all_data()
    all_exams = sorted(data['exams_with_enrollment']['exam_id'].unique())
    p_pen_dict = dict(zip(data['periods']['period_id'], data['periods']['penalty']))
    
    validator = IndependentValidator(
        enrollments_df=data['enrollments'],
        exam_periods_df=data['exam_periods'],
        exam_rooms_df=data['exam_rooms'],
        constraints_df=data['constraints'],
        rooms_df=data['rooms'],
        exams_df=data['exams_with_enrollment']
    )
    
    results = {}
    
    # ====================================================
    # PHASE 3.10A: 750 EXAMS
    # ====================================================
    print("\n" + "="*60)
    print(" PHASE 3.10A: 750-EXAM SCALE-UP RUN (pairwise_compact)")
    print("="*60)
    subset_750 = set(all_exams[:750])
    
    mem_before_750 = get_peak_memory_mb()
    t0 = time.time()
    m_750 = BIPTimetablingModel(
        exams_df=data['exams_with_enrollment'],
        periods_df=data['periods'],
        exam_periods_df=data['exam_periods'],
        enrollments_df=data['enrollments'],
        constraints_df=data['constraints'],
        exam_subset=subset_750,
        formulation='pairwise_compact'
    )
    m_750.build_model()
    t_750_build = time.time() - t0
    mem_after_build_750 = get_peak_memory_mb()
    
    print(f"Model 750 Built in {t_750_build:.2f}s:")
    print(f"  x variables: {len(m_750.x):,}")
    print(f"  c variables: {len(m_750.c):,}")
    print(f"  total variables: {m_750.num_variables:,}")
    print(f"  total constraints: {m_750.num_constraints:,}")
    print(f"  exact-one constraints: {m_750.num_exact_one_constraints:,}")
    print(f"  fixed-time constraints: {m_750.num_fixed_time_constraints:,}")
    print(f"  distribution constraints: {m_750.num_distribution_constraints:,}")
    print(f"  conflict linking constraints: {m_750.num_conflict_constraints:,}")
    print(f"  memory: {mem_after_build_750:.2f} MB")
    
    # 15-minute time limit = 900 seconds
    print("\nStarting CBC Solve (time limit: 900s)...")
    t_solve_start = time.time()
    res_750 = m_750.solve(time_limit_seconds=900)
    t_750_solve = time.time() - t_solve_start
    mem_after_solve_750 = get_peak_memory_mb()
    
    print(f"\nCBC Solve Completed in {t_750_solve:.2f}s:")
    print(f"  Solver status: {res_750['status']}")
    print(f"  Scheduled exams: {res_750['scheduled_exams']} / 750")
    print(f"  Period penalty: {res_750['period_penalty']}")
    print(f"  Conflict penalty: {res_750['conflict_penalty']}")
    print(f"  Objective Z1: {res_750['objective_value']}")
    
    # Independent validation
    has_full_750 = (m_750.timetable_df is not None and len(m_750.timetable_df) == 750)
    val_750 = validator.validate_timetable(m_750.timetable_df) if has_full_750 else {}
    indep_p_750 = sum(p_pen_dict.get(p, 0) for p in m_750.timetable_df['period_id']) if has_full_750 else None
    indep_c_750 = val_750.get('student_conflicts', {}).get('affected_students', None) if has_full_750 else None
    indep_z1_750 = (1.0 * indep_p_750 + 100.0 * indep_c_750) if (indep_p_750 is not None and indep_c_750 is not None) else None
    
    hard_viols_750 = (
        val_750.get('exact_one_assignment', {}).get('violations', 0) +
        val_750.get('valid_periods', {}).get('violations', 0) +
        val_750.get('fixed_time_compliance', {}).get('violations', 0) +
        val_750.get('distribution_compliance', {}).get('violations', 0)
    ) if has_full_750 else 'INCOMPLETE'
    
    # Classification
    if res_750['status'] == 'OPTIMAL' and has_full_750 and hard_viols_750 == 0:
        classification_750 = "OPTIMAL"
    elif "FEASIBLE" in res_750['status'] and has_full_750 and hard_viols_750 == 0:
        classification_750 = "FEASIBLE / TIME LIMIT"
    elif res_750['status'] == "INFEASIBLE":
        classification_750 = "INFEASIBLE"
    else:
        classification_750 = "UNKNOWN / TIME LIMIT"
        
    print(f"\nPhase 3.10A Final Classification: {classification_750}")
    print(f"Hard Violations: {hard_viols_750}")
    if has_full_750:
        print(f"Independent Clashing Pairs: {val_750['student_conflicts']['conflicting_pairs']}")
        print(f"Independent Affected Students: {indep_c_750}")
        print(f"Independent Period Penalty: {indep_p_750}")
        print(f"Independent Z1: {indep_z1_750}")
        m_750.timetable_df.to_csv("results/phase3_10/timetable_750_pairwise_compact.csv", index=False)
        
    results['scope_750'] = {
        'scope': 750,
        'classification': classification_750,
        'status': res_750['status'],
        'scheduled': res_750['scheduled_exams'],
        'x_vars': len(m_750.x),
        'c_vars': len(m_750.c),
        'total_vars': m_750.num_variables,
        'total_constraints': m_750.num_constraints,
        'build_time': round(t_750_build, 2),
        'solve_time': round(res_750['runtime'], 2),
        'peak_memory_mb': mem_after_solve_750,
        'model_period_penalty': res_750['period_penalty'],
        'model_conflict_penalty': res_750['conflict_penalty'],
        'model_z1': res_750['objective_value'],
        'hard_violations': hard_viols_750,
        'indep_conflict_pairs': val_750.get('student_conflicts', {}).get('conflicting_pairs', 0) if has_full_750 else None,
        'indep_affected_students': indep_c_750,
        'indep_period_penalty': indep_p_750,
        'indep_z1': indep_z1_750,
        'val_details': val_750
    }
    
    with open("results/phase3_10/phase310_results.json", "w") as f:
        json.dump(results, f, indent=2)

    # Check proceed condition for Phase 3.10B
    if not (has_full_750 and hard_viols_750 == 0):
        print(f"\n--> STOPPING: Scope 750 did not produce a complete valid timetable. Will not proceed to Scope 1,000.")
        return

    # ====================================================
    # PHASE 3.10B: 1,000 EXAMS
    # ====================================================
    print("\n" + "="*60)
    print(" PHASE 3.10B: 1,000-EXAM SCALE-UP RUN (pairwise_compact)")
    print("="*60)
    subset_1000 = set(all_exams[:1000])
    
    t0 = time.time()
    m_1000 = BIPTimetablingModel(
        exams_df=data['exams_with_enrollment'],
        periods_df=data['periods'],
        exam_periods_df=data['exam_periods'],
        enrollments_df=data['enrollments'],
        constraints_df=data['constraints'],
        exam_subset=subset_1000,
        formulation='pairwise_compact'
    )
    m_1000.build_model()
    t_1000_build = time.time() - t0
    mem_after_build_1000 = get_peak_memory_mb()
    
    print(f"Model 1,000 Built in {t_1000_build:.2f}s:")
    print(f"  x variables: {len(m_1000.x):,}")
    print(f"  c variables: {len(m_1000.c):,}")
    print(f"  total variables: {m_1000.num_variables:,}")
    print(f"  total constraints: {m_1000.num_constraints:,}")
    print(f"  exact-one constraints: {m_1000.num_exact_one_constraints:,}")
    print(f"  fixed-time constraints: {m_1000.num_fixed_time_constraints:,}")
    print(f"  distribution constraints: {m_1000.num_distribution_constraints:,}")
    print(f"  conflict linking constraints: {m_1000.num_conflict_constraints:,}")
    print(f"  memory: {mem_after_build_1000:.2f} MB")
    
    # 15-minute time limit = 900 seconds
    print("\nStarting CBC Solve for Scope 1000 (time limit: 900s)...")
    t_solve_start = time.time()
    res_1000 = m_1000.solve(time_limit_seconds=900)
    t_1000_solve = time.time() - t_solve_start
    mem_after_solve_1000 = get_peak_memory_mb()
    
    print(f"\nCBC Solve Completed in {t_1000_solve:.2f}s:")
    print(f"  Solver status: {res_1000['status']}")
    print(f"  Scheduled exams: {res_1000['scheduled_exams']} / 1000")
    print(f"  Period penalty: {res_1000['period_penalty']}")
    print(f"  Conflict penalty: {res_1000['conflict_penalty']}")
    print(f"  Objective Z1: {res_1000['objective_value']}")
    
    # Independent validation
    has_full_1000 = (m_1000.timetable_df is not None and len(m_1000.timetable_df) == 1000)
    val_1000 = validator.validate_timetable(m_1000.timetable_df) if has_full_1000 else {}
    indep_p_1000 = sum(p_pen_dict.get(p, 0) for p in m_1000.timetable_df['period_id']) if has_full_1000 else None
    indep_c_1000 = val_1000.get('student_conflicts', {}).get('affected_students', None) if has_full_1000 else None
    indep_z1_1000 = (1.0 * indep_p_1000 + 100.0 * indep_c_1000) if (indep_p_1000 is not None and indep_c_1000 is not None) else None
    
    hard_viols_1000 = (
        val_1000.get('exact_one_assignment', {}).get('violations', 0) +
        val_1000.get('valid_periods', {}).get('violations', 0) +
        val_1000.get('fixed_time_compliance', {}).get('violations', 0) +
        val_1000.get('distribution_compliance', {}).get('violations', 0)
    ) if has_full_1000 else 'INCOMPLETE'
    
    # Classification
    if res_1000['status'] == 'OPTIMAL' and has_full_1000 and hard_viols_1000 == 0:
        classification_1000 = "OPTIMAL"
    elif "FEASIBLE" in res_1000['status'] and has_full_1000 and hard_viols_1000 == 0:
        classification_1000 = "FEASIBLE / TIME LIMIT"
    elif res_1000['status'] == "INFEASIBLE":
        classification_1000 = "INFEASIBLE"
    else:
        classification_1000 = "UNKNOWN / TIME LIMIT"
        
    print(f"\nPhase 3.10B Final Classification: {classification_1000}")
    print(f"Hard Violations: {hard_viols_1000}")
    if has_full_1000:
        print(f"Independent Clashing Pairs: {val_1000['student_conflicts']['conflicting_pairs']}")
        print(f"Independent Affected Students: {indep_c_1000}")
        print(f"Independent Period Penalty: {indep_p_1000}")
        print(f"Independent Z1: {indep_z1_1000}")
        m_1000.timetable_df.to_csv("results/phase3_10/timetable_1000_pairwise_compact.csv", index=False)
        
    results['scope_1000'] = {
        'scope': 1000,
        'classification': classification_1000,
        'status': res_1000['status'],
        'scheduled': res_1000['scheduled_exams'],
        'x_vars': len(m_1000.x),
        'c_vars': len(m_1000.c),
        'total_vars': m_1000.num_variables,
        'total_constraints': m_1000.num_constraints,
        'build_time': round(t_1000_build, 2),
        'solve_time': round(res_1000['runtime'], 2),
        'peak_memory_mb': mem_after_solve_1000,
        'model_period_penalty': res_1000['period_penalty'],
        'model_conflict_penalty': res_1000['conflict_penalty'],
        'model_z1': res_1000['objective_value'],
        'hard_violations': hard_viols_1000,
        'indep_conflict_pairs': val_1000.get('student_conflicts', {}).get('conflicting_pairs', 0) if has_full_1000 else None,
        'indep_affected_students': indep_c_1000,
        'indep_period_penalty': indep_p_1000,
        'indep_z1': indep_z1_1000,
        'val_details': val_1000
    }
    
    with open("results/phase3_10/phase310_results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\nPhase 3.10 Completed Successfully.")

if __name__ == '__main__':
    run_scale_up()
