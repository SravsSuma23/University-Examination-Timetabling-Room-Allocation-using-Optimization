"""
06_Model_Inspector.py
=====================
Academic Model Inspector & Viva Defense Guide.
Presents the formal mathematical formulations, model mapping, and theoretical rationale.
"""

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Model Inspector — ExamOpt", page_icon="🔍", layout="wide")

st.markdown("## 🔍 Academic Model Inspector & Viva Defense Guide")
st.markdown("""
This section details the theoretical mathematical formulations, decision variables, deviation mechanics, 
and relational data mappings for the **Operations Research Course Examination (23MNG336)**.
""")

tab_m1, tab_m2, tab_map, tab_viva = st.tabs([
    "📐 Model 1: BIP Timetabling",
    "🎯 Model 2: Weighted Goal Programming",
    "🗺️ Dataset-to-Model Mapping",
    "🎓 Professor Viva Q&A Guide",
])

with tab_m1:
    st.markdown("### Model 1: Binary Integer Programming (BIP) Examination Timetabling")
    
    st.markdown("#### 1. Sets and Indices")
    st.markdown("""
    - $e \in E$: Set of examinations, where $|E| = 2,198$.
    - $t \in T$: Set of examination periods, where $T = \{1, 2, \dots, 29\}$.
    - $T_e \subseteq T$: Permissible periods for examination $e$ (from `exam_periods.csv`).
    - $(e, e') \in C$: Set of conflicting examination pairs that share $\ge 1$ student (from `enrollments.csv`).
    - $FT \subset E$: Set of fixed-time examinations where $|T_e| = 1$.
    - $D$: Set of distribution constraints (from `constraints.csv`).
    """)

    st.markdown("#### 2. Parameters")
    st.markdown("""
    - $p_{e, t}$: Undesirability penalty for assigning exam $e$ to period $t$ (from `periods.csv`: Saturday = 4, Friday PM = 1, Weekday = 0).
    - $N_e$: Number of registered students in examination $e$.
    """)

    st.markdown("#### 3. Decision Variables")
    st.latex(r"""
    \begin{aligned}
    x_{e, t} \in \{0, 1\} & = \begin{cases} 1 & \text{if examination } e \text{ is assigned to period } t \\ 0 & \text{otherwise} \end{cases} \quad \forall e \in E, \ t \in T_e \\
    c_{e_1, e_2} \in [0, 1] & = \text{Continuous collision indicator for simultaneous assignment of conflicting pair } (e_1, e_2) \in C \\
    z_{e_1, e_2, t} \in [0, 1] & = \text{Period-specific slack indicator (used in prior pairwise-period formulation)}
    \end{aligned}
    """)

    st.markdown("#### 4. Objective Function (Combined Soft Optimization)")
    st.latex(r"""
    \min Z_1 = \alpha \underbrace{\sum_{e \in E} \sum_{t \in T_e} p_t \cdot x_{e, t}}_{Z_{\text{period}}} + \beta \underbrace{\sum_{(e_1, e_2) \in C} s_{e_1, e_2} \cdot c_{e_1, e_2}}_{Z_{\text{conflict}}} \quad (\alpha=1.0, \ \beta=100.0)
    """)
    st.caption("Combines period undesirability penalties (Z_period) with student co-enrollment conflict penalties (Z_conflict), weighted by shared student counts s_{e1, e2}.")

    st.markdown("#### 5. Hard Operational & Administrative Constraints")
    st.latex(r"""
    \begin{aligned}
    \text{Exact-One Period Assignment:} \quad & \sum_{t \in T_e} x_{e, t} = 1 \quad \forall e \in E \\
    \text{Fixed-Time Enforcement:} \quad & x_{e, t^*} = 1 \quad \forall e \in FT, \ \{t^*\} = T_e \\
    \text{Same-Period Distribution:} \quad & x_{e_1, t} - x_{e_2, t} = 0 \quad \forall t \in T_{e_1} \cup T_{e_2}, \ \forall (e_1, e_2) \in D_{\text{same}} \\
    \text{Different-Period Distribution:} \quad & x_{e_1, t} + x_{e_2, t} \le 1 \quad \forall t \in T_{e_1} \cap T_{e_2}, \ \forall (e_1, e_2) \in D_{\text{diff}} \\
    \text{Precedence Distribution:} \quad & \sum_{t \in T_{e_1}} t \cdot x_{e_1, t} \le \sum_{t \in T_{e_2}} t \cdot x_{e_2, t} - 1 \quad \forall (e_1, e_2) \in D_{\text{prec}}
    \end{aligned}
    """)

    st.markdown("#### 6. Soft Direct-Conflict Linearization Link (Compact vs Pairwise-Period)")
    st.markdown("""
    - **Production Compact Formulation (`pairwise_compact`):** Exactly 1 continuous collision variable $c_{e_1, e_2} \in [0, 1]$ per conflicting pair $(e_1, e_2) \in C$:
    """)
    st.latex(r"""
    c_{e_1, e_2} \ge x_{e_1, t} + x_{e_2, t} - 1 \quad \forall (e_1, e_2) \in C, \ \forall t \in T_{e_1} \cap T_{e_2}
    """)
    st.markdown("""
    Because each exam satisfies $\sum_t x_{e,t} = 1$ and minimization forces $c_{e_1, e_2}$ down, $c_{e_1, e_2} = 1$ if and only if $e_1$ and $e_2$ collide in the same period. This reduces auxiliary conflict variables from **1,956,655** down to **72,066**.
    - **Previous Reference Formulation (`pairwise_z`):** Creates $z_{e_1, e_2, t} \in [0, 1]$ for every period $t$.
    """)

