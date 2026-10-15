"""
Phase 3.8 Step 3 & 4: Regression suite on scopes 150, 350, 750, 1000
Measures both OLD (pairwise_z) and NEW (student_load) models.
Outputs detailed statistics and independent validations to results/phase3_8/
"""
import time
import json
import pandas as pd
from collections import defaultdict
from src.data_loader import load_all_data
from src.bip_model import BIPTimetablingModel
from src.validation import IndependentValidator

def run_regression_suite():
    data = load_all_data()
    all_exams = sorted(data['exams_with_enrollment']['exam_id'].unique())
    scopes = [150, 350, 750, 1000]
    
    validator = IndependentValidator(
        enrollments_df=data['enrollments'],
        exam_periods_df=data['exam_periods'],
        exam_rooms_df=data['exam_rooms'],
        constraints_df=data['constraints'],
        rooms_df=data['rooms'],
        exams_df=data['exams_with_enrollment']
    )
    p_pen_dict = dict(zip(data['periods']['period_id'], data['periods']['penalty']))
    
    results = {}
    
    for scope in scopes:
        print(f"\n=======================================================")
        print(f" REGRESSION TEST SCOPE: {scope} EXAMS")
        print(f"=======================================================")
        subset = set(all_exams[:scope])
        scope_res = {}
        
        # 1. OLD MODEL: pairwise_z
        print(f"\n--- [SCOPE {scope}] OLD MODEL: pairwise_z ---")
        t0 = time.time()
        m_old = BIPTimetablingModel(
            exams_df=data['exams_with_enrollment'],
            periods_df=data['periods'],
            exam_periods_df=data['exam_periods'],
            enrollments_df=data['enrollments'],
            constraints_df=data['constraints'],
            exam_subset=subset,
            formulation='pairwise_z'
        )
        m_old.build_model()
        t_old_build = time.time() - t0
        
        # Allocate time limit: 60s for 150, 350; 120s for 750, 1000
        tl = 60 if scope <= 350 else 180
        res_old = m_old.solve(time_limit_seconds=tl)
        
        rep_old = validator.validate_timetable(m_old.timetable_df) if m_old.timetable_df is not None else {}
        indep_p_old = sum(p_pen_dict.get(p, 0) for p in m_old.timetable_df['period_id']) if m_old.timetable_df is not None else None
        indep_c_old = rep_old.get('student_conflicts', {}).get('affected_students', None)
        indep_z1_old = (1.0 * indep_p_old + 100.0 * indep_c_old) if (indep_p_old is not None and indep_c_old is not None) else None
        
        scope_res['pairwise_z'] = {
            'scope': scope,
            'status': res_old['status'],
            'scheduled_exams': res_old['scheduled_exams'],
            'x_vars': len(m_old.x),
            'z_vars': len(m_old.z),
            'total_vars': m_old.num_variables,
            'total_constraints': m_old.num_constraints,
            'build_time': round(t_old_build, 2),
            'solve_time': round(res_old['runtime'], 2),
            'model_period_penalty': res_old['period_penalty'],
            'model_conflict_penalty': res_old['conflict_penalty'],
            'model_z1': res_old['objective_value'],
            'indep_period_penalty': indep_p_old,
            'indep_conflict_penalty': indep_c_old,
            'indep_z1': indep_z1_old,
            'hard_violations': (
                rep_old.get('exact_one_assignment', {}).get('violations', 0) +
                rep_old.get('valid_periods', {}).get('violations', 0) +
                rep_old.get('fixed_time_compliance', {}).get('violations', 0) +
                rep_old.get('distribution_compliance', {}).get('violations', 0)
            ) if rep_old else 'N/A'
        }
        
        print(f"OLD: Status={res_old['status']}, Scheduled={res_old['scheduled_exams']}/{scope}, Vars={m_old.num_variables:,}, Constrs={m_old.num_constraints:,}, Build={t_old_build:.2f}s, Solve={res_old['runtime']:.2f}s, Z1={res_old['objective_value']}")
        
        # 2. NEW MODEL: student_load
        print(f"\n--- [SCOPE {scope}] NEW MODEL: student_load ---")
        t0 = time.time()
        m_new = BIPTimetablingModel(
            exams_df=data['exams_with_enrollment'],
            periods_df=data['periods'],
            exam_periods_df=data['exam_periods'],
            enrollments_df=data['enrollments'],
            constraints_df=data['constraints'],
            exam_subset=subset,
            formulation='student_load'
        )
        m_new.build_model()
        t_new_build = time.time() - t0
        
        res_new = m_new.solve(time_limit_seconds=tl)
        
        rep_new = validator.validate_timetable(m_new.timetable_df) if m_new.timetable_df is not None else {}
        indep_p_new = sum(p_pen_dict.get(p, 0) for p in m_new.timetable_df['period_id']) if m_new.timetable_df is not None else None
        indep_c_new = rep_new.get('student_conflicts', {}).get('affected_students', None)
        indep_z1_new = (1.0 * indep_p_new + 100.0 * indep_c_new) if (indep_p_new is not None and indep_c_new is not None) else None
        
        scope_res['student_load'] = {
            'scope': scope,
            'status': res_new['status'],
            'scheduled_exams': res_new['scheduled_exams'],
            'x_vars': len(m_new.x),
            'n_vars': len(m_new.n_load),
            'u_vars': len(m_new.u_load),
            'total_vars': m_new.num_variables,
            'total_constraints': m_new.num_constraints,
            'build_time': round(t_new_build, 2),
            'solve_time': round(res_new['runtime'], 2),
            'model_period_penalty': res_new['period_penalty'],
            'model_conflict_penalty': res_new['conflict_penalty'],
            'model_z1': res_new['objective_value'],
            'indep_period_penalty': indep_p_new,
            'indep_conflict_penalty': indep_c_new,
            'indep_z1': indep_z1_new,
            'hard_violations': (
                rep_new.get('exact_one_assignment', {}).get('violations', 0) +
                rep_new.get('valid_periods', {}).get('violations', 0) +
                rep_new.get('fixed_time_compliance', {}).get('violations', 0) +
                rep_new.get('distribution_compliance', {}).get('violations', 0)
            ) if rep_new else 'N/A'
        }
        
        print(f"NEW: Status={res_new['status']}, Scheduled={res_new['scheduled_exams']}/{scope}, Vars={m_new.num_variables:,} (x={len(m_new.x):,}, n={len(m_new.n_load):,}, u={len(m_new.u_load):,}), Constrs={m_new.num_constraints:,}, Build={t_new_build:.2f}s, Solve={res_new['runtime']:.2f}s, Z1={res_new['objective_value']}")
        
        results[f"scope_{scope}"] = scope_res
        
        # Save incremental results to file
        with open("results/phase3_8/regression_results.json", "w") as f:
            json.dump(results, f, indent=2)
            
    print("\n=======================================================")
    print(" ALL REGRESSION SCOPES COMPLETED")
    print("=======================================================")

if __name__ == '__main__':
    run_regression_suite()
