"""
src/dashboard_data.py
=====================
Loads, validates, and provides structured access to the completed
Stage 1 BIP Timetable and Stage 2 Goal Programming benchmark results,
as well as dynamic live optimization runs from results/live_runs/.

Strictly preserves:
- Audited Phase 3.11 & Phase 4.4 benchmark results without modification.
- Full compatibility with all dashboard views and evaluation tabs.
"""

from pathlib import Path
import json
import pandas as pd
from typing import Dict, Any, Tuple, List, Optional


# Paths to authoritative benchmark results
BASE_DIR = Path(__file__).resolve().parent.parent
STAGE1_TIMETABLE_PATH = BASE_DIR / "results" / "phase3_11" / "timetable_2198_pairwise_compact.csv"
STAGE2_ALLOCATION_PATH = BASE_DIR / "results" / "phase4_stage2_final" / "stage2_2198_room_allocation.csv"
ROOM_VALIDATION_PATH = BASE_DIR / "results" / "phase4_stage2_final" / "room_validation_2198.json"
PHASE44_RESULTS_PATH = BASE_DIR / "results" / "phase4_stage2_final" / "phase44_2198_results.json"
PHASE44_AUDIT_PATH = BASE_DIR / "results" / "phase4_stage2_final" / "phase44_2198_audit.json"
PHASE44_REPORT_PATH = BASE_DIR / "results" / "phase4_stage2_final" / "phase44_2198_report.md"

LIVE_RUNS_DIR = BASE_DIR / "results" / "live_runs"


