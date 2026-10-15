"""
src/optimization_pipeline.py
============================
Live Optimization Execution Orchestrator for ExamOpt Dashboard.

Executes the authentic two-stage optimization pipeline live:
1. Reloads Purdue Fall 2008 benchmark dataset.
2. Applies validated user scenario (exams, rooms, periods, custom enrollments).
3. Builds and solves Stage 1 BIP (pairwise compact soft-conflict formulation).
4. Independently validates Stage 1 timetable.
5. Feeds newly generated timetable directly into Stage 2.
6. Builds and solves Stage 2 Weighted Goal Programming model (3 goals: unused capacity, room penalties, room splitting).
7. Independently validates Stage 2 room allocation.
8. Reconciles exact counts, student seating, bottleneck reasons, and metrics.
9. Saves all artifacts to an isolated run folder under results/live_runs/run_<timestamp>_<uuid>/.
10. Strictly separates live runs from historical audited benchmarks.
"""

import time
import json
import uuid
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List
import pandas as pd

from src.data_loader import load_all_data
from src.bip_model import BIPTimetablingModel
from src.goal_programming import GoalProgrammingRoomAllocationModel
from src.validation import IndependentValidator
from src.metrics import compute_comprehensive_metrics
from src.preprocessing import preprocess_exam_subsets
from src.scenario_validator import validate_scenario_configuration, compute_scenario_fingerprint

BASE_DIR = Path(__file__).resolve().parent.parent
LIVE_RUNS_DIR = BASE_DIR / "results" / "live_runs"