with tab_m2:
    st.markdown("### Model 2: Weighted Goal Programming (GP) Room Allocation")

    st.markdown("#### 1. Sets and Indices")
    st.markdown("""
    - $e \in E$: Set of scheduled examinations.
    - $r \in R$: Set of available campus rooms ($|R| = 524$).
    - $R_e \subseteq R$: Permissible examination rooms for exam $e$ (from `exam_rooms.csv`).
    - $t^*_e$: Fixed period assigned to examination $e$ from Stage 1 BIP solution.
    """)

    st.markdown("#### 2. Parameters")
    st.markdown("""
    - $C_r$: Physical seating capacity of room $r$.
    - $N_e$: Number of students registered for exam $e$.
    - $P_{r, t}$: Room undesirability penalty for room $r$ in period $t$ (from `room_period_penalties.csv`).
    - $w_1, w_2, w_3$: User-configured non-negative weights for Goal 1, Goal 2, and Goal 3.
    """)

    st.markdown("#### 3. Decision Variables")
    st.latex(r"""
    \begin{aligned}
    y_{e, r} \in \{0, 1\} & = \begin{cases} 1 & \text{if examination } e \text{ utilizes room } r \\ 0 & \text{otherwise} \end{cases} \\
    q_{e, r} \ge 0 & = \text{number of students of examination } e \text{ seated in room } r \\
    d_1^+, d_2^+, d_3^+ \ge 0 & = \text{positive deviation variables measuring over-achievement of undesirable goals}
    \end{aligned}
    """)

    st.markdown("#### 4. Hard Constraints")
    st.latex(r"""
    \begin{aligned}
    \text{All Students Accommodated:} \quad & \sum_{r \in R_e} q_{e, r} = N_e \quad \forall e \in E \\
    \text{Physical Room Capacity Limit:} \quad & q_{e, r} \le C_r \cdot y_{e, r} \quad \forall e \in E, \ r \in R_e \\
    \text{No Room Double-Booking:} \quad & \sum_{e: t^*_e = t} y_{e, r} \le 1 \quad \forall r \in R, \ \forall t \in T \\
    \text{Fixed-Room Enforcement:} \quad & y_{e, r_{fixed}} = 1 \quad \forall e \in FR
    \end{aligned}
    """)

    st.markdown("#### 5. Goal Programming Equations & Deviations")
    st.latex(r"""
    \begin{aligned}
    \textbf{Goal 1 (Minimize Unused Capacity):} \quad & \sum_{e, r} (C_r \cdot y_{e, r} - q_{e, r}) + d_1^- - d_1^+ = 0 \implies d_1^+ = U \\
    \textbf{Goal 2 (Minimize Room Penalties):} \quad & \sum_{e, r} P_{r, t^*_e} \cdot y_{e, r} + d_2^- - d_2^+ = 0 \implies d_2^+ = R \\
    \textbf{Goal 3 (Minimize Room Splitting):} \quad & \sum_{e} \left(\sum_r y_{e, r} - 1\right) + d_3^- - d_3^+ = 0 \implies d_3^+ = S \\
    \textbf{Weighted Goal Objective:} \quad & \min Z_2 = w_1 \cdot d_1^+ + w_2 \cdot d_2^+ + w_3 \cdot d_3^+
    \end{aligned}
    """)

