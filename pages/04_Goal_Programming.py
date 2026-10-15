"""
04_Goal_Programming.py
=======================
Stage 2: Examination Room Allocation using Weighted Goal Programming (GP).
Assigns scheduled examinations to suitable rooms balancing multiple operational goals.
"""

import streamlit as st
import pandas as pd
import io
import time
import json
from pathlib import Path

import importlib
import src.goal_programming
import src.validation
importlib.reload(src.goal_programming)
importlib.reload(src.validation)

from src.data_loader import load_all_data
from src.goal_programming import GoalProgrammingRoomAllocationModel
from src.validation import IndependentValidator
from src.visualization import plot_room_utilization_gauge, plot_goal_tradeoff_scenarios

from src.dashboard_data import list_completed_runs

st.set_page_config(page_title="Goal Programming — ExamOpt", page_icon="🏫", layout="wide")

if "data" not in st.session_state:
    st.session_state.data = load_all_data()

data = st.session_state.data

# Safe session-state variable initialization
if "gp_model" not in st.session_state:
    st.session_state.gp_model = None
if "gp_summary" not in st.session_state:
    st.session_state.gp_summary = None
if "allocation_df" not in st.session_state:
    st.session_state.allocation_df = None
if "gp_scenarios" not in st.session_state:
    st.session_state.gp_scenarios = []

# Discover available runs with timetables
available_runs = list_completed_runs()
runs_with_tt = [r for r in available_runs if r.get("has_timetable") or r.get("is_baseline")]
run_map = {r["run_id"]: r["name"] for r in runs_with_tt}

# Run selection box
selected_run_id = st.selectbox(
    "Select Stage 1 Timetable Source for Room Allocation:",
    options=list(run_map.keys()),
    index=0 if "target_run_id" not in st.session_state or st.session_state.target_run_id not in run_map else list(run_map.keys()).index(st.session_state.target_run_id),
    format_func=lambda rid: run_map[rid],
    help="Select which Stage 1 Timetable to allocate rooms for. This guarantees Stage 2 receives the exact timetable from the selected run."
)
st.session_state.target_run_id = selected_run_id

# Load the exact timetable for the selected run
selected_run_obj = next((r for r in runs_with_tt if r["run_id"] == selected_run_id), None)
if selected_run_obj and not selected_run_obj.get("is_baseline"):
    tt_file = Path(selected_run_obj["path"]) / "timetable.csv"
    if tt_file.exists():
        st.session_state.timetable_df = pd.read_csv(tt_file)
else:
    tt_benchmark = Path(__file__).resolve().parent.parent / "results" / "phase3_11" / "timetable_2198_pairwise_compact.csv"
    if tt_benchmark.exists():
        st.session_state.timetable_df = pd.read_csv(tt_benchmark)

st.markdown("## 🏫 Stage 2 — Room Allocation (Weighted Goal Programming)")
st.markdown("""
**Core Question:** *"Which room or rooms should be assigned to each scheduled examination?"*  
The Goal Programming model takes the timetable $t^*_e$ produced by Stage 1 as **fixed input** and allocates campus rooms 
while satisfying physical capacities and balancing three competing objectives.
""")

# State guard
if st.session_state.timetable_df is None or st.session_state.timetable_df.empty:
    st.warning("⚠️ **Stage 1 Timetable Not Found.** Please ensure a valid timetable exists or run Stage 1 to generate one.")
    st.stop()


# Stage 1 Status Banner
st.success(f"✅ Stage 1 Timetable active: **{len(st.session_state.timetable_df)} examinations** scheduled across periods.")

# Weight Sliders for Goal Programming
st.markdown("### ⚖️ Multi-Objective Goal Weights Configuration")
col_w1, col_w2, col_w3 = st.columns(3)

with col_w1:
    w1 = st.slider("w₁: Minimize Unused Capacity (Seat Efficiency)", min_value=0.0, max_value=5.0, value=1.0, step=0.1)
with col_w2:
    w2 = st.slider("w₂: Minimize Room Period Penalties", min_value=0.0, max_value=5.0, value=1.0, step=0.1)
with col_w3:
    w3 = st.slider("w₃: Minimize Room Splitting (Exam Dispersal)", min_value=0.0, max_value=5.0, value=2.0, step=0.1)