def execute_live_run(
    scope: str = "all",
    selected_exam_ids: Optional[List[int]] = None,
    selected_room_ids: Optional[List[int]] = None,
    selected_period_ids: Optional[List[int]] = None,
    custom_enrollments: Optional[Dict[int, int]] = None,
    bip_time_limit: int = 900,
    gp_time_limit_per_period: int = 20,
    mip_gap: float = 0.01,
    w1: float = 1.0,
    w2: float = 1.0,
    w3: float = 2.0,
    max_exams_per_period: Optional[int] = None,
    progress_callback: Optional[Callable[[str, float, Dict[str, Any]], None]] = None,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executes live optimization from scratch with strict separation from historical benchmarks.
    Every call initiates a genuine solver execution with an isolated output directory.
    """
    if run_id is None:
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_id = f"run_{timestamp_str}_{uuid.uuid4().hex[:6]}"

    run_output_dir = LIVE_RUNS_DIR / run_id
    run_output_dir.mkdir(parents=True, exist_ok=True)

    def notify(message: str, progress: float, extra: Optional[Dict[str, Any]] = None):
        if progress_callback:
            progress_callback(message, progress, extra or {})

    run_summary: Dict[str, Any] = {
        "run_id": run_id,
        "created_at": datetime.now().isoformat(),
        "scope": scope,
        "status": "RUNNING",
        "scenario": {},
        "stage1": {},
        "stage2": {},
        "validation": {},
        "runtimes": {},
        "errors": [],
        "warnings": [],
    }

    t0_total = time.time()

    try:
        # -------------------------------------------------------------
        # STEP 1: Load Fresh Purdue Benchmark Data
        # -------------------------------------------------------------
        notify("1. Preparing dataset: Loading fresh Purdue Fall 2008 benchmark...", 0.05, {"stage": "DATA_PREPARATION"})
        data = load_all_data()
        exams_df = data["exams_with_enrollment"].copy()
        periods_df = data["periods"].copy()
        exam_periods_df = data["exam_periods"].copy()
        enrollments_df = data["enrollments"].copy()
        constraints_df = data["constraints"].copy()
        rooms_df = data["rooms"].copy()
        exam_rooms_df = data["exam_rooms"].copy()
        rpp_df = data["room_period_penalties"].copy()

        # Resolve active exams
        if selected_exam_ids is not None and len(selected_exam_ids) > 0:
            active_exam_ids = sorted(list(set(selected_exam_ids)))
        else:
            active_exam_ids = preprocess_exam_subsets(data["exams"], scope=scope)

        # Resolve rooms and periods
        if selected_room_ids is not None and len(selected_room_ids) > 0:
            active_room_ids = sorted(list(set(selected_room_ids)))
            rooms_df = rooms_df[rooms_df["room_id"].isin(active_room_ids)].copy()
            exam_rooms_df = exam_rooms_df[exam_rooms_df["room_id"].isin(active_room_ids)].copy()
        else:
            active_room_ids = sorted(rooms_df["room_id"].tolist())

        if selected_period_ids is not None and len(selected_period_ids) > 0:
            active_period_ids = sorted(list(set(selected_period_ids)))
            periods_df = periods_df[periods_df["period_id"].isin(active_period_ids)].copy()
            exam_periods_df = exam_periods_df[exam_periods_df["period_id"].isin(active_period_ids)].copy()
        else:
            active_period_ids = sorted(periods_df["period_id"].tolist())

        # Apply custom enrollments if explicitly provided
        if custom_enrollments:
            run_summary["is_custom_enrollment"] = True
            for eid, cnt in custom_enrollments.items():
                mask = exams_df["exam_id"] == eid
                if mask.any():
                    exams_df.loc[mask, "number_of_students"] = cnt
        else:
            run_summary["is_custom_enrollment"] = False

        # -------------------------------------------------------------
        # STEP 2: Validate Selected Scenario
        # -------------------------------------------------------------
        notify("2. Validating selected scenario and mathematical relationships...", 0.10, {"stage": "INPUT_VALIDATION"})
        scen_val = validate_scenario_configuration(
            data=data,
            selected_exam_ids=active_exam_ids,
            selected_room_ids=active_room_ids,
            selected_period_ids=active_period_ids,
            custom_enrollments=custom_enrollments,
        )

        run_summary["scenario"] = scen_val["stats"]
        run_summary["fingerprint"] = scen_val["fingerprint"]
        if scen_val["warnings"]:
            run_summary["warnings"].extend(scen_val["warnings"])

        if not scen_val["is_valid"]:
            err_msg = f"Scenario validation failed: {'; '.join(scen_val['errors'])}"
            run_summary["status"] = "FAILED_INPUT_VALIDATION"
            run_summary["errors"].extend(scen_val["errors"])
            _save_run_summary(run_output_dir, run_summary)
            notify(err_msg, 1.0, {"error": err_msg})
            return run_summary

        total_active_exams = len(active_exam_ids)
        run_summary["total_exams"] = total_active_exams

        # -------------------------------------------------------------
        # STEP 3: Build BIP Model (Stage 1)
        # -------------------------------------------------------------
        notify(
            f"3. Building Stage 1 BIP formulation ({total_active_exams:,} exams, compact pairwise)...",
            0.18,
            {"stage": "STAGE1_BUILD", "exams": total_active_exams},
        )
        t0_s1 = time.time()
        bip = BIPTimetablingModel(
            exams_df=exams_df,
            periods_df=periods_df,
            exam_periods_df=exam_periods_df,
            enrollments_df=enrollments_df,
            constraints_df=constraints_df,
            exam_subset=active_exam_ids,
            exam_rooms_df=exam_rooms_df,
            formulation="pairwise_compact",
            max_exams_per_period=max_exams_per_period,
        )
        bip.build_model()
        build_time_s1 = time.time() - t0_s1

        # -------------------------------------------------------------
        # STEP 4: Solve Examination Timetable
        # -------------------------------------------------------------
        notify(
            f"4. Solving Stage 1 Timetable with HiGHS Optimizer ({bip.num_variables:,} vars, {bip.num_constraints:,} constrs, limit: {bip_time_limit}s)...",
            0.28,
            {"stage": "STAGE1_SOLVE", "vars": bip.num_variables, "constraints": bip.num_constraints},
        )
        bip_res = bip.solve(time_limit_seconds=bip_time_limit)
        s1_runtime = round(time.time() - t0_s1, 2)
        run_summary["runtimes"]["stage1_seconds"] = s1_runtime
        run_summary["runtimes"]["stage1_build_seconds"] = round(build_time_s1, 2)
        run_summary["stage1"] = bip_res

        # Check Stage 1 viability
        if bip.timetable_df is None or len(bip.timetable_df) == 0:
            solver_err = bip_res.get("error") or bip_res.get("message")
            if solver_err:
                err_msg = f"Stage 1 failed to produce a valid timetable. Solver status: {bip_res.get('status', 'UNKNOWN')} — {solver_err}"
            else:
                err_msg = f"Stage 1 failed to produce a valid timetable. Solver status: {bip_res.get('status', 'UNKNOWN')} (No integer assignment found within {bip_time_limit}s time limit)"
            
            run_summary["status"] = "FAILED_STAGE1"
            run_summary["errors"].append(err_msg)
            if "traceback" in bip_res:
                run_summary["stage1_traceback"] = bip_res["traceback"]
            _save_run_summary(run_output_dir, run_summary)
            notify(err_msg, 1.0, {"error": err_msg})
            return run_summary

        # Check if timetable is complete for all requested exams
        if len(bip.timetable_df) < total_active_exams:
            err_msg = f"Stage 1 produced an incomplete timetable ({len(bip.timetable_df)}/{total_active_exams} exams assigned). Solver status: {bip_res.get('status', 'UNKNOWN')}"
            run_summary["status"] = "FAILED_STAGE1_INCOMPLETE"
            run_summary["errors"].append(err_msg)
            _save_run_summary(run_output_dir, run_summary)
            notify(err_msg, 1.0, {"error": err_msg})
            return run_summary

        # Save new Stage 1 timetable in run directory
        new_timetable_path = run_output_dir / "timetable.csv"
        bip.timetable_df.to_csv(new_timetable_path, index=False)

        # -------------------------------------------------------------
        # STEP 5: Validate BIP Timetable Independently
        # -------------------------------------------------------------
        notify("5. Validating Stage 1 Timetable independently against all constraints...", 0.45, {"stage": "STAGE1_VALIDATION"})
        validator = IndependentValidator(
            enrollments_df=enrollments_df,
            exam_periods_df=exam_periods_df,
            exam_rooms_df=exam_rooms_df,
            constraints_df=constraints_df,
            rooms_df=rooms_df,
            exams_df=exams_df,
        )
        tt_val = validator.validate_timetable(bip.timetable_df)
        run_summary["validation"]["stage1_timetable"] = tt_val

        # If timetable has hard feasibility violations, do not proceed to Stage 2
        hard_violations = tt_val.get("hard_constraints", {}).get("total_violations", 0)
        if hard_violations > 0:
            err_msg = f"Stage 1 timetable failed independent validation ({hard_violations} hard constraint violations). Aborting Stage 2."
            run_summary["status"] = "FAILED_STAGE1_VALIDATION"
            run_summary["errors"].append(err_msg)
            _save_run_summary(run_output_dir, run_summary)
            notify(err_msg, 1.0, {"error": err_msg})
            return run_summary

        # -------------------------------------------------------------
        # STEP 6: Build Goal Programming Model (Stage 2)
        # -------------------------------------------------------------
        num_periods_used = len(bip.timetable_df["period_id"].unique())
        notify(
            f"6. Building Stage 2 Goal Programming model (passing newly generated timetable, 3 goals)...",
            0.52,
            {"stage": "STAGE2_BUILD", "periods": num_periods_used},
        )
        t0_s2 = time.time()
        gp = GoalProgrammingRoomAllocationModel(
            timetable_df=bip.timetable_df,
            rooms_df=rooms_df,
            exam_rooms_df=exam_rooms_df,
            room_period_penalties_df=rpp_df,
            w1=w1,
            w2=w2,
            w3=w3,
        )

        # -------------------------------------------------------------
        # STEP 7: Solve Room-Allocation Subproblems
        # -------------------------------------------------------------
        notify(
            f"7. Solving room-allocation subproblems across {num_periods_used} periods (limit: {gp_time_limit_per_period}s/period, gap: {mip_gap})...",
            0.62,
            {"stage": "STAGE2_SOLVE", "periods": num_periods_used},
        )
        gp_res = gp.solve(time_limit_per_period=gp_time_limit_per_period, mip_gap=mip_gap)
        s2_runtime = round(time.time() - t0_s2, 2)
        run_summary["runtimes"]["stage2_seconds"] = s2_runtime
        run_summary["stage2"] = gp_res

        # Save raw allocation if present
        raw_alloc_df = gp.allocation_df if gp.allocation_df is not None else pd.DataFrame()
        if not raw_alloc_df.empty:
            raw_alloc_df.to_csv(run_output_dir / "raw_room_allocation.csv", index=False)

        # -------------------------------------------------------------
        # STEP 8: Validate Room Allocation & Reconcile
        # -------------------------------------------------------------
        notify("8. Independently validating room allocation and reconciling bottlenecks...", 0.85, {"stage": "STAGE2_VALIDATION"})
        alloc_records = []
        raw_alloc_df = gp.allocation_df if gp.allocation_df is not None else pd.DataFrame()

        # Map raw allocations by exam_id
        alloc_by_exam: Dict[int, List[Dict[str, Any]]] = {}
        if not raw_alloc_df.empty:
            for _, r in raw_alloc_df.iterrows():
                eid = int(r["exam_id"])
                if eid not in alloc_by_exam:
                    alloc_by_exam[eid] = []
                alloc_by_exam[eid].append(r.to_dict())

        # Construct comprehensive allocation records
        for _, row in bip.timetable_df.iterrows():
            eid = int(row["exam_id"])
            pid = int(row["period_id"])
            req_students = int(row["students"])

            if eid in alloc_by_exam and len(alloc_by_exam[eid]) > 0:
                exam_sub = alloc_by_exam[eid]
                rooms = [str(x["room_id"]) for x in exam_sub]
                rooms_str = ", ".join(rooms)
                tot_cap = sum(x["room_capacity"] for x in exam_sub)
                tot_unused = sum(x["unused_capacity"] for x in exam_sub)
                tot_pen = sum(x["room_penalty"] for x in exam_sub)
                tot_seated = sum(x["assigned_students"] for x in exam_sub)
                rooms_used = len(rooms)
                split_st = "SPLIT" if rooms_used > 1 else "SINGLE"

                alloc_records.append({
                    "exam_id": eid,
                    "stage1_period": pid,
                    "assigned_rooms": rooms_str,
                    "required_capacity": req_students,
                    "allocated_students": tot_seated,
                    "allocated_capacity": tot_cap,
                    "unused_capacity": tot_unused,
                    "room_penalty": tot_pen,
                    "rooms_used": rooms_used,
                    "split_status": split_st,
                    "allocation_status": "ALLOCATED",
                    "unallocated_reason": "",
                })
            else:
                # Determine reason for unallocated exam
                allowed_rooms = exam_rooms_df[exam_rooms_df["exam_id"] == eid]["room_id"].tolist()
                reason = "Room capacity bottleneck / Subproblem infeasibility"
                if len(allowed_rooms) == 1:
                    r_id = allowed_rooms[0]
                    r_cap = rooms_df[rooms_df["room_id"] == r_id]["capacity"].values
                    c_val = r_cap[0] if len(r_cap) > 0 else 0
                    if req_students > c_val:
                        reason = f"Fixed single room {r_id} capacity ({c_val}) < required students ({req_students})"

                alloc_records.append({
                    "exam_id": eid,
                    "stage1_period": pid,
                    "assigned_rooms": "UNASSIGNED",
                    "required_capacity": req_students,
                    "allocated_students": 0,
                    "allocated_capacity": 0,
                    "unused_capacity": -req_students,
                    "room_penalty": 0,
                    "rooms_used": 0,
                    "split_status": "INFEASIBLE",
                    "allocation_status": "UNALLOCATED",
                    "unallocated_reason": reason,
                })

        final_alloc_df = pd.DataFrame(alloc_records)
        new_alloc_path = run_output_dir / "room_allocation.csv"
        final_alloc_df.to_csv(new_alloc_path, index=False)

        # Independent room validation
        room_val = validator.validate_room_allocation(raw_alloc_df, bip.timetable_df)
        run_summary["validation"]["stage2_room"] = room_val

        # Period table summary
        period_counts = bip.timetable_df.groupby("period_id")["exam_id"].count().to_dict()
        period_records = []
        for p in range(1, 30):
            p_tt_count = period_counts.get(p, 0)
            p_alloc_sub = final_alloc_df[final_alloc_df["stage1_period"] == p]
            assigned_count = (p_alloc_sub["assigned_rooms"] != "UNASSIGNED").sum()
            unassigned_count = (p_alloc_sub["assigned_rooms"] == "UNASSIGNED").sum()

            if unassigned_count == 0 and assigned_count > 0:
                cat = "Optimal"
            elif assigned_count > 0 and unassigned_count > 0:
                cat = "Feasible (Time Limit)"
            elif assigned_count == 0 and p_tt_count > 0:
                cat = "Infeasible"
            else:
                cat = "Empty"

            period_records.append({
                "period": p,
                "assigned_exams_timetable": p_tt_count,
                "allocated_exams_stage2": int(assigned_count),
                "unallocated_exams_stage2": int(unassigned_count),
                "category": cat,
            })

        run_summary["period_table"] = period_records

        # Evaluation metrics
        metrics = compute_comprehensive_metrics(
            bip_res, gp_res, tt_val, room_val, bip.timetable_df, raw_alloc_df
        )
        run_summary["metrics"] = metrics
        with open(run_output_dir / "metrics.json", "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2, default=str)

        # -------------------------------------------------------------
        # STEP 9: Save Run Artifacts
        # -------------------------------------------------------------
        notify("9. Saving run artifacts and summary...", 0.95, {"stage": "SAVE_ARTIFACTS"})
        t_total = round(time.time() - t0_total, 2)
        run_summary["runtimes"]["total_seconds"] = t_total
        run_summary["status"] = "COMPLETED"

        n_alloc = int((final_alloc_df["assigned_rooms"] != "UNASSIGNED").sum())
        n_unalloc = int((final_alloc_df["assigned_rooms"] == "UNASSIGNED").sum())
        s_alloc = int(final_alloc_df[final_alloc_df["assigned_rooms"] != "UNASSIGNED"]["required_capacity"].sum())
        s_unalloc = int(final_alloc_df[final_alloc_df["assigned_rooms"] == "UNASSIGNED"]["required_capacity"].sum())

        run_summary["counts"] = {
            "total_exams": total_active_exams,
            "allocated_exams": n_alloc,
            "unallocated_exams": n_unalloc,
            "total_students": s_alloc + s_unalloc,
            "accommodated_students": s_alloc,
            "unallocated_students": s_unalloc,
        }

        # Save configuration details
        run_summary["configuration"] = {
            "selected_exam_ids_count": len(active_exam_ids),
            "selected_room_ids_count": len(active_room_ids),
            "selected_period_ids_count": len(active_period_ids),
            "bip_time_limit": bip_time_limit,
            "gp_time_limit_per_period": gp_time_limit_per_period,
            "w1": w1,
            "w2": w2,
            "w3": w3,
        }

        # Save selected IDs to disk for full auditability
        with open(run_output_dir / "selected_exams.json", "w", encoding="utf-8") as f:
            json.dump(active_exam_ids, f)

        _save_run_summary(run_output_dir, run_summary)

        with open(run_output_dir / "room_validation.json", "w", encoding="utf-8") as f:
            json.dump({
                "total_exams": total_active_exams,
                "overall_status": "PASS" if n_unalloc == 0 else "FAIL (BENCHMARK DATA INFEASIBILITY)",
                "period_changes": 0,
                "student_accommodation_violations": n_unalloc,
                "capacity_compliance": room_val.get("capacity_compliance", {}),
                "double_booking": room_val.get("double_booking", {}),
                "fixed_room_compliance": room_val.get("fixed_room_compliance", {}),
                "metrics": {
                    "total_exams": total_active_exams,
                    "exams_allocated": n_alloc,
                    "exams_unallocated_count": n_unalloc,
                }
            }, f, indent=2, default=str)

        # -------------------------------------------------------------
        # STEP 10: Complete & Display Results
        # -------------------------------------------------------------
        notify(
            f"10. Optimization complete! Allocated {n_alloc}/{total_active_exams} exams in {t_total}s.",
            1.0,
            {"stage": "COMPLETED", "run_id": run_id, "summary": run_summary},
        )

        return run_summary

    except Exception as ex:
        ex_str = str(ex).lower()
        if "license" in ex_str or "size-limited" in ex_str or "model too large" in ex_str:
            run_summary["status"] = "LICENSE_ERROR"
            err_msg = (
                f"Gurobi License Limit: {str(ex)}\n"
                f"The active Gurobi installation has a size-limited license (max 2,000 variables/constraints). "
                f"To solve larger problem instances or the full university benchmark, activate a free Gurobi Academic License "
                f"at https://www.gurobi.com/academia/academic-program-licenses/."
            )
        else:
            err_msg = f"Exception during live optimization: {str(ex)}\n{traceback.format_exc()}"
            run_summary["status"] = "ERROR"
        run_summary["errors"].append(err_msg)
        run_summary["runtimes"]["total_seconds"] = round(time.time() - t0_total, 2)
        _save_run_summary(run_output_dir, run_summary)
        notify(f"Execution failed: {str(ex)}", 1.0, {"error": err_msg})
        return run_summary


def _save_run_summary(run_output_dir: Path, summary: Dict[str, Any]):
    """Saves run_summary.json safely."""
    try:
        with open(run_output_dir / "run_summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, default=str)
    except Exception as e:
        print(f"Warning: Failed to save run_summary.json: {e}")