with tab_map:
    st.markdown("### 🗺️ Relational Mapping: Dataset Files to Mathematical Model")
    
    mapping_data = [
        {"CSV File": "exams.csv", "Field": "exam_id", "Math Symbol": "e ∈ E", "Role in Model": "Index set of examination events."},
        {"CSV File": "periods.csv", "Field": "period_id, penalty", "Math Symbol": "t ∈ T, p_t", "Role in Model": "Index set of time slots and period objective penalty coefficients."},
        {"CSV File": "enrollments.csv", "Field": "student_id, exam_id", "Math Symbol": "(e, e') ∈ C", "Role in Model": "Bipartite graph generating the student conflict constraint pairs."},
        {"CSV File": "exam_periods.csv", "Field": "exam_id, period_id", "Math Symbol": "T_e ⊆ T", "Role in Model": "Domain restriction variables x[e, t]; determines fixed-time exams."},
        {"CSV File": "rooms.csv", "Field": "room_id, capacity", "Math Symbol": "r ∈ R, C_r", "Role in Model": "Available room set and upper bound capacity constraints."},
        {"CSV File": "exam_rooms.csv", "Field": "exam_id, room_id", "Math Symbol": "R_e ⊆ R", "Role in Model": "Eligible room choices y[e, r] and fixed-room constraints."},
        {"CSV File": "constraints.csv", "Field": "constraint_type, exam_ids", "Math Symbol": "d ∈ D", "Role in Model": "Institutional distribution constraints (same, different, precedence)."},
        {"CSV File": "room_period_penalties.csv", "Field": "room_id, period_id, penalty", "Math Symbol": "P_{r, t}", "Role in Model": "Coefficient for Goal 2 room undesirability penalty."},
        {"CSV File": "exams_with_enrollment.csv", "Field": "number_of_students", "Math Symbol": "N_e", "Role in Model": "RHS demand for student accommodation ∑ q[e, r] = N_e."},
    ]
    st.dataframe(pd.DataFrame(mapping_data), use_container_width=True, hide_index=True)

with tab_viva:
    st.markdown("### 🎓 Operations Research Viva Defense Preparation")

    viva_qa = [
        {
            "q": "Why use a Two-Stage Sequential Optimization approach rather than a single unified model?",
            "a": "A unified model assigning both periods and rooms simultaneously would require variables x[e, t, r] of size 2,198 × 29 × 524 ≈ 33.4 million 3D binary decision variables, creating an intractable Non-Linear/Quadratic Integer Program. Decoupling into Stage 1 (WHEN: BIP) and Stage 2 (WHERE: Goal Programming) reflects university institutional hierarchy, reduces dimensionality by orders of magnitude, and guarantees provable optimality."
        },
        {
            "q": "Why is Goal Programming chosen for Stage 2 rather than standard Linear Programming?",
            "a": "Room allocation inherently involves conflicting criteria: maximizing room seating efficiency, minimizing room undesirability penalties, and preventing room splitting (which confuses students and requires extra proctors). Standard LP can only optimize a single scalar objective. Weighted Goal Programming introduces deviation variables (d1+, d2+, d3+) from ideal aspiration levels, allowing decision-makers to evaluate Pareto trade-offs across competing institutional goals."
        },
        {
            "q": "What is the role of deviation variables d_i^- and d_i^+?",
            "a": "In Goal Programming, d_i^- represents under-achievement of the target, while d_i^+ represents over-achievement. Because unused capacity, room penalties, and room splits are all undesirable metrics with an ideal aspiration level of 0, any positive realization is an over-achievement (d_i^+ > 0). Minimizing ∑ w_i d_i^+ directly drives the schedule toward the ideal multi-criteria state."
        },
        {
            "q": "How does the solver guarantee that students do not have two exams at the same time?",
            "a": "The sparse conflict builder analyzes all 130,539 student enrollments to identify all 72,066 conflicting pairs (e, e') sharing at least one student. The BIP enforces the mutual exclusion constraint x[e, t] + x[e', t] ≤ 1 for every period t, which is mathematically impossible to satisfy if both exams are assigned to period t."
        },
    ]

    for item in viva_qa:
        with st.expander(f"❓ **{item['q']}**", expanded=True):
            st.markdown(f"**Answer:** {item['a']}")
