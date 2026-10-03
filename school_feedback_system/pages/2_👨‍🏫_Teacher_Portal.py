import streamlit as st
from datetime import date
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from session_service import get_active_session
from auth_service import authenticate_teacher
from report_service import get_teacher_report
from import_export_service import export_dataframe_to_excel

st.set_page_config(page_title="Teacher Analytics Portal", page_icon="👨‍🏫", layout="wide")

st.title("👨‍🏫 Teacher Feedback & Analytics Portal")

active_session = get_active_session()
if not active_session:
    st.error("No active academic session found. Please contact the administrator.")
    st.stop()

# Session State for Teacher
if "teacher_user" not in st.session_state:
    st.session_state.teacher_user = None

# --- Login Form ---
if not st.session_state.teacher_user:
    st.markdown(f"**Session:** `{active_session['name']}` | Sign in using your registered teacher credentials.")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        with st.form("teacher_login_form"):
            t_id = st.text_input("Teacher ID / Employee Code", placeholder="e.g. TCH-001").strip()
            phone = st.text_input("Registered Phone Number", placeholder="e.g. 9876543210").strip()
            dob = st.date_input("Date of Birth", min_value=date(1950, 1, 1), max_value=date(2010, 1, 1), value=date(1985, 1, 1))
            
            submit_btn = st.form_submit_button("Access My Analytics ➡️", type="primary", use_container_width=True)
            if submit_btn:
                if not t_id or not phone:
                    st.error("Please provide your Teacher ID and Phone Number.")
                else:
                    success, msg, data = authenticate_teacher(active_session["id"], t_id, phone, dob)
                    if success:
                        st.session_state.teacher_user = data
                        st.rerun()
                    else:
                        st.error(msg)
    with col2:
        st.markdown("""
        ### 🛡️ Privacy & Aggregation Policy
        - **Anonymous Feedback:** To foster honest evaluation, feedback is collected without student identifiers.
        - **K-Anonymity Protection:** Results for class groups with fewer than 5 responses are automatically suppressed to prevent statistical identification.
        - **Self-Service Analytics:** You have full visibility into your aggregated ratings across all classes and subjects you teach.
        """)
        
    if st.button("⬅️ Back to Main Menu"):
        st.switch_page("app.py")
    st.stop()

# --- Authenticated Teacher Dashboard ---
teacher = st.session_state.teacher_user
report_data = get_teacher_report(active_session["id"], teacher["id"])

# Header & Logout
hcol1, hcol2 = st.columns([4, 1])
with hcol1:
    st.markdown(f"## 👤 {report_data['teacher_name']}")
    st.markdown(f"**Department:** {report_data['department']} &nbsp;|&nbsp; **Academic Session:** `{active_session['name']}`")
with hcol2:
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.teacher_user = None
        st.rerun()

st.divider()

# High-Level Metrics
overall_suppressed = report_data["overall_is_suppressed"]
m1, m2, m3, m4 = st.columns(4)
with m1:
    average_value = "N/A" if report_data["total_responses"] == 0 else "Suppressed" if overall_suppressed else f"{report_data['overall_average']} / 5.0"
    st.metric("Overall Average Rating", average_value)
with m2:
    response_value = "Suppressed" if overall_suppressed and report_data["total_responses"] > 0 else report_data["total_responses"]
    st.metric("Total Responses Received", response_value)
with m3:
    st.metric("Assigned Classes", report_data['total_classes'])
with m4:
    sat_pct = round((report_data['overall_average'] / 5.0) * 100, 1) if report_data['total_responses'] > 0 and not overall_suppressed else 0
    satisfaction_value = "N/A" if report_data["total_responses"] == 0 else "Suppressed" if overall_suppressed else f"{sat_pct}%"
    st.metric("Overall Satisfaction", satisfaction_value)

st.divider()

# Two Main Views
view_tab1, view_tab2 = st.tabs(["📊 Overall Performance & Question Insights", "🏫 Class-wise Breakdown"])