with st.expander("⚙️ Advanced HiGHS Solver Settings", expanded=False):
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        gp_time_limit = st.slider("Time Limit per Period Subproblem (seconds)", min_value=5, max_value=120, value=20, step=5)
    with col_t2:
        gp_mip_gap = st.slider("MIP Relative Optimality Gap", min_value=0.0, max_value=0.10, value=0.01, step=0.005, format="%.3f")

st.markdown("---")
run_gp_btn = st.button("🚀 Run Goal Programming Room Allocation (HiGHS)", type="primary", use_container_width=True)

if run_gp_btn:
    with st.spinner(f"Solving Stage 2 Room Allocation with HiGHS for {len(st.session_state.timetable_df)} examinations..."):
        t0_gp = time.time()
        gp = GoalProgrammingRoomAllocationModel(
            timetable_df=st.session_state.timetable_df,
            rooms_df=data["rooms"],
            exam_rooms_df=data["exam_rooms"],
            room_period_penalties_df=data["room_period_penalties"],
            w1=w1,
            w2=w2,
            w3=w3,
        )
        gp_res = gp.solve(time_limit_per_period=gp_time_limit, mip_gap=gp_mip_gap)
        st.session_state.gp_model = gp
        st.session_state.gp_summary = gp_res
        st.session_state.allocation_df = gp.allocation_df
        
        # Scenario recording for Pareto trade-off analysis
        st.session_state.gp_scenarios.append({
            "Scenario": f"w1={w1:.1f}, w2={w2:.1f}, w3={w3:.1f}",
            "Objective Z2": gp_res.get("objective_value", 0.0),
            "Unused Capacity (d1+)": gp_res.get("unused_capacity", 0),
            "Room Penalty (d2+)": gp_res.get("room_penalty", 0),
            "Room Splits (d3+)": gp_res.get("room_splits", 0),
            "Utilization (%)": gp_res.get("utilization_pct", 0.0),
        })

        # Save to active run if available
        if "target_run_id" in st.session_state and st.session_state.target_run_id != "baseline_benchmark":
            active_run_dir = Path(__file__).resolve().parent.parent / "results" / "live_runs" / st.session_state.target_run_id
            if active_run_dir.exists() and gp.allocation_df is not None:
                gp.allocation_df.to_csv(active_run_dir / "room_allocation.csv", index=False)
                # Also update run_summary.json with stage 2 details
                sum_path = active_run_dir / "run_summary.json"
                if sum_path.exists():
                    try:
                        with open(sum_path, "r", encoding="utf-8") as sf:
                            s_data = json.load(sf)
                        s_data["stage2"] = {
                            "status": gp_res.get("status", "UNKNOWN"),
                            "objective_value": gp_res.get("objective_value", 0.0),
                            "runtime": gp_res.get("runtime", 0.0),
                            "unused_capacity": gp_res.get("unused_capacity", 0),
                            "room_penalty": gp_res.get("room_penalty", 0),
                            "room_splits": gp_res.get("room_splits", 0),
                            "utilization_pct": gp_res.get("utilization_pct", 0.0),
                            "weights": {"w1": w1, "w2": w2, "w3": w3},
                        }
                        if "runtimes" in s_data:
                            s_data["runtimes"]["stage2_seconds"] = gp_res.get("runtime", 0.0)
                            s_data["runtimes"]["total_seconds"] = round(
                                s_data["runtimes"].get("solver_seconds", 0.0) + gp_res.get("runtime", 0.0), 2
                            )
                        with open(sum_path, "w", encoding="utf-8") as sf:
                            json.dump(s_data, sf, indent=2)
                    except Exception:
                        pass
        st.success(f"🎉 Goal Programming completed in {gp_res.get('runtime', 0.0)}s! Room allocation results displayed below.")

