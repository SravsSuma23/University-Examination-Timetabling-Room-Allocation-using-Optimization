"""
bip_model.py
============
Mathematical formulation and solver execution for Stage 1:
Examination Timetabling using Binary Integer Programming (BIP).

Decision Variable:
x[e, t] ∈ {0, 1} : 1 if examination e is assigned to period t, 0 otherwise.

Objective:
Minimize undesirable examination-period penalties + conflict penalization:
min ∑_{e} ∑_{t ∈ T_e} p_t · x[e, t] + M · ∑ v
"""

import time
from collections import defaultdict
from typing import Dict, List, Set, Tuple, Optional, Any
from pathlib import Path
import pandas as pd
import numpy as np
import pulp

from src.conflict_builder import ConflictGraph, get_conflict_graph, PREASSIGNMENT_CONFLICT_EXEMPTIONS
from src.distribution_constraints import parse_distribution_constraints, DistributionConstraint


class BIPTimetablingModel:
    """
    Binary Integer Programming model for Examination Timetabling.
    """

    def __init__(
        self,
        exams_df: pd.DataFrame,
        periods_df: pd.DataFrame,
        exam_periods_df: pd.DataFrame,
        enrollments_df: pd.DataFrame,
        constraints_df: pd.DataFrame,
        exam_subset: Optional[List[int]] = None,
        exam_rooms_df: Optional[pd.DataFrame] = None,
        formulation: str = "pairwise_compact",
        max_exams_per_period: Optional[int] = None,
    ):
        self.exams_df = exams_df
        self.periods_df = periods_df
        self.exam_periods_df = exam_periods_df
        self.enrollments_df = enrollments_df
        self.constraints_df = constraints_df
        self.exam_subset = exam_subset
        self.exam_rooms_df = exam_rooms_df
        self.formulation = formulation
        self.max_exams_per_period = max_exams_per_period

        # Precompute mappings
        self._prepare_data()

        # Model and solution tracking
        self.prob: Optional[pulp.LpProblem] = None
        self.x: Dict[Tuple[int, int], pulp.LpVariable] = {}
        self.z: Dict[Tuple[int, int, int], pulp.LpVariable] = {}
        self.c: Dict[Tuple[int, int], pulp.LpVariable] = {}
        self.n_load: Dict[Tuple[int, int], pulp.LpVariable] = {}
        self.u_load: Dict[Tuple[int, int, int], pulp.LpVariable] = {}
        self.solver_status: str = "NOT_BUILT"
        self.runtime_seconds: float = 0.0
        self.objective_value: Optional[float] = None
        self.num_variables: int = 0
        self.num_x_variables: int = 0
        self.num_z_variables: int = 0
        self.num_c_variables: int = 0
        self.num_n_variables: int = 0
        self.num_u_variables: int = 0
        self.num_constraints: int = 0
        self.num_exact_one_constraints: int = 0
        self.num_conflict_constraints: int = 0
        self.num_fixed_time_constraints: int = 0
        self.num_distribution_constraints: int = 0
        self.timetable_df: Optional[pd.DataFrame] = None

    def _prepare_data(self):
        # 1. Determine active exams
        if self.exam_subset is not None:
            self.active_exams = sorted(list(set(self.exam_subset)))
        else:
            self.active_exams = sorted(self.exams_df["exam_id"].tolist())
        self.active_exams_set = set(self.active_exams)

        # 2. Periods and period penalties
        self.periods = sorted(self.periods_df["period_id"].tolist())
        self.period_penalties = dict(zip(self.periods_df["period_id"], self.periods_df["penalty"]))
        self.period_info = self.periods_df.set_index("period_id").to_dict(orient="index")

        # 3. Allowed periods per exam
        self.allowed_periods = defaultdict(set)
        for eid, pid in zip(self.exam_periods_df["exam_id"], self.exam_periods_df["period_id"]):
            if eid in self.active_exams_set:
                self.allowed_periods[eid].add(pid)

        # Ensure all active exams have at least one allowed period (fallback to all if missing)
        for e in self.active_exams:
            if not self.allowed_periods[e]:
                self.allowed_periods[e] = set(self.periods)

        # 4. Conflict graph for active exams (all raw pairs included as soft candidates)
        self.conflict_graph = get_conflict_graph(self.enrollments_df, total_exams=len(self.exams_df))
        self.active_conflicts: Dict[Tuple[int, int], int] = self.conflict_graph.get_schedulable_conflict_pairs(
            self.active_exams_set, exclude_exemptions=False
        )

        # 5. Dedicated single-room mutual exclusions (prevents Stage 2 room collision)
        if self.exam_rooms_df is not None:
            rc = self.exam_rooms_df.groupby("exam_id").size()
            single_room_exams = set(rc[rc == 1].index)
            er_single = self.exam_rooms_df[self.exam_rooms_df["exam_id"].isin(single_room_exams)]
            r2e = er_single.groupby("room_id")["exam_id"].apply(list).to_dict()
            for r, eids in r2e.items():
                rel = [e for e in eids if e in self.active_exams_set]
                for i in range(len(rel)):
                    for j in range(i + 1, len(rel)):
                        e1, e2 = min(rel[i], rel[j]), max(rel[i], rel[j])
                        if (e1, e2) not in self.active_conflicts:
                            self.active_conflicts[(e1, e2)] = 1

        # 6. Distribution constraints
        self.parsed_constraints = parse_distribution_constraints(self.constraints_df)

        # 7. Exam student counts
        if "number_of_students" in self.exams_df.columns:
            self.exam_students = dict(zip(self.exams_df["exam_id"], self.exams_df["number_of_students"]))
        else:
            self.exam_students = defaultdict(int)

    def build_model(self, alpha: float = 1.0, beta: float = 100.0) -> pulp.LpProblem:
        """
        Constructs the Binary Integer Programming model in PuLP strictly matching
        Option 2 (Soft Student Conflicts with Hard Administrative/Institutional Constraints):
        Supported formulations:
            - "student_load" (default): Compact Student-Period Load Formulation
                n[s, t] = integer load of student s in period t
                u[s, t, k] ∈ {0, 1} incremental binaries for k=2..D_s
                StudentConflictPenalty = ∑_s ∑_t ∑_{k=2}^{D_s} (k-1) u[s,t,k] == ∑_s ∑_t C(n[s,t], 2)
            - "pairwise_z": Explicit pair-period soft-conflict linearization
                z[e1, e2, t] ∈ [0, 1], z >= x1 + x2 - 1
        """
        t0 = time.time()
        self.prob = pulp.LpProblem("ExamOpt_Timetabling_BIP", pulp.LpMinimize)
        self.alpha = alpha
        self.beta = beta

        # --- Primary Assignment Variables (x) ---
        self.x = {}
        for e in self.active_exams:
            for t in self.allowed_periods[e]:
                self.x[e, t] = pulp.LpVariable(f"x_{e}_{t}", cat=pulp.LpBinary)

        self.z = {}
        self.c = {}
        self.n_load = {}
        self.u_load = {}
        conflict_terms = []

        if self.formulation == "pairwise_compact":
            # --- Formulation C: Compact Pairwise Soft-Conflict BIP (Phase 3.9) ---
            # Exactly one continuous variable c[e1, e2] in [0, 1] per unique conflict pair
            for (e1, e2), shared_students in self.active_conflicts.items():
                self.c[e1, e2] = pulp.LpVariable(f"c_{e1}_{e2}", lowBound=0.0, upBound=1.0, cat=pulp.LpContinuous)

            conflict_penalty_expr = pulp.lpSum(
                self.active_conflicts[(e1, e2)] * self.c[e1, e2]
                for (e1, e2) in self.c
            )

        elif self.formulation == "pairwise_z":
            # --- Formulation A: Pairwise-Period z variables ---
            for (e1, e2), shared_students in self.active_conflicts.items():
                common_periods = self.allowed_periods[e1].intersection(self.allowed_periods[e2])
                for t in common_periods:
                    self.z[e1, e2, t] = pulp.LpVariable(f"z_{e1}_{e2}_{t}", lowBound=0.0, upBound=1.0, cat=pulp.LpContinuous)

            conflict_penalty_expr = pulp.lpSum(
                self.active_conflicts[(e1, e2)] * self.z[e1, e2, t]
                for (e1, e2, t) in self.z
            )
        else:
            # --- Formulation B: Student-Period Load with Incremental Binaries (Phase 3.8) ---
            # Precompute student to active exams
            active_enr = self.enrollments_df[self.enrollments_df["exam_id"].isin(self.active_exams_set)]
            s2e = defaultdict(list)
            for s, e in zip(active_enr["student_id"], active_enr["exam_id"]):
                s2e[s].append(e)

            for s, exam_list in s2e.items():
                d_s = len(exam_list)
                if d_s < 2:
                    continue
                # Identify periods where student s has >= 2 permissible exams
                p_counts = defaultdict(int)
                for e in exam_list:
                    for p in self.allowed_periods[e]:
                        p_counts[p] += 1
                rel_periods = [p for p, cnt in p_counts.items() if cnt >= 2]

                for t in rel_periods:
                    # n[s, t] integer variable
                    n_var = pulp.LpVariable(f"n_{s}_{t}", lowBound=0, upBound=d_s, cat=pulp.LpInteger)
                    self.n_load[s, t] = n_var
                    # Linking: n[s, t] == sum_{e in exam_list} x[e, t]
                    self.prob += (
                        n_var == pulp.lpSum(self.x[e, t] for e in exam_list if (e, t) in self.x),
                        f"LoadLink_{s}_{t}",
                    )
                    # Incremental binaries u[s, t, k] for k in 2..d_s
                    for k in range(2, d_s + 1):
                        u_var = pulp.LpVariable(f"u_{s}_{t}_{k}", cat=pulp.LpBinary)
                        self.u_load[s, t, k] = u_var
                        # n[s, t] >= k * u[s, t, k]
                        self.prob += (
                            n_var >= k * u_var,
                            f"LoadLower_{s}_{t}_{k}",
                        )
                        # n[s, t] <= (k - 1) + (d_s - k + 1) * u[s, t, k]
                        self.prob += (
                            n_var <= (k - 1) + (d_s - k + 1) * u_var,
                            f"LoadUpper_{s}_{t}_{k}",
                        )
                        conflict_terms.append((k - 1) * u_var)

            conflict_penalty_expr = pulp.lpSum(conflict_terms)

        # --- Objective Function ---
        period_penalty_expr = pulp.lpSum(
            self.period_penalties.get(t, 0) * self.x[e, t]
            for (e, t) in self.x
        )
        self.prob += (
            self.alpha * period_penalty_expr + self.beta * conflict_penalty_expr,
            "Total_Combined_Objective",
        )

        # --- Constraint 1: Exact One Period Assignment per Exam (HARD) ---
        self.num_exact_one_constraints = 0
        for e in self.active_exams:
            self.prob += (
                pulp.lpSum(self.x[e, t] for t in self.allowed_periods[e]) == 1,
                f"OnePeriod_{e}",
            )
            self.num_exact_one_constraints += 1

        # --- Constraint 2: Pairwise Conflict Linking Constraints ---
        self.num_conflict_constraints = 0
        if self.formulation == "pairwise_compact":
            for (e1, e2), c_var in self.c.items():
                common_periods = self.allowed_periods[e1].intersection(self.allowed_periods[e2])
                for t in common_periods:
                    self.prob += (
                        c_var >= self.x[e1, t] + self.x[e2, t] - 1,
                        f"CompactConflictLink_{e1}_{e2}_{t}",
                    )
                    self.num_conflict_constraints += 1
        elif self.formulation == "pairwise_z":
            for (e1, e2, t), z_var in self.z.items():
                self.prob += (
                    z_var >= self.x[e1, t] + self.x[e2, t] - 1,
                    f"ConflictLink_{e1}_{e2}_{t}",
                )
                self.num_conflict_constraints += 1
        else:
            # For student_load, conflict constraints count = load links + lower + upper bounds
            self.num_conflict_constraints = len(self.n_load) + 2 * len(self.u_load)

        # --- Constraint 3: Fixed-Time Examinations (HARD) ---
        self.num_fixed_time_constraints = 0
        for e in self.active_exams:
            if len(self.allowed_periods[e]) == 1:
                fixed_t = list(self.allowed_periods[e])[0]
                self.prob += self.x[e, fixed_t] == 1, f"FixedTime_{e}_{fixed_t}"
                self.num_fixed_time_constraints += 1

        # --- Constraint 4: Distribution Constraints (HARD) ---
        self.num_distribution_constraints = 0
        for c in self.parsed_constraints:
            relevant_exams = [e for e in c.exam_ids if e in self.active_exams_set]
            if len(relevant_exams) < 2:
                continue

            if c.constraint_type == "same-period":
                base_exam = relevant_exams[0]
                for other_exam in relevant_exams[1:]:
                    all_t = self.allowed_periods[base_exam].union(self.allowed_periods[other_exam])
                    for t in all_t:
                        var_base = self.x.get((base_exam, t), 0)
                        var_other = self.x.get((other_exam, t), 0)
                        self.prob += (
                            var_base == var_other,
                            f"Dist_SamePeriod_{c.constraint_id}_{base_exam}_{other_exam}_{t}",
                        )
                        self.num_distribution_constraints += 1

            elif c.constraint_type == "different-period":
                for i in range(len(relevant_exams)):
                    for j in range(i + 1, len(relevant_exams)):
                        e1, e2 = relevant_exams[i], relevant_exams[j]
                        common_t = self.allowed_periods[e1].intersection(self.allowed_periods[e2])
                        for t in common_t:
                            self.prob += (
                                self.x[e1, t] + self.x[e2, t] <= 1,
                                f"Dist_DiffPeriod_{c.constraint_id}_{e1}_{e2}_{t}",
                            )
                            self.num_distribution_constraints += 1

            elif c.constraint_type == "precedence":
                e1, e2 = relevant_exams[0], relevant_exams[1]
                expr_e1 = pulp.lpSum(t * self.x[e1, t] for t in self.allowed_periods[e1])
                expr_e2 = pulp.lpSum(t * self.x[e2, t] for t in self.allowed_periods[e2])
                self.prob += (
                    expr_e1 <= expr_e2 - 1,
                    f"Dist_Precedence_{c.constraint_id}_{e1}_{e2}",
                )
                self.num_distribution_constraints += 1

        # --- Constraint 5: Period Exam Capacity for Room Feasibility (Integrated Refinement) ---
        if self.max_exams_per_period is not None and self.max_exams_per_period > 0:
            for t in self.periods:
                self.prob += (
                    pulp.lpSum(self.x[e, t] for e in self.active_exams if (e, t) in self.x) <= self.max_exams_per_period,
                    f"MaxExamsPerPeriod_{t}",
                )

        self.num_x_variables = len(self.x)
        self.num_z_variables = len(self.z)
        self.num_c_variables = len(self.c)
        self.num_n_variables = len(self.n_load)
        self.num_u_variables = len(self.u_load)
        self.num_variables = self.num_x_variables + self.num_z_variables + self.num_c_variables + self.num_n_variables + self.num_u_variables
        try:
            self.num_constraints = len(dict(self.prob.constraints))
        except Exception:
            self.num_constraints = len(list(self.prob.constraints))
        return self.prob

    def solve(self, time_limit_seconds: int = 30) -> Dict[str, Any]:
        """
        Solves the BIP problem using HiGHS Optimizer via PuLP direct interface.
        Accurately reports OPTIMAL, FEASIBLE, INFEASIBLE, or TIME_LIMIT_NO_INCUMBENT.
        HiGHS is open-source (MIT License) with ZERO model size limitations.
        """
        import traceback
        from src.solver_config import get_solver, get_solver_info, verify_solver_status

        if self.prob is None:
            self.build_model()

        # Step 0: Check solver health
        solver_status = verify_solver_status()
        solver_meta = get_solver_info()

        if not solver_status["is_valid"]:
            self.solver_status = "SOLVER_ERROR"
            return {
                "status": "SOLVER_ERROR",
                "error": solver_status["error_message"],
                "runtime": 0.0,
                "solver": f"{solver_meta['solver_name']} {solver_meta['version']}",
                "time_limit": time_limit_seconds,
                "num_exams": len(self.active_exams),
                "scheduled_exams": 0,
                "message": f"HiGHS initialization error: {solver_status['error_message']}",
            }

        try:
            solver = get_solver(time_limit=time_limit_seconds, mip_gap=0.01)
        except Exception as ex:
            self.solver_status = "SOLVER_ERROR"
            return {
                "status": "SOLVER_ERROR",
                "error": str(ex),
                "runtime": 0.0,
                "solver": f"{solver_meta['solver_name']} {solver_meta['version']}",
                "time_limit": time_limit_seconds,
                "num_exams": len(self.active_exams),
                "scheduled_exams": 0,
                "message": f"Failed to instantiate HiGHS solver: {ex}",
            }

        t_start = time.time()
        raw_status = None
        solve_exception = None

        # For large models (> 1,000 exams), PuLP's in-memory C-API duplication can trigger
        # Python/highspy heap fragmentation and bad allocation.
        # We stream via MPS file directly into highspy's C++ core and free Python memory before solving.
        if len(self.active_exams) > 500:
            import tempfile
            import os
            import gc
            import highspy

            mps_fd = tempfile.NamedTemporaryFile(suffix=".mps", delete=False)
            mps_path = mps_fd.name
            mps_fd.close()

            try:
                # 1. Export formulation to MPS format
                self.prob.writeMPS(mps_path)

                # 2. Free Python PuLP constraint structures to release RAM
                self.prob.constraints.clear()
                gc.collect()

                # 3. Read model directly into HiGHS C++ engine
                h = highspy.Highs()
                h.setOptionValue("time_limit", float(time_limit_seconds))
                h.setOptionValue("mip_rel_gap", 0.05)
                h.setOptionValue("threads", 4)
                h.setOptionValue("mip_heuristic_effort", 0.5)
                h.setOptionValue("output_flag", False)
                read_status = h.readModel(mps_path)

                # Remove temporary file
                try:
                    os.remove(mps_path)
                except Exception:
                    pass

                # 4. Execute optimization
                h.run()
                highs_status = h.getModelStatus()
                highs_info = h.getInfo()

                # 5. Extract solution values back into self.x
                sol = h.getSolution()
                lp = h.getLp()
                col_name_to_val = {}
                for i in range(lp.num_col_):
                    cname = h.getColName(i)[1]
                    col_name_to_val[cname] = sol.col_value[i]

                for (e, t), var in self.x.items():
                    val = col_name_to_val.get(var.name)
                    if val is not None:
                        var.varValue = val

                for (e1, e2), var in self.c.items():
                    val = col_name_to_val.get(var.name)
                    if val is not None:
                        var.varValue = val

                for (e1, e2, t), var in self.z.items():
                    val = col_name_to_val.get(var.name)
                    if val is not None:
                        var.varValue = val

                for (s, t, k), var in self.u_load.items():
                    val = col_name_to_val.get(var.name)
                    if val is not None:
                        var.varValue = val

                if highs_info.primal_solution_status == 2:
                    self.objective_value = float(highs_info.objective_function_value)

                if highs_status == highspy.HighsModelStatus.kOptimal:
                    raw_status = "Optimal"
                elif highs_info.primal_solution_status == 2:
                    raw_status = "Not Solved"  # Feasible integer solution exists, time limit reached
                else:
                    raw_status = "Not Solved"

            except Exception as ex:
                solve_exception = ex
                self.solver_error = str(ex)
                self.solver_traceback = traceback.format_exc()
                try:
                    if os.path.exists(mps_path):
                        os.remove(mps_path)
                except Exception:
                    pass
        else:
            try:
                raw_status = self.prob.solve(solver)
            except Exception as ex:
                solve_exception = ex
                self.solver_error = str(ex)
                self.solver_traceback = traceback.format_exc()

        self.runtime_seconds = round(time.time() - t_start, 2)

        # Check how many exams received an integer assignment
        assigned_exams_count = 0
        try:
            for e in self.active_exams:
                for t in self.allowed_periods[e]:
                    val = pulp.value(self.x[e, t])
                    if val is not None and val > 0.5:
                        assigned_exams_count += 1
                        break
        except Exception:
            assigned_exams_count = 0

        has_complete_integer_solution = (assigned_exams_count == len(self.active_exams))
        has_solution = False

        if solve_exception is not None:
            if has_complete_integer_solution:
                self.solver_status = "FEASIBLE — TIME LIMIT REACHED"
                has_solution = True
            elif assigned_exams_count > 0:
                self.solver_status = f"TIME LIMIT REACHED ({assigned_exams_count}/{len(self.active_exams)} exams assigned)"
                has_solution = True
            ex_str = str(solve_exception).lower()
            if "bad allocation" in ex_str or "memoryerror" in ex_str:
                self.solver_status = "OUT_OF_MEMORY"
                mem_err = (
                    f"Out of Memory (bad allocation) during solver execution: The full 2,198-exam formulation contains "
                    f"1.96 million constraints and 5.9 million non-zero matrix elements. Solving the full formulation in memory "
                    f"requires approximately 4.5+ GB of free RAM. Currently available system RAM is too low to hold both the matrix "
                    f"and simplex tableaux. To run on this computer, please choose a custom subset (e.g. 50-200 exams) or close background memory-heavy apps."
                )
                return {
                    "status": "OUT_OF_MEMORY",
                    "error": mem_err,
                    "traceback": self.solver_traceback,
                    "runtime": self.runtime_seconds,
                    "solver": f"{solver_meta['solver_name']} {solver_meta['version']}",
                    "time_limit": time_limit_seconds,
                    "num_exams": len(self.active_exams),
                    "scheduled_exams": 0,
                    "message": mem_err,
                }

            self.solver_status = "ERROR"
            return {
                "status": "ERROR",
                "error": str(solve_exception),
                "traceback": self.solver_traceback,
                "runtime": self.runtime_seconds,
                "solver": f"{solver_meta['solver_name']} {solver_meta['version']}",
                "time_limit": time_limit_seconds,
                "num_exams": len(self.active_exams),
                "scheduled_exams": 0,
                "message": f"HiGHS solver execution failure: {solve_exception}",
            }
        else:
            # Normalize PuLP / HiGHS status string
            if hasattr(raw_status, '__int__'):
                pulp_status_str = pulp.LpStatus.get(int(raw_status), "Unknown")
            else:
                pulp_status_str = str(raw_status)

            if pulp_status_str == "Optimal" and has_complete_integer_solution:
                self.solver_status = "OPTIMAL"
                has_solution = True
            elif has_complete_integer_solution:
                self.solver_status = "FEASIBLE — TIME LIMIT REACHED"
                has_solution = True
            elif pulp_status_str == "Infeasible":
                self.solver_status = "INFEASIBLE"
            elif pulp_status_str in ("Not Solved", "Undefined"):
                if has_complete_integer_solution:
                    self.solver_status = "FEASIBLE — TIME LIMIT REACHED"
                    has_solution = True
                else:
                    self.solver_status = f"TIME LIMIT REACHED ({assigned_exams_count}/{len(self.active_exams)} exams assigned)"
                    return {
                        "status": "TIME_LIMIT_NO_INCUMBENT",
                        "error": f"HiGHS reached time limit ({time_limit_seconds}s) before finding a feasible integer timetable.",
                        "runtime": self.runtime_seconds,
                        "solver": f"{solver_meta['solver_name']} {solver_meta['version']}",
                        "time_limit": time_limit_seconds,
                        "num_exams": len(self.active_exams),
                        "scheduled_exams": 0,
                        "message": f"HiGHS stopped on time limit ({time_limit_seconds}s) without finding an integer solution.",
                    }
            else:
                self.solver_status = pulp_status_str
                if has_complete_integer_solution:
                    has_solution = True
        period_penalty_val = 0.0
        conflict_penalty_val = 0.0
        if has_solution:
            try:
                obj_val = pulp.value(self.prob.objective)
                self.objective_value = float(obj_val) if obj_val is not None else 0.0
            except Exception:
                self.objective_value = 0.0

            self._extract_solution()

            # Calculate objective components
            try:
                for (e, t), var in self.x.items():
                    v = pulp.value(var)
                    if v is not None and v > 0.5:
                        period_penalty_val += self.period_penalties.get(t, 0)
                if self.formulation == "pairwise_compact":
                    for (e1, e2), c_var in self.c.items():
                        cv = pulp.value(c_var)
                        if cv is not None and cv > 1e-4:
                            conflict_penalty_val += self.active_conflicts[(e1, e2)] * cv
                elif self.formulation == "pairwise_z":
                    for (e1, e2, t), z_var in self.z.items():
                        zv = pulp.value(z_var)
                        if zv is not None and zv > 1e-4:
                            conflict_penalty_val += self.active_conflicts[(e1, e2)] * zv
                else:
                    for (s, t, k), u_var in self.u_load.items():
                        uv = pulp.value(u_var)
                        if uv is not None and uv > 0.5:
                            conflict_penalty_val += (k - 1)
            except Exception:
                pass

        return {
            "status": self.solver_status,
            "objective_value": self.objective_value,
            "period_penalty": round(period_penalty_val, 2),
            "conflict_penalty": round(conflict_penalty_val, 2),
            "runtime": self.runtime_seconds,
            "solver": f"{solver_meta['solver_name']} {solver_meta['version']}",
            "time_limit": time_limit_seconds,
            "formulation": self.formulation,
            "num_exams": len(self.active_exams),
            "num_periods": len(self.periods),
            "num_variables": self.num_variables,
            "num_x_variables": self.num_x_variables,
            "num_z_variables": self.num_z_variables,
            "num_c_variables": self.num_c_variables,
            "num_n_variables": self.num_n_variables,
            "num_u_variables": self.num_u_variables,
            "num_constraints": self.num_constraints,
            "num_exact_one_constraints": self.num_exact_one_constraints,
            "num_conflict_constraints": self.num_conflict_constraints,
            "num_fixed_time_constraints": self.num_fixed_time_constraints,
            "num_distribution_constraints": self.num_distribution_constraints,
            "scheduled_exams": len(self.timetable_df) if self.timetable_df is not None else 0,
        }

    def _extract_solution(self):
        """
        Extracts assigned period for each exam into a structured DataFrame.
        """
        records = []
        for e in self.active_exams:
            assigned_period = None
            for t in self.allowed_periods[e]:
                val = pulp.value(self.x[e, t])
                if val is not None and val > 0.5:
                    assigned_period = t
                    break

            if assigned_period is not None:
                p_info = self.period_info.get(assigned_period, {})
                pen = self.period_penalties.get(assigned_period, 0)
                is_fixed = len(self.allowed_periods[e]) == 1
                deg = self.conflict_graph.degree.get(e, 0)
                records.append({
                    "exam_id": e,
                    "period_id": assigned_period,
                    "day": p_info.get("day", ""),
                    "time": p_info.get("time", ""),
                    "period_penalty": pen,
                    "students": self.exam_students.get(e, 0),
                    "is_fixed_time": is_fixed,
                    "conflict_degree": deg,
                })

        self.timetable_df = pd.DataFrame(records)

    def save_timetable(self, output_dir: Path = None) -> Path:
        """Saves the generated timetable to data/outputs/timetable.csv."""
        if self.timetable_df is None:
            raise ValueError("No timetable exists to save.")
        if output_dir is None:
            output_dir = Path(__file__).resolve().parent.parent / "data" / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        csv_path = output_dir / "timetable.csv"
        self.timetable_df.to_csv(csv_path, index=False)
        return csv_path