# TAB 1: OVERALL PERFORMANCE
with view_tab1:
    if report_data["total_responses"] == 0:
        st.info("ℹ️ No feedback responses have been submitted for your classes yet in this session.")
    elif overall_suppressed:
        st.warning("Overall results are suppressed until the minimum response threshold is reached.")
    else:
        st.subheader("Performance Across All Questions")
        
        q_data = report_data["overall_questions"]
        if q_data:
            q_df = pd.DataFrame([
                {
                    "Question ID": f"Q{q['question_id']}",
                    "Question": q["question_text"],
                    "Average Rating": q["average"],
                    "Responses": q["count"]
                }
                for q in q_data
            ])
            
            # Visual Bar Chart
            fig = px.bar(
                q_df,
                x="Question ID",
                y="Average Rating",
                text="Average Rating",
                hover_data=["Question", "Responses"],
                title="Average Rating by Evaluation Question",
                range_y=[0, 5.2],
                color="Average Rating",
                color_continuous_scale="Teal"
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
            
            # Detailed Question Table
            st.markdown("##### Detailed Evaluation Statements:")
            st.dataframe(q_df[["Question ID", "Question", "Average Rating", "Responses"]], use_container_width=True, hide_index=True)
            
            # Export Option
            excel_bytes = export_dataframe_to_excel(q_df, sheet_name="Teacher_Overall")
            st.download_button(
                "📥 Download Overall Report (Excel)",
                data=excel_bytes,
                file_name=f"teacher_{teacher['teacher_id']}_overall.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

# TAB 2: CLASS-WISE BREAKDOWN
with view_tab2:
    classes = report_data["classes"]
    if not classes:
        st.info("No class mappings assigned to your profile.")
    else:
        class_options = [f"Class {c['class_level']}-{c['section']} ({c['subject']})" for c in classes]
        selected_class_label = st.selectbox("Select Class & Section to Inspect:", class_options)
        
        selected_class_idx = class_options.index(selected_class_label)
        target_class = classes[selected_class_idx]
        
        st.write("")
        c_col1, c_col2, c_col3 = st.columns(3)
        with c_col1:
            st.metric("Enrolled / Eligible Students", target_class["eligible_count"])
        with c_col2:
            response_value = "Suppressed" if target_class["is_suppressed"] and target_class["response_count"] > 0 else target_class["response_count"]
            st.metric("Responses Collected", response_value)
        with c_col3:
            if target_class["is_suppressed"]:
                st.metric("Class Average", "Suppressed 🛡️")
            else:
                st.metric("Class Average", f"{target_class['class_average']} / 5.0" if target_class['class_average'] else "N/A")
                
        if target_class["is_suppressed"]:
            st.warning("🛡️ **K-Anonymity Notice:** Detailed results are suppressed until this group reaches the minimum response threshold.")
        else:
            q_list = target_class["question_breakdown"]
            if q_list:
                c_df = pd.DataFrame([
                    {
                        "Question ID": f"Q{q['question_id']}",
                        "Question": q["question_text"],
                        "Average Rating": q["average"],
                        "Count": q["count"]
                    }
                    for q in q_list
                ])
                
                c_fig = px.bar(
                    c_df,
                    x="Question ID",
                    y="Average Rating",
                    text="Average Rating",
                    hover_data=["Question"],
                    range_y=[0, 5.2],
                    title=f"Question Averages for {selected_class_label}",
                    color="Average Rating",
                    color_continuous_scale="Blues"
                )
                c_fig.update_traces(textposition="outside")
                st.plotly_chart(c_fig, use_container_width=True)
                
                st.dataframe(c_df, use_container_width=True, hide_index=True)
                
                # Export class report
                c_excel = export_dataframe_to_excel(c_df, sheet_name="Class_Report")
                st.download_button(
                    f"📥 Export {selected_class_label} Report (Excel)",
                    data=c_excel,
                    file_name=f"teacher_{teacher['teacher_id']}_class_{target_class['class_level']}{target_class['section']}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