if st.session_state.gp_summary is not None and st.session_state.allocation_df is not None:
    gp_summary = st.session_state.gp_summary
    alloc_df = st.session_state.allocation_df

    st.markdown("---")
    st.markdown("### 📋 Room Allocation Optimization Summary")

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    with k1:
        st.metric("Objective Z₂", f"{gp_summary.get('objective_value', 0.0):,.1f}")
    with k2:
        st.metric("Room Utilization", f"{gp_summary['utilization_pct']}%")
    with k3:
        st.metric("Unused Capacity (d1+)", f"{gp_summary['unused_capacity']:,} seats")
    with k4:
        st.metric("Room Penalty (d2+)", f"{gp_summary['room_penalty']:,}")
    with k5:
        st.metric("Extra Room Uses (d3+)", f"{gp_summary['room_splits']}")
    with k6:
        st.metric("Solver Runtime", f"{gp_summary['runtime']}s")

    # Gauge chart
    col_g1, col_g2 = st.columns([4, 6])
    with col_g1:
        st.plotly_chart(plot_room_utilization_gauge(gp_summary["utilization_pct"]), use_container_width=True)
    with col_g2:
        st.markdown("#### 🛡️ Independent Room Allocation Audit")
        validator = IndependentValidator(
            enrollments_df=data["enrollments"],
            exam_periods_df=data["exam_periods"],
            exam_rooms_df=data["exam_rooms"],
            constraints_df=data["constraints"],
            rooms_df=data["rooms"],
            exams_df=data["exams_with_enrollment"],
        )
        val_r = validator.validate_room_allocation(alloc_df, st.session_state.timetable_df)
        
        st.markdown(f"• **All Students Accommodated:** {'✅ PASS' if val_r['student_accommodation']['status'] == 'PASS' else '❌ FAIL'}")
        st.markdown(f"• **Room Capacities Respected:** {'✅ PASS' if val_r['capacity_compliance']['status'] == 'PASS' else '❌ FAIL'}")
        st.markdown(f"• **No Room Double-Booking:** {'✅ PASS' if val_r['double_booking']['status'] == 'PASS' else '⚠️ ' + str(val_r['double_booking']['violations']) + ' Collisions'}")
        st.markdown(f"• **Fixed-Room Assignments:** {'✅ PASS' if val_r['fixed_room_compliance']['status'] == 'PASS' else '❌ FAIL'}")

    # Full Room Allocation Table
    st.markdown("### 🪑 Examination Room Allocation Table")
    
    col_rf1, col_rf2 = st.columns(2)
    with col_rf1:
        rf_period = st.multiselect("Filter by Assigned Period:", options=sorted(alloc_df["period_id"].unique()), default=[])
    with col_rf2:
        rf_split = st.checkbox("Show Only Split Examinations", value=False)

    disp_alloc = alloc_df.copy()
    if rf_period:
        disp_alloc = disp_alloc[disp_alloc["period_id"].isin(rf_period)]
    if rf_split:
        disp_alloc = disp_alloc[disp_alloc["is_split"] == True]

    st.dataframe(disp_alloc, use_container_width=True, hide_index=True)

    # Downloads
    d_col1, d_col2 = st.columns(2)
    with d_col1:
        csv_buffer = disp_alloc.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Room Allocation (CSV)",
            data=csv_buffer,
            file_name="examopt_room_allocation.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with d_col2:
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            disp_alloc.to_excel(writer, index=False, sheet_name="Rooms")
        st.download_button(
            label="📥 Download Room Allocation (Excel)",
            data=excel_buffer.getvalue(),
            file_name="examopt_room_allocation.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    # Multi-Objective Trade-off Analysis Section
    st.markdown("---")
    st.markdown("### 📈 Multi-Objective Goal Weight Trade-off Analysis")
    st.markdown("Demonstration of Pareto trade-offs as decision-makers shift priority across the three goals.")
    
    if len(st.session_state.gp_scenarios) > 0:
        scenarios_df = pd.DataFrame(st.session_state.gp_scenarios).drop_duplicates(subset=["Scenario"], keep="last")
        st.dataframe(scenarios_df, use_container_width=True, hide_index=True)
        if len(scenarios_df) > 1:
            st.plotly_chart(plot_goal_tradeoff_scenarios(scenarios_df), use_container_width=True)
        else:
            st.caption("Change the weight sliders above and run again to compare trade-off scenarios on the chart.")
else:
    st.info("👆 Configure the goal weights above and click **Run Goal Programming Room Allocation**.")
