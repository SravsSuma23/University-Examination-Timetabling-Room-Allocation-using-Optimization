"""
Phase 3.9.1 Investigation Script
Audits and resolves the Scope 350 objective discrepancy between pairwise_z and pairwise_compact.
"""
import json
import time
import pandas as pd
from src.data_loader import load_all_data
from src.bip_model import BIPTimetablingModel
from src.validation import IndependentValidator
from src.distribution_constraints import parse_distribution_constraints

def run_investigation():
    data = load_all_data()
    all_exams = sorted(data['exams_with_enrollment']['exam_id'].unique())
    subset_350 = set(all_exams[:350])
    p_pen = dict(zip(data['periods']['period_id'], data['periods']['penalty']))
    
    print("="*60)
    print(" PHASE 3.9.1: SCOPE 350 FORMULATION EQUIVALENCE AUDIT")
    print("="*60)

    # 1. Build and Solve pairwise_z with 120s limit
    print("\n--- 1. Running PAIRWISE_Z Model ---")
    m_z = BIPTimetablingModel(
        exams_df=data['exams_with_enrollment'],
        periods_df=data['periods'],
        exam_periods_df=data['exam_periods'],
        enrollments_df=data['enrollments'],
        constraints_df=data['constraints'],
        exam_subset=subset_350,
        formulation='pairwise_z'
    )
    t0 = time.time()
    m_z.build_model()
    t_z_build = time.time() - t0
    res_z = m_z.solve(time_limit_seconds=120)
    
    # 2. Build and Solve pairwise_compact with 120s limit
    print("\n--- 2. Running PAIRWISE_COMPACT Model ---")
    m_c = BIPTimetablingModel(
        exams_df=data['exams_with_enrollment'],
        periods_df=data['periods'],
        exam_periods_df=data['exam_periods'],
        enrollments_df=data['enrollments'],
        constraints_df=data['constraints'],
        exam_subset=subset_350,
        formulation='pairwise_compact'
    )
    t0 = time.time()
    m_c.build_model()
    t_c_build = time.time() - t0
    res_c = m_c.solve(time_limit_seconds=120)

    print("\n--- 3. Direct Solver Reporting ---")
    print(f"PAIRWISE_Z:       status={res_z['status']}, obj={res_z['objective_value']}, period_pen={res_z['period_penalty']}, conflict_pen={res_z['conflict_penalty']}, runtime={res_z['runtime']:.2f}s")
    print(f"PAIRWISE_COMPACT: status={res_c['status']}, obj={res_c['objective_value']}, period_pen={res_c['period_penalty']}, conflict_pen={res_c['conflict_penalty']}, runtime={res_c['runtime']:.2f}s")

    # 3. Independent Validation
    validator = IndependentValidator(
        enrollments_df=data['enrollments'],
        exam_periods_df=data['exam_periods'],
        exam_rooms_df=data['exam_rooms'],
        constraints_df=data['constraints'],
        rooms_df=data['rooms'],
        exams_df=data['exams_with_enrollment']
    )
    v_z = validator.validate_timetable(m_z.timetable_df)
    v_c = validator.validate_timetable(m_c.timetable_df)

    indep_p_z = sum(p_pen.get(p, 0) for p in m_z.timetable_df['period_id'])
    indep_c_z = v_z['student_conflicts']['affected_students']
    indep_z1_z = 1.0 * indep_p_z + 100.0 * indep_c_z

    indep_p_c = sum(p_pen.get(p, 0) for p in m_c.timetable_df['period_id'])
    indep_c_c = v_c['student_conflicts']['affected_students']
    indep_z1_c = 1.0 * indep_p_c + 100.0 * indep_c_c

    print("\n--- 4. Independent Validation Results ---")
    print(f"INDEP Z: period_pen={indep_p_z}, conflict_pen={indep_c_z}, Z1={indep_z1_z}")
    print(f"  Exact-one violations: {v_z['exact_one_assignment']['violations']}")
    print(f"  Valid-period violations: {v_z['valid_periods']['violations']}")
    print(f"  Fixed-time violations: {v_z['fixed_time_compliance']['violations']}")
    print(f"  Distribution violations: {v_z['distribution_compliance']['violations']}")

    print(f"INDEP C: period_pen={indep_p_c}, conflict_pen={indep_c_c}, Z1={indep_z1_c}")
    print(f"  Exact-one violations: {v_c['exact_one_assignment']['violations']}")
    print(f"  Valid-period violations: {v_c['valid_periods']['violations']}")
    print(f"  Fixed-time violations: {v_c['fixed_time_compliance']['violations']}")
    print(f"  Distribution violations: {v_c['distribution_compliance']['violations']}")

    # 4. Save detailed timetable comparisons
    df_compare = pd.DataFrame({
        'exam_id': sorted(list(subset_350)),
    })
    tt_z_map = dict(zip(m_z.timetable_df['exam_id'], m_z.timetable_df['period_id']))
    tt_c_map = dict(zip(m_c.timetable_df['exam_id'], m_c.timetable_df['period_id']))
    
    df_compare['period_z'] = df_compare['exam_id'].map(tt_z_map)
    df_compare['period_c'] = df_compare['exam_id'].map(tt_c_map)
    df_compare['pen_z'] = df_compare['period_z'].map(p_pen)
    df_compare['pen_c'] = df_compare['period_c'].map(p_pen)
    df_compare['allowed_periods'] = df_compare['exam_id'].map(lambda e: sorted(list(m_z.allowed_periods[e])))
    df_compare['fixed_status'] = df_compare['allowed_periods'].map(lambda p: len(p) == 1)

    df_compare.to_csv("results/phase3_9_1/scope350_timetable_comparison.csv", index=False)
    m_z.timetable_df.to_csv("results/phase3_9_1/timetable_350_pairwise_z.csv", index=False)
    m_c.timetable_df.to_csv("results/phase3_9_1/timetable_350_pairwise_compact.csv", index=False)

    # 5. Non-zero penalty exam investigation
    non_zero_z = df_compare[df_compare['pen_z'] > 0]
    non_zero_c = df_compare[df_compare['pen_c'] > 0]
    print(f"\nNon-zero penalty exams in Pairwise_Z: {len(non_zero_z)}")
    if len(non_zero_z) > 0:
        print(non_zero_z[['exam_id', 'period_z', 'pen_z', 'allowed_periods', 'fixed_status']])

    print(f"Non-zero penalty exams in Pairwise_Compact: {len(non_zero_c)}")
    if len(non_zero_c) > 0:
        print(non_zero_c[['exam_id', 'period_c', 'pen_c', 'allowed_periods', 'fixed_status']])

    # 6. Cross evaluation test
    # Evaluate Compact Timetable in Pairwise_Z Formulation
    cross_z_on_c_timetable = 0.0
    for (e, t), var in m_z.x.items():
        if tt_c_map.get(e) == t:
            cross_z_on_c_timetable += p_pen.get(t, 0)
    print(f"\nCROSS EVALUATION: Compact timetable evaluated under pairwise_z period penalty: {cross_z_on_c_timetable}")

    # Evaluate Pairwise_Z Timetable under Pairwise_Compact Formulation
    cross_c_on_z_timetable = 0.0
    for (e, t), var in m_c.x.items():
        if tt_z_map.get(e) == t:
            cross_c_on_z_timetable += p_pen.get(t, 0)
    print(f"CROSS EVALUATION: Pairwise_z timetable evaluated under compact period penalty: {cross_c_on_z_timetable}")

    # 7. Distribution Constraints Audit
    rules = parse_distribution_constraints(data['constraints'])
    dist_audit = []
    total_dist_constrs_full = 0
    total_dist_constrs_350 = 0
    for r in rules:
        rel_full = [e for e in r.exam_ids if e in m_z.active_exams_set] # full benchmark set
        # for 350 scope:
        rel_350 = [e for e in r.exam_ids if e in subset_350]
        
        # count for full:
        c_full = 0
        if r.constraint_type == 'same-period' and len(r.exam_ids) >= 2:
            base = r.exam_ids[0]
            for other in r.exam_ids[1:]:
                c_full += 29
        elif r.constraint_type == 'different-period' and len(r.exam_ids) >= 2:
            for i in range(len(r.exam_ids)):
                for j in range(i+1, len(r.exam_ids)):
                    c_full += 29
        elif r.constraint_type == 'precedence' and len(r.exam_ids) >= 2:
            c_full += 1

        # count for 350:
        c_350 = 0
        if r.constraint_type == 'same-period' and len(rel_350) >= 2:
            base = rel_350[0]
            for other in rel_350[1:]:
                all_t = m_z.allowed_periods[base].union(m_z.allowed_periods[other])
                c_350 += len(all_t)
        elif r.constraint_type == 'different-period' and len(rel_350) >= 2:
            for i in range(len(rel_350)):
                for j in range(i+1, len(rel_350)):
                    com_t = m_z.allowed_periods[rel_350[i]].intersection(m_z.allowed_periods[rel_350[j]])
                    c_350 += len(com_t)
        elif r.constraint_type == 'precedence' and len(rel_350) >= 2:
            c_350 += 1
            
        dist_audit.append({
            'rule_id': r.constraint_id,
            'type': r.constraint_type,
            'exam_count_total': len(r.exam_ids),
            'exam_count_scope350': len(rel_350),
            'generated_constrs_scope350': c_350
        })

    summary = {
        'scope': 350,
        'pairwise_z': {
            'vars': m_z.num_variables,
            'x_vars': len(m_z.x),
            'z_vars': len(m_z.z),
            'constraints': m_z.num_constraints,
            'exact_one_constrs': m_z.num_exact_one_constraints,
            'fixed_time_constrs': m_z.num_fixed_time_constraints,
            'conflict_constrs': m_z.num_conflict_constraints,
            'dist_constrs': m_z.num_distribution_constraints,
            'build_time': round(t_z_build, 2),
            'solve_time': round(res_z['runtime'], 2),
            'status': res_z['status'],
            'model_period_penalty': res_z['period_penalty'],
            'model_conflict_penalty': res_z['conflict_penalty'],
            'model_z1': res_z['objective_value'],
            'indep_period_penalty': indep_p_z,
            'indep_conflict_penalty': indep_c_z,
            'indep_z1': indep_z1_z,
            'hard_violations': (
                v_z['exact_one_assignment']['violations'] +
                v_z['valid_periods']['violations'] +
                v_z['fixed_time_compliance']['violations'] +
                v_z['distribution_compliance']['violations']
            )
        },
        'pairwise_compact': {
            'vars': m_c.num_variables,
            'x_vars': len(m_c.x),
            'c_vars': len(m_c.c),
            'constraints': m_c.num_constraints,
            'exact_one_constrs': m_c.num_exact_one_constraints,
            'fixed_time_constrs': m_c.num_fixed_time_constraints,
            'conflict_constrs': m_c.num_conflict_constraints,
            'dist_constrs': m_c.num_distribution_constraints,
            'build_time': round(t_c_build, 2),
            'solve_time': round(res_c['runtime'], 2),
            'status': res_c['status'],
            'model_period_penalty': res_c['period_penalty'],
            'model_conflict_penalty': res_c['conflict_penalty'],
            'model_z1': res_c['objective_value'],
            'indep_period_penalty': indep_p_c,
            'indep_conflict_penalty': indep_c_c,
            'indep_z1': indep_z1_c,
            'hard_violations': (
                v_c['exact_one_assignment']['violations'] +
                v_c['valid_periods']['violations'] +
                v_c['fixed_time_compliance']['violations'] +
                v_c['distribution_compliance']['violations']
            )
        },
        'distribution_rules_audit': dist_audit
    }

    with open("results/phase3_9_1/phase391_audit_results.json", "w") as f:
        json.dump(summary, f, indent=2)

    print("\nAudit complete. Results saved to results/phase3_9_1/phase391_audit_results.json")

if __name__ == '__main__':
    run_investigation()
