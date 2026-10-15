"""
02_Conflict_Analysis.py
=======================
Analysis of student enrollment conflict structure and co-enrollment patterns.
Dynamically calculated from real enrollments.csv and exams.csv.
"""

import streamlit as st
import pandas as pd
from src.data_loader import load_all_data
from src.conflict_builder import get_conflict_graph
from src.visualization import plot_conflict_degree_distribution

st.set_page_config(page_title="Conflict Analysis — ExamOpt", page_icon="⚡", layout="wide")

if "data" not in st.session_state:
    st.session_state.data = load_all_data()

data = st.session_state.data

st.markdown("## ⚡ Student Examination Conflict Analysis")
st.markdown("""
A conflict exists between Exam $e$ and Exam $e'$ whenever at least one student is enrolled in both examinations. 
In Binary Integer Programming, these pairs form the strict hard constraint:  
$$x_{e, t} + x_{e', t} \\le 1 \\quad \\forall (e, e') \\in C, \\ \\forall t \\in T_e \\cap T_{e'}$$
All metrics on this page are computed dynamically from `examopt_data/enrollments.csv`.
""")

cg = get_conflict_graph(data["enrollments"], total_exams=len(data["exams"]))
stats = cg.get_summary_statistics()

# Macro KPI Cards calculated directly from real dataset
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("Total Conflict Pairs", f"{stats['total_conflict_pairs']:,}")
with col2:
    st.metric("Shared Enrollments", f"{stats['total_shared_student_instances']:,}")
with col3:
    st.metric("Max Conflict Degree", f"{stats['max_conflict_degree']} (Exam 434)")
with col4:
    st.metric("Avg Conflict Degree", stats["average_conflict_degree"])
with col5:
    st.metric("Isolated (0 Conflict) Exams", stats["zero_conflict_exams"])

# Conflict degree distribution chart
degrees = list(cg.degree.values())
st.plotly_chart(plot_conflict_degree_distribution(degrees), use_container_width=True)

col_top, col_search = st.columns([5, 5])

with col_top:
    st.markdown("### 🏆 Top 20 Most Conflicting Examinations")
    st.caption("Exams with highest co-enrollment degree requiring priority scheduling in BIP.")
    top_df = cg.get_top_conflicting_exams(top_n=20)
    st.dataframe(top_df, use_container_width=True, hide_index=True)

with col_search:
    st.markdown("### 🔍 Specific Exam Conflict Inspector")
    search_exam = st.number_input(
        "Enter Exam ID to inspect conflicts (e.g., 293):",
        min_value=1,
        max_value=len(data["exams"]),
        value=293,
        step=1,
    )

    exam_conflicts_df = cg.get_conflicts_for_exam(int(search_exam))
    target_deg = cg.degree.get(int(search_exam), 0)
    target_students = len(cg.exam_to_students.get(int(search_exam), []))
    max_shared = (
        exam_conflicts_df["Shared Students"].max()
        if not exam_conflicts_df.empty
        else 0
    )

    st.markdown(f"#### Profile for Exam {search_exam}")
    p1, p2, p3 = st.columns(3)
    with p1:
        st.metric("Enrolled Students", f"{target_students:,}")
    with p2:
        st.metric("Conflict Degree", f"{target_deg} exams")
    with p3:
        st.metric("Max Shared with 1 Exam", f"{max_shared} students")

    if not exam_conflicts_df.empty:
        st.caption(f"Showing all {len(exam_conflicts_df)} conflicting examinations for Exam {search_exam}:")
        st.dataframe(exam_conflicts_df, use_container_width=True, hide_index=True)
    else:
        st.success(f"Exam {search_exam} has zero conflicts with other examinations!")
