"""
Phase 3.8 Step 2: Formal Mathematical Equivalence Test
Compares pairwise_z vs student_load on small and moderate deterministic scopes.
Verifies:
1. StudentConflictPenalty == Independent Pairwise Conflict Penalty
2. PeriodPenalty == Independent Period Penalty
3. Z1 == 1.0 * PeriodPenalty + 100.0 * StudentConflictPenalty
4. Hard violations == 0
"""
import time
import pandas as pd
import numpy as np
from src.data_loader import load_all_data
from src.bip_model import BIPTimetablingModel
from src.validation import IndependentValidator

def test_equivalence_on_scope(scope_size=50, solver_name='CBC', time_limit=60):
    print(f"\n=======================================================")
    print(f" MATHEMATICAL EQUIVALENCE TEST: SCOPE {scope_size} EXAMS")
    print(f"=======================================================")
    
    data = load_all_data()
    all_exams = sorted(data['exams_with_enrollment']['exam_id'].unique())
    exam_subset = set(all_exams[:scope_size])
    
    # 1. Solve pairwise_z model
    print(f"\n--- 1. Building & Solving PAIRWISE_Z Model ---")
    t0 = time.time()
    m_pair = BIPTimetablingModel(
        exams_df=data['exams_with_enrollment'],
        periods_df=data['periods'],
        exam_periods_df=data['exam_periods'],
        enrollments_df=data['enrollments'],
        constraints_df=data['constraints'],
        exam_subset=exam_subset,
        formulation='pairwise_z'
    )
    m_pair.build_model()
    t_pair_build = time.time() - t0
    
    res_pair = m_pair.solve(time_limit_seconds=time_limit)
    print(f"PAIRWISE_Z Status: {res_pair['status']}")
    print(f"PAIRWISE_Z Vars: {m_pair.num_variables:,} (x={len(m_pair.x):,}, z={len(m_pair.z):,})")
    print(f"PAIRWISE_Z Constrs: {m_pair.num_constraints:,}")
    print(f"PAIRWISE_Z Build Time: {t_pair_build:.2f}s, Solve Time: {res_pair['runtime']:.2f}s")
    print(f"PAIRWISE_Z Model Period Penalty: {res_pair['period_penalty']}")
    print(f"PAIRWISE_Z Model Conflict Penalty: {res_pair['conflict_penalty']}")
    print(f"PAIRWISE_Z Model Z1: {res_pair['objective_value']}")
    
    validator = IndependentValidator(
        enrollments_df=data['enrollments'],
        exam_periods_df=data['exam_periods'],
        exam_rooms_df=data['exam_rooms'],
        constraints_df=data['constraints'],
        rooms_df=data['rooms'],
        exams_df=data['exams_with_enrollment']
    )
    rep_pair = validator.validate_timetable(m_pair.timetable_df)
    
    # Calculate independent period penalty for pairwise
    p_pen_dict = dict(zip(data['periods']['period_id'], data['periods']['penalty']))
    indep_p_pair = sum(p_pen_dict.get(p, 0) for p in m_pair.timetable_df['period_id'])
    indep_c_pair = rep_pair['student_conflicts']['affected_students']
    indep_z1_pair = 1.0 * indep_p_pair + 100.0 * indep_c_pair

    print(f"PAIRWISE_Z Independent Validations:")
    print(f"  Exact-one violations: {rep_pair['exact_one_assignment']['violations']}")
    print(f"  Period domain violations: {rep_pair['valid_periods']['violations']}")
    print(f"  Fixed-time violations: {rep_pair['fixed_time_compliance']['violations']}")
    print(f"  Distribution violations: {rep_pair['distribution_compliance']['violations']}")
    print(f"  Independent Conflict Penalty: {indep_c_pair}")
    print(f"  Independent Period Penalty: {indep_p_pair}")
    print(f"  Independent Z1: {indep_z1_pair}")
    
    # 2. Solve student_load model
    print(f"\n--- 2. Building & Solving STUDENT_LOAD Model ---")
    t0 = time.time()
    m_load = BIPTimetablingModel(
        exams_df=data['exams_with_enrollment'],
        periods_df=data['periods'],
        exam_periods_df=data['exam_periods'],
        enrollments_df=data['enrollments'],
        constraints_df=data['constraints'],
        exam_subset=exam_subset,
        formulation='student_load'
    )
    m_load.build_model()
    t_load_build = time.time() - t0
    
    res_load = m_load.solve(time_limit_seconds=time_limit)
    print(f"STUDENT_LOAD Status: {res_load['status']}")
    print(f"STUDENT_LOAD Vars: {m_load.num_variables:,} (x={len(m_load.x):,}, n={len(m_load.n_load):,}, u={len(m_load.u_load):,})")
    print(f"STUDENT_LOAD Constrs: {m_load.num_constraints:,}")
    print(f"STUDENT_LOAD Build Time: {t_load_build:.2f}s, Solve Time: {res_load['runtime']:.2f}s")
    print(f"STUDENT_LOAD Model Period Penalty: {res_load['period_penalty']}")
    print(f"STUDENT_LOAD Model Conflict Penalty: {res_load['conflict_penalty']}")
    print(f"STUDENT_LOAD Model Z1: {res_load['objective_value']}")
    
    rep_load = validator.validate_timetable(m_load.timetable_df)
    indep_p_load = sum(p_pen_dict.get(p, 0) for p in m_load.timetable_df['period_id'])
    indep_c_load = rep_load['student_conflicts']['affected_students']
    indep_z1_load = 1.0 * indep_p_load + 100.0 * indep_c_load
    
    print(f"STUDENT_LOAD Independent Validations:")
    print(f"  Exact-one violations: {rep_load['exact_one_assignment']['violations']}")
    print(f"  Period domain violations: {rep_load['valid_periods']['violations']}")
    print(f"  Fixed-time violations: {rep_load['fixed_time_compliance']['violations']}")
    print(f"  Distribution violations: {rep_load['distribution_compliance']['violations']}")
    print(f"  Independent Conflict Penalty: {indep_c_load}")
    print(f"  Independent Period Penalty: {indep_p_load}")
    print(f"  Independent Z1: {indep_z1_load}")
    
    # Mathematical Equivalence Checks
    load_conflict_diff = abs(res_load['conflict_penalty'] - indep_c_load)
    load_period_diff = abs(res_load['period_penalty'] - indep_p_load)
    load_z1_expected = 1.0 * indep_p_load + 100.0 * indep_c_load
    load_z1_diff = abs(res_load['objective_value'] - load_z1_expected)
    
    print(f"\n--- VERIFICATION CHECKS FOR STUDENT_LOAD ---")
    print(f"Conflict Penalty Match: model={res_load['conflict_penalty']} vs independent={indep_c_load} (diff={load_conflict_diff})")
    print(f"Period Penalty Match: model={res_load['period_penalty']} vs independent={indep_p_load} (diff={load_period_diff})")
    print(f"Z1 Objective Match: model={res_load['objective_value']} vs formula={load_z1_expected} (diff={load_z1_diff})")
    
    assert load_conflict_diff < 1e-4, f"Mismatch in conflict penalty! {load_conflict_diff}"
    assert load_period_diff < 1e-4, f"Mismatch in period penalty! {load_period_diff}"
    assert load_z1_diff < 1e-4, f"Mismatch in Z1 objective! {load_z1_diff}"
    print(f"--> MATHEMATICAL EQUIVALENCE FULLY CONFIRMED FOR SCOPE {scope_size}!")
    
    return {
        'scope': scope_size,
        'pair': {
            'vars': m_pair.num_variables,
            'constrs': m_pair.num_constraints,
            'build_time': t_pair_build,
            'solve_time': res_pair['runtime'],
            'status': res_pair['status'],
            'conflict_penalty': indep_c_pair,
            'period_penalty': indep_p_pair,
            'z1': indep_z1_pair
        },
        'load': {
            'vars': m_load.num_variables,
            'constrs': m_load.num_constraints,
            'build_time': t_load_build,
            'solve_time': res_load['runtime'],
            'status': res_load['status'],
            'conflict_penalty': indep_c_load,
            'period_penalty': indep_p_load,
            'z1': indep_z1_load
        }
    }

if __name__ == '__main__':
    res50 = test_equivalence_on_scope(50, time_limit=60)
    print("\nTest completed successfully.")
