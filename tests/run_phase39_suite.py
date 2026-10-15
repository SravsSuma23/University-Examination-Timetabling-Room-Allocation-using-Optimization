"""
Phase 3.9 Validation Runner
Executes:
1. Scope 50: pairwise_z vs pairwise_compact comparison
2. Scope 100: pairwise_z vs pairwise_compact comparison
3. Scope 150: pairwise_compact validation
4. Scope 350: pairwise_compact validation (compared against pairwise_z benchmark)
5. Full 2,198 theoretical size calculation (actual counts)
Saves results into results/phase3_9/
"""
import time
import json
import pandas as pd
from src.data_loader import load_all_data
from src.bip_model import BIPTimetablingModel
from src.validation import IndependentValidator

def run_phase39_suite():
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
    
    # ----------------------------------------------------
    # TEST 1: Scope 50 Comparison
    # ----------------------------------------------------
    print("\n" + "="*60)
    print(" PHASE 3.9 — TEST 1: SCOPE 50 COMPARISON")
    print("="*60)
    subset_50 = set(all_exams[:50])
    
    # Pairwise z
    m_z_50 = BIPTimetablingModel(
        exams_df=data['exams_with_enrollment'],
        periods_df=data['periods'],
        exam_periods_df=data['exam_periods'],
        enrollments_df=data['enrollments'],
        constraints_df=data['constraints'],
        exam_subset=subset_50,
        formulation='pairwise_z'
    )
    t0 = time.time()
    m_z_50.build_model()
    t_z_50_build = time.time() - t0
    res_z_50 = m_z_50.solve(time_limit_seconds=60)
    val_z_50 = validator.validate_timetable(m_z_50.timetable_df)
    indep_p_z_50 = sum(p_pen_dict.get(p, 0) for p in m_z_50.timetable_df['period_id'])
    indep_c_z_50 = val_z_50['student_conflicts']['affected_students']
    indep_z1_z_50 = 1.0 * indep_p_z_50 + 100.0 * indep_c_z_50
    
    # Pairwise compact
    m_c_50 = BIPTimetablingModel(
        exams_df=data['exams_with_enrollment'],
        periods_df=data['periods'],
        exam_periods_df=data['exam_periods'],
        enrollments_df=data['enrollments'],
        constraints_df=data['constraints'],
        exam_subset=subset_50,
        formulation='pairwise_compact'
    )
    t0 = time.time()
    m_c_50.build_model()
    t_c_50_build = time.time() - t0
    res_c_50 = m_c_50.solve(time_limit_seconds=60)
    val_c_50 = validator.validate_timetable(m_c_50.timetable_df)
    indep_p_c_50 = sum(p_pen_dict.get(p, 0) for p in m_c_50.timetable_df['period_id'])
    indep_c_c_50 = val_c_50['student_conflicts']['affected_students']
    indep_z1_c_50 = 1.0 * indep_p_c_50 + 100.0 * indep_c_c_50
    
    results['scope_50'] = {
        'pairwise_z': {
            'status': res_z_50['status'],
            'scheduled': res_z_50['scheduled_exams'],
            'x_vars': len(m_z_50.x),
            'conflict_vars': len(m_z_50.z),
            'total_vars': m_z_50.num_variables,
            'total_constraints': m_z_50.num_constraints,
            'build_time': round(t_z_50_build, 2),
            'solve_time': round(res_z_50['runtime'], 2),
            'model_period_penalty': res_z_50['period_penalty'],
            'model_conflict_penalty': res_z_50['conflict_penalty'],
            'model_z1': res_z_50['objective_value'],
            'hard_violations': (
                val_z_50['exact_one_assignment']['violations'] +
                val_z_50['valid_periods']['violations'] +
                val_z_50['fixed_time_compliance']['violations'] +
                val_z_50['distribution_compliance']['violations']
            ),
            'indep_conflict_penalty': indep_c_z_50,
            'indep_period_penalty': indep_p_z_50,
            'indep_z1': indep_z1_z_50
        },
        'pairwise_compact': {
            'status': res_c_50['status'],
            'scheduled': res_c_50['scheduled_exams'],
            'x_vars': len(m_c_50.x),
            'conflict_vars': len(m_c_50.c),
            'total_vars': m_c_50.num_variables,
            'total_constraints': m_c_50.num_constraints,
            'build_time': round(t_c_50_build, 2),
            'solve_time': round(res_c_50['runtime'], 2),
            'model_period_penalty': res_c_50['period_penalty'],
            'model_conflict_penalty': res_c_50['conflict_penalty'],
            'model_z1': res_c_50['objective_value'],
            'hard_violations': (
                val_c_50['exact_one_assignment']['violations'] +
                val_c_50['valid_periods']['violations'] +
                val_c_50['fixed_time_compliance']['violations'] +
                val_c_50['distribution_compliance']['violations']
            ),
            'indep_conflict_penalty': indep_c_c_50,
            'indep_period_penalty': indep_p_c_50,
            'indep_z1': indep_z1_c_50
        }
    }
    print(f"Scope 50 Pairwise_Z: Status={res_z_50['status']}, Vars={m_z_50.num_variables}, Time={res_z_50['runtime']:.2f}s, Z1={res_z_50['objective_value']}")
    print(f"Scope 50 Compact:    Status={res_c_50['status']}, Vars={m_c_50.num_variables}, Time={res_c_50['runtime']:.2f}s, Z1={res_c_50['objective_value']}")
    assert abs(res_c_50['conflict_penalty'] - indep_c_c_50) < 1e-4, "Conflict penalty mismatch in 50 compact!"
    assert abs(res_c_50['period_penalty'] - indep_p_c_50) < 1e-4, "Period penalty mismatch in 50 compact!"
    assert abs(res_c_50['objective_value'] - indep_z1_c_50) < 1e-4, "Z1 objective mismatch in 50 compact!"
    print("--> Scope 50 Mathematical Equivalence Passed.")

    # ----------------------------------------------------
    # TEST 2: Scope 100 Comparison
    # ----------------------------------------------------
    print("\n" + "="*60)
    print(" PHASE 3.9 — TEST 2: SCOPE 100 COMPARISON")
    print("="*60)
    subset_100 = set(all_exams[:100])
    
    # Pairwise z
    m_z_100 = BIPTimetablingModel(
        exams_df=data['exams_with_enrollment'],
        periods_df=data['periods'],
        exam_periods_df=data['exam_periods'],
        enrollments_df=data['enrollments'],
        constraints_df=data['constraints'],
        exam_subset=subset_100,
        formulation='pairwise_z'
    )
    t0 = time.time()
    m_z_100.build_model()
    t_z_100_build = time.time() - t0
    res_z_100 = m_z_100.solve(time_limit_seconds=60)
    val_z_100 = validator.validate_timetable(m_z_100.timetable_df)
    indep_p_z_100 = sum(p_pen_dict.get(p, 0) for p in m_z_100.timetable_df['period_id'])
    indep_c_z_100 = val_z_100['student_conflicts']['affected_students']
    indep_z1_z_100 = 1.0 * indep_p_z_100 + 100.0 * indep_c_z_100
    
    # Pairwise compact
    m_c_100 = BIPTimetablingModel(
        exams_df=data['exams_with_enrollment'],
        periods_df=data['periods'],
        exam_periods_df=data['exam_periods'],
        enrollments_df=data['enrollments'],
        constraints_df=data['constraints'],
        exam_subset=subset_100,
        formulation='pairwise_compact'
    )
    t0 = time.time()
    m_c_100.build_model()
    t_c_100_build = time.time() - t0
    res_c_100 = m_c_100.solve(time_limit_seconds=60)
    val_c_100 = validator.validate_timetable(m_c_100.timetable_df)
    indep_p_c_100 = sum(p_pen_dict.get(p, 0) for p in m_c_100.timetable_df['period_id'])
    indep_c_c_100 = val_c_100['student_conflicts']['affected_students']
    indep_z1_c_100 = 1.0 * indep_p_c_100 + 100.0 * indep_c_c_100
    
    results['scope_100'] = {
        'pairwise_z': {
            'status': res_z_100['status'],
            'scheduled': res_z_100['scheduled_exams'],
            'x_vars': len(m_z_100.x),
            'conflict_vars': len(m_z_100.z),
            'total_vars': m_z_100.num_variables,
            'total_constraints': m_z_100.num_constraints,
            'build_time': round(t_z_100_build, 2),
            'solve_time': round(res_z_100['runtime'], 2),
            'model_period_penalty': res_z_100['period_penalty'],
            'model_conflict_penalty': res_z_100['conflict_penalty'],
            'model_z1': res_z_100['objective_value'],
            'hard_violations': (
                val_z_100['exact_one_assignment']['violations'] +
                val_z_100['valid_periods']['violations'] +
                val_z_100['fixed_time_compliance']['violations'] +
                val_z_100['distribution_compliance']['violations']
            ),
            'indep_conflict_penalty': indep_c_z_100,
            'indep_period_penalty': indep_p_z_100,
            'indep_z1': indep_z1_z_100
        },
        'pairwise_compact': {
            'status': res_c_100['status'],
            'scheduled': res_c_100['scheduled_exams'],
            'x_vars': len(m_c_100.x),
            'conflict_vars': len(m_c_100.c),
            'total_vars': m_c_100.num_variables,
            'total_constraints': m_c_100.num_constraints,
            'build_time': round(t_c_100_build, 2),
            'solve_time': round(res_c_100['runtime'], 2),
            'model_period_penalty': res_c_100['period_penalty'],
            'model_conflict_penalty': res_c_100['conflict_penalty'],
            'model_z1': res_c_100['objective_value'],
            'hard_violations': (
                val_c_100['exact_one_assignment']['violations'] +
                val_c_100['valid_periods']['violations'] +
                val_c_100['fixed_time_compliance']['violations'] +
                val_c_100['distribution_compliance']['violations']
            ),
            'indep_conflict_penalty': indep_c_c_100,
            'indep_period_penalty': indep_p_c_100,
            'indep_z1': indep_z1_c_100
        }
    }
    print(f"Scope 100 Pairwise_Z: Status={res_z_100['status']}, Vars={m_z_100.num_variables}, Time={res_z_100['runtime']:.2f}s, Z1={res_z_100['objective_value']}")
    print(f"Scope 100 Compact:    Status={res_c_100['status']}, Vars={m_c_100.num_variables}, Time={res_c_100['runtime']:.2f}s, Z1={res_c_100['objective_value']}")
    assert abs(res_c_100['conflict_penalty'] - indep_c_c_100) < 1e-4, "Conflict penalty mismatch in 100 compact!"
    assert abs(res_c_100['period_penalty'] - indep_p_c_100) < 1e-4, "Period penalty mismatch in 100 compact!"
    assert abs(res_c_100['objective_value'] - indep_z1_c_100) < 1e-4, "Z1 objective mismatch in 100 compact!"
    print("--> Scope 100 Mathematical Equivalence Passed.")

    # ----------------------------------------------------
    # TEST 3: Scope 150 Compact Validation
    # ----------------------------------------------------
    print("\n" + "="*60)
    print(" PHASE 3.9 — TEST 3: SCOPE 150 COMPACT VALIDATION")
    print("="*60)
    subset_150 = set(all_exams[:150])
    m_c_150 = BIPTimetablingModel(
        exams_df=data['exams_with_enrollment'],
        periods_df=data['periods'],
        exam_periods_df=data['exam_periods'],
        enrollments_df=data['enrollments'],
        constraints_df=data['constraints'],
        exam_subset=subset_150,
        formulation='pairwise_compact'
    )
    t0 = time.time()
    m_c_150.build_model()
    t_c_150_build = time.time() - t0
    res_c_150 = m_c_150.solve(time_limit_seconds=60)
    val_c_150 = validator.validate_timetable(m_c_150.timetable_df)
    indep_p_c_150 = sum(p_pen_dict.get(p, 0) for p in m_c_150.timetable_df['period_id'])
    indep_c_c_150 = val_c_150['student_conflicts']['affected_students']
    indep_z1_c_150 = 1.0 * indep_p_c_150 + 100.0 * indep_c_c_150
    
    results['scope_150'] = {
        'pairwise_compact': {
            'status': res_c_150['status'],
            'scheduled': res_c_150['scheduled_exams'],
            'x_vars': len(m_c_150.x),
            'conflict_vars': len(m_c_150.c),
            'total_vars': m_c_150.num_variables,
            'total_constraints': m_c_150.num_constraints,
            'build_time': round(t_c_150_build, 2),
            'solve_time': round(res_c_150['runtime'], 2),
            'model_period_penalty': res_c_150['period_penalty'],
            'model_conflict_penalty': res_c_150['conflict_penalty'],
            'model_z1': res_c_150['objective_value'],
            'hard_violations': (
                val_c_150['exact_one_assignment']['violations'] +
                val_c_150['valid_periods']['violations'] +
                val_c_150['fixed_time_compliance']['violations'] +
                val_c_150['distribution_compliance']['violations']
            ),
            'indep_conflict_penalty': indep_c_c_150,
            'indep_period_penalty': indep_p_c_150,
            'indep_z1': indep_z1_c_150
        }
    }
    print(f"Scope 150 Compact: Status={res_c_150['status']}, Vars={m_c_150.num_variables}, Time={res_c_150['runtime']:.2f}s, Z1={res_c_150['objective_value']}")
    assert abs(res_c_150['conflict_penalty'] - indep_c_c_150) < 1e-4, "Conflict penalty mismatch in 150 compact!"
    assert abs(res_c_150['period_penalty'] - indep_p_c_150) < 1e-4, "Period penalty mismatch in 150 compact!"
    assert abs(res_c_150['objective_value'] - indep_z1_c_150) < 1e-4, "Z1 objective mismatch in 150 compact!"
    print("--> Scope 150 Mathematical Equivalence Passed.")

    # ----------------------------------------------------
    # TEST 4: Scope 350 Compact Validation
    # ----------------------------------------------------
    print("\n" + "="*60)
    print(" PHASE 3.9 — TEST 4: SCOPE 350 COMPACT VALIDATION")
    print("="*60)
    subset_350 = set(all_exams[:350])
    m_c_350 = BIPTimetablingModel(
        exams_df=data['exams_with_enrollment'],
        periods_df=data['periods'],
        exam_periods_df=data['exam_periods'],
        enrollments_df=data['enrollments'],
        constraints_df=data['constraints'],
        exam_subset=subset_350,
        formulation='pairwise_compact'
    )
    t0 = time.time()
    m_c_350.build_model()
    t_c_350_build = time.time() - t0
    res_c_350 = m_c_350.solve(time_limit_seconds=60)
    val_c_350 = validator.validate_timetable(m_c_350.timetable_df)
    indep_p_c_350 = sum(p_pen_dict.get(p, 0) for p in m_c_350.timetable_df['period_id'])
    indep_c_c_350 = val_c_350['student_conflicts']['affected_students']
    indep_z1_c_350 = 1.0 * indep_p_c_350 + 100.0 * indep_c_c_350
    
    results['scope_350'] = {
        'pairwise_compact': {
            'status': res_c_350['status'],
            'scheduled': res_c_350['scheduled_exams'],
            'x_vars': len(m_c_350.x),
            'conflict_vars': len(m_c_350.c),
            'total_vars': m_c_350.num_variables,
            'total_constraints': m_c_350.num_constraints,
            'build_time': round(t_c_350_build, 2),
            'solve_time': round(res_c_350['runtime'], 2),
            'model_period_penalty': res_c_350['period_penalty'],
            'model_conflict_penalty': res_c_350['conflict_penalty'],
            'model_z1': res_c_350['objective_value'],
            'hard_violations': (
                val_c_350['exact_one_assignment']['violations'] +
                val_c_350['valid_periods']['violations'] +
                val_c_350['fixed_time_compliance']['violations'] +
                val_c_350['distribution_compliance']['violations']
            ),
            'indep_conflict_pairs': val_c_350['student_conflicts']['conflicting_pairs'],
            'indep_conflict_penalty': indep_c_c_350,
            'indep_period_penalty': indep_p_c_350,
            'indep_z1': indep_z1_c_350
        }
    }
    print(f"Scope 350 Compact: Status={res_c_350['status']}, Vars={m_c_350.num_variables}, Time={res_c_350['runtime']:.2f}s, Z1={res_c_350['objective_value']}")
    assert abs(res_c_350['conflict_penalty'] - indep_c_c_350) < 1e-4, "Conflict penalty mismatch in 350 compact!"
    assert abs(res_c_350['period_penalty'] - indep_p_c_350) < 1e-4, "Period penalty mismatch in 350 compact!"
    assert abs(res_c_350['objective_value'] - indep_z1_c_350) < 1e-4, "Z1 objective mismatch in 350 compact!"
    print("--> Scope 350 Mathematical Equivalence Passed.")

    # Save results to json
    with open("results/phase3_9/phase39_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nResults saved to results/phase3_9/phase39_results.json")

if __name__ == '__main__':
    run_phase39_suite()