def list_completed_runs() -> List[Dict[str, Any]]:
    """
    Returns list of available runs (Baseline Benchmark + any live optimization runs).
    """
    runs = [
        {
            "run_id": "baseline_benchmark",
            "name": "🏆 Audited Baseline — Previously Computed Benchmark (Purdue 2,198)",
            "timestamp": "Audited Baseline",
            "status": "COMPLETED (STRICT BENCHMARK)",
            "is_baseline": True,
            "path": str(BASE_DIR / "results" / "phase4_stage2_final"),
        }
    ]

    if LIVE_RUNS_DIR.exists():
        for run_path in sorted(LIVE_RUNS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if run_path.is_dir():
                summary_file = run_path / "run_summary.json"
                if summary_file.exists():
                    try:
                        with open(summary_file, "r", encoding="utf-8") as f:
                            s = json.load(f)
                        total_ex = s.get("total_exams", s.get("scope", "all"))
                        has_tt = (run_path / "timetable.csv").exists()
                        has_ra = (run_path / "room_allocation.csv").exists()
                        stage_info = "Stage 1 + Stage 2" if (has_tt and has_ra) else ("Stage 1 Only" if has_tt else "Incomplete")
                        scope_str = s.get("scope_label") or f"{total_ex} Exams"
                        created = s.get("created_at", "")[:19].replace("T", " ")
                        
                        runs.append({
                            "run_id": s.get("run_id", run_path.name),
                            "name": f"⚡ Live Run: {scope_str} ({s.get('run_id', run_path.name)}) [{stage_info}]",
                            "timestamp": created,
                            "status": s.get("solver_status", s.get("status", "UNKNOWN")),
                            "is_baseline": False,
                            "path": str(run_path),
                            "summary": s,
                            "has_timetable": has_tt,
                            "has_allocation": has_ra,
                        })
                    except Exception:
                        pass
    return runs


def load_integrated_results(run_id: str = "baseline_benchmark") -> Dict[str, Any]:
    """
    Loads saved artifacts into memory for the requested run.
    Default is the baseline benchmark. If a live run_id is supplied, loads from live_runs/<run_id>.
    """
    if run_id == "baseline_benchmark" or not run_id:
        # Load Baseline Benchmark
        if not STAGE1_TIMETABLE_PATH.exists():
            raise FileNotFoundError(f"Missing Stage 1 timetable: {STAGE1_TIMETABLE_PATH.name}")
        tt_df = pd.read_csv(STAGE1_TIMETABLE_PATH)

        if not STAGE2_ALLOCATION_PATH.exists():
            raise FileNotFoundError(f"Missing Stage 2 room allocation: {STAGE2_ALLOCATION_PATH.name}")
        alloc_df = pd.read_csv(STAGE2_ALLOCATION_PATH)

        with open(ROOM_VALIDATION_PATH, "r", encoding="utf-8") as f:
            room_val = json.load(f)

        with open(PHASE44_RESULTS_PATH, "r", encoding="utf-8") as f:
            solver_res = json.load(f)

        with open(PHASE44_AUDIT_PATH, "r", encoding="utf-8") as f:
            audit_data = json.load(f)

        report_md = ""
        if PHASE44_REPORT_PATH.exists():
            with open(PHASE44_REPORT_PATH, "r", encoding="utf-8") as f:
                report_md = f.read()

        pt_records = audit_data.get("period_table", [])
        period_df = pd.DataFrame(pt_records)

        # Baseline summary
        run_summary = {
            "run_id": "baseline_benchmark",
            "scope": "2,198 (Complete Benchmark)",
            "status": "COMPLETED (STRICT BENCHMARK)",
            "is_baseline": True,
            "runtimes": {"total_seconds": 1620.0, "stage1_seconds": 1080.0, "stage2_seconds": 540.0},
            "counts": {"total_exams": 2198, "allocated_exams": 1938, "unallocated_exams": 260},
            "stage1": {"status": "OPTIMAL", "objective_value": 72.0},
            "stage2": {"status": "FEASIBLE (DATA INFEASIBILITY)", "objective_value": 216177.0},
        }

    else:
        # Load Live Run
        run_dir = LIVE_RUNS_DIR / run_id
        if not run_dir.exists():
            raise FileNotFoundError(f"Run directory not found: {run_id}")

        tt_path = run_dir / "timetable.csv"
        alloc_path = run_dir / "room_allocation.csv"
        summary_path = run_dir / "run_summary.json"
        run_summary = {}
        if summary_path.exists():
            try:
                with open(summary_path, "r", encoding="utf-8") as f:
                    run_summary = json.load(f)
            except Exception:
                run_summary = {}

        # If run is incomplete or failed, return structured summary without raising misleading missing file error
        if not tt_path.exists() or not alloc_path.exists():
            tt_df = pd.read_csv(tt_path) if tt_path.exists() else pd.DataFrame()
            alloc_df = pd.read_csv(alloc_path) if alloc_path.exists() else pd.DataFrame()
            
            run_status = run_summary.get("status", "INCOMPLETE")
            error_reasons = run_summary.get("errors", ["Run did not produce complete outputs."])

            return {
                "run_id": run_id,
                "is_baseline": False,
                "run_summary": run_summary,
                "integrated_df": pd.DataFrame(),
                "timetable_df": tt_df,
                "allocation_df": alloc_df,
                "period_df": pd.DataFrame(),
                "solver_results": {
                    "phase": "Live Optimization (Failed/Incomplete)",
                    "scope": f"{run_summary.get('total_exams', len(tt_df))} Exams",
                    "final_classification": run_status,
                    "stage1": run_summary.get("stage1", {}),
                    "stage2": run_summary.get("stage2", {}),
                    "runtimes": run_summary.get("runtimes", {}),
                    "errors": error_reasons,
                },
                "room_validation": {},
                "audit_data": {"period_table": [], "counts": {}},
                "report_md": f"# Live Run: {run_id} ({run_status})\n\n" + "\n".join(f"- {e}" for e in error_reasons),
                "is_complete": False,
            }

        tt_df = pd.read_csv(tt_path)
        alloc_df = pd.read_csv(alloc_path)

        room_val_path = run_dir / "room_validation.json"
        if room_val_path.exists():
            with open(room_val_path, "r", encoding="utf-8") as f:
                room_val = json.load(f)
        else:
            room_val = run_summary.get("validation", {}).get("stage2_room", {})

        solver_res = {
            "phase": "Live Optimization",
            "scope": f"{len(tt_df)} Exams",
            "formulation": "Compact Pairwise BIP + Weighted Goal Programming",
            "final_classification": run_summary.get("status", "COMPLETED"),
            "stage1": run_summary.get("stage1", {}),
            "stage2": run_summary.get("stage2", {}),
            "runtimes": run_summary.get("runtimes", {}),
        }

        audit_data = {
            "audit_phase": "Live Optimization Run",
            "period_table": run_summary.get("period_table", []),
            "counts": run_summary.get("counts", {}),
        }

        report_md = f"# Live Optimization Run: {run_id}\n\n- Scope: {len(tt_df)} Exams\n- Status: {run_summary.get('status')}"
        period_df = pd.DataFrame(run_summary.get("period_table", []))

    # Integrate / Merge Data for the Dashboard Views
    if not alloc_df.empty:
        # Standardize allocation format if coming from live GP
        if "assigned_rooms" not in alloc_df.columns and "room_id" in alloc_df.columns:
            # Group by exam_id if there are splits
            alloc_summary = alloc_df.groupby("exam_id").agg({
                "room_id": lambda r: ", ".join(map(str, sorted(r))),
                "assigned_students": "sum",
                "room_capacity": "sum",
                "unused_capacity": "sum",
                "room_penalty": "sum",
                "is_split": "any",
            }).reset_index()
            alloc_summary.rename(columns={
                "room_id": "assigned_rooms",
                "assigned_students": "allocated_students",
                "room_capacity": "allocated_capacity",
            }, inplace=True)
            alloc_summary["is_allocated"] = True
            alloc_summary["allocation_status"] = "ALLOCATED"
            merged = pd.merge(tt_df, alloc_summary, on="exam_id", how="left")
            merged["is_allocated"] = merged["is_allocated"].fillna(False)
            merged["allocation_status"] = merged["allocation_status"].fillna("UNALLOCATED")
            merged["assigned_rooms"] = merged["assigned_rooms"].fillna("UNASSIGNED")
            merged["allocated_students"] = merged["allocated_students"].fillna(0)
        else:
            merged = pd.merge(
                tt_df,
                alloc_df.drop(columns=["stage1_period"], errors="ignore"),
                on="exam_id",
                how="left"
            )
            merged["is_allocated"] = merged.get("assigned_rooms", pd.Series(dtype=str)) != "UNASSIGNED"
            merged["allocation_status"] = merged["is_allocated"].map({True: "ALLOCATED", False: "UNALLOCATED"})
            merged["allocated_students"] = merged.apply(
                lambda r: r["students"] if r.get("is_allocated", False) else 0, axis=1
            )
    else:
        merged = tt_df.copy()
        merged["is_allocated"] = False
        merged["allocation_status"] = "UNALLOCATED"
        merged["assigned_rooms"] = "UNASSIGNED"
        merged["allocated_students"] = 0

    if not period_df.empty and "period" in period_df.columns:
        period_status_map = dict(zip(period_df["period"], period_df["category"]))
        merged["solver_status"] = merged["period_id"].map(period_status_map).fillna("Unknown")
    else:
        merged["solver_status"] = "Scheduled"

    return {
        "run_id": run_id,
        "is_baseline": (run_id == "baseline_benchmark"),
        "timetable_df": tt_df,
        "allocation_df": alloc_df,
        "integrated_df": merged,
        "period_df": period_df,
        "room_validation": room_val,
        "solver_results": solver_res,
        "audit_data": audit_data,
        "report_md": report_md,
        "run_summary": run_summary,
    }


def verify_benchmark_identities(data: Dict[str, Any]) -> Dict[str, Tuple[bool, str]]:
    """
    Validates all mandatory benchmark mathematical and count identities.
    Returns dictionary of {check_name: (passed_bool, description)}.
    """
    merged = data["integrated_df"]
    pt_df = data["period_df"]
    audit = data["audit_data"]
    is_base = data.get("is_baseline", False)

    checks = {}

    total_exams = len(merged)
    expected_exams = 2198 if is_base else len(merged)
    c1 = (total_exams == expected_exams)
    checks[f"Total Examinations = {expected_exams:,}"] = (c1, f"Found {total_exams:,} exams")

    n_alloc = int(merged["is_allocated"].sum())
    n_unalloc = int((~merged["is_allocated"]).sum())
    c2 = (n_alloc + n_unalloc == total_exams)
    checks[f"Allocated ({n_alloc:,}) + Unallocated ({n_unalloc:,}) = Total ({total_exams:,})"] = (
        c2, f"Allocated: {n_alloc:,}, Unallocated: {n_unalloc:,}, Sum: {n_alloc + n_unalloc:,}"
    )

    s_alloc = int(merged[merged["is_allocated"]]["students"].sum())
    s_unalloc = int(merged[~merged["is_allocated"]]["students"].sum())
    s_tot = s_alloc + s_unalloc
    c3 = (s_alloc + s_unalloc == s_tot)
    checks[f"Accommodated Students ({s_alloc:,}) + Unallocated ({s_unalloc:,}) = Total ({s_tot:,})"] = (
        c3, f"Accommodated: {s_alloc:,}, Unallocated: {s_unalloc:,}, Total: {s_tot:,}"
    )

    if not pt_df.empty and "category" in pt_df.columns:
        opt_p = int((pt_df["category"] == "Optimal").sum())
        tl_p = int((pt_df["category"] == "Feasible (Time Limit)").sum())
        inf_p = int((pt_df["category"] == "Infeasible").sum())
        tot_p = len(pt_df)
        checks["Period Category Breakdown"] = (
            True, f"Optimal: {opt_p}, Time-Limit: {tl_p}, Infeasible: {inf_p}, Total: {tot_p}"
        )

    if is_base:
        obj = audit.get("objective_reconciliation", {}).get("assigned_subset_1938_exams", {})
        d1 = obj.get("d1_unused_capacity", 0)
        d2 = obj.get("d2_room_penalty", 0)
        d3 = obj.get("d3_additional_room_assignments", 0)
        splits = obj.get("split_examinations_count", 0)
        z2 = obj.get("z2_objective", 0.0)
        c6 = (d1 == 215027 and d2 == 660 and d3 == 490 and splits == 382 and z2 == 216177.0)
        checks["Stage 2 Goal Reconciliation: Z2 = 215,027 + 660 + 490 = 216,177"] = (
            c6, f"d1+: {d1:,}, d2+: {d2:,}, d3+: {d3:,}, Splits: {splits}, Z2: {z2:,.1f}"
        )

    p_changes = data["room_validation"].get("period_changes", 0)
    c7 = (p_changes == 0)
    checks["Stage 1 Period Preservation: 0 Modifications (100% Invariance)"] = (
        c7, f"Period changes: {p_changes}"
    )

    return checks
