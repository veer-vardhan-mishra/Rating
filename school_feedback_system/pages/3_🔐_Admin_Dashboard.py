import streamlit as st
from datetime import date, datetime
import pandas as pd
import json
import plotly.express as px
from config import Config
from database import (
    get_db_session, Student, Teacher, AuditLog,
    QuestionnaireTemplate, TeacherSubjectMapping, MappingQuestionnaire
)
from auth_service import authenticate_admin
from session_service import (
    create_session, get_all_sessions, get_active_session,
    set_active_session, launch_poll, close_poll, get_closure_info
)
from mapping_service import (
    get_students_for_class_section, create_or_update_mapping,
    get_mappings_for_session, delete_mapping
)
from questionnaire_service import (
    get_questionnaires_for_session, create_questionnaire, update_questionnaire,
    duplicate_questionnaire, get_questionnaire_by_id, seed_default_questionnaires,
    delete_questionnaire, QUESTION_SCALES, assign_questionnaire_to_teachers,
    DEFAULT_ACADEMIC_QUESTIONS, DEFAULT_SPORTS_QUESTIONS
)
from report_service import (
    get_admin_school_overview, get_school_report_matrix,
    get_teacher_comparisons, get_teacher_report
)
from import_export_service import (
    generate_student_excel_template, generate_teacher_excel_template,
    import_students_from_file, import_teachers_from_file, export_dataframe_to_excel
)

st.set_page_config(page_title="Admin Control Center", page_icon="🔐", layout="wide")

st.title("🔐 Administrator Control Center")

# Admin Session State
if "admin_user" not in st.session_state:
    st.session_state.admin_user = None

# --- Admin Authentication ---
if not st.session_state.admin_user:
    st.markdown("Sign in with administrative credentials to manage sessions, mappings, questionnaires, and reports.")
    col1, col2 = st.columns([1, 1])
    with col1:
        with st.form("admin_login_form"):
            username = st.text_input("Username", value="admin").strip()
            password = st.text_input("Password", type="password").strip()
            submitted = st.form_submit_button("Sign In ➡️", type="primary", use_container_width=True)
            if submitted:
                success, msg, data = authenticate_admin(username, password)
                if success:
                    st.session_state.admin_user = data
                    st.rerun()
                else:
                    st.error(msg)
                    
        st.caption("Default credentials: `admin` / `admin123` (Change in `.env` for production)")
    with col2:
        st.markdown("""
        ### ⚙️ System Capabilities
        - **Multi-Year Sessions:** Configure recurring sessions with distinct settings and archives.
        - **Excel Batch Import:** Upload students and teachers directly from spreadsheets with validation.
        - **Fine-Grained Mapping:** Map teachers to specific classes, sections, and elective student cohorts.
        - **Google Forms-Style Questionnaires:** Build unique evaluation questions for individual teachers or departments.
        - **Cryptographic Closure:** Seal responses with a SHA-256 fingerprint when poll ends.
        """)
        
    if st.button("⬅️ Back to Main Menu"):
        st.switch_page("app.py")
    st.stop()

# --- Authenticated Admin Console ---
admin = st.session_state.admin_user
active_session = get_active_session()

# Top Navigation Bar
top_c1, top_c2, top_c3 = st.columns([3, 2, 1])
with top_c1:
    if active_session:
        st.markdown(f"**Active Session:** `{active_session['name']}` | **Poll Status:** `{active_session['status']}`")
    else:
        st.warning("No active session selected.")
with top_c2:
    sessions_list = get_all_sessions()
    if sessions_list:
        sess_names = [s["name"] for s in sessions_list]
        cur_idx = sess_names.index(active_session["name"]) if (active_session and active_session["name"] in sess_names) else 0
        selected_sess_name = st.selectbox("Switch Session:", sess_names, index=cur_idx, label_visibility="collapsed")
        if active_session and selected_sess_name != active_session["name"]:
            target_s = next(s for s in sessions_list if s["name"] == selected_sess_name)
            set_active_session(target_s["id"])
            st.rerun()
with top_c3:
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.admin_user = None
        st.rerun()

st.divider()

# Main Admin Tabs
tab_sess, tab_data, tab_map, tab_q, tab_rep, tab_exp, tab_audit = st.tabs([
    "📅 Sessions & Lifecycle",
    "📥 Data Import & Records",
    "🗺️ Teacher-Subject Mapping",
    "📝 Questionnaire Builder (Google Form)",
    "📊 School Reports & Analytics",
    "💾 Export Center",
    "🛡️ Audit & Integrity"
])

# ==========================================
# TAB 1: SESSIONS & LIFECYCLE
# ==========================================
with tab_sess:
    st.subheader("Academic Sessions & Poll Controls")
    
    col_s1, col_s2 = st.columns([1, 1])
    with col_s1:
        st.markdown("#### Create New Academic Session")
        with st.form("create_session_form"):
            s_name = st.text_input("Session Name", placeholder="e.g. 2027-28 or 2026-Term2")
            s_start = st.date_input("Start Date", value=date.today())
            s_end = st.date_input("End Date", value=date(date.today().year + 1, 3, 31))
            s_active = st.checkbox("Set as currently active session", value=True)
            
            create_btn = st.form_submit_button("Create Session ➕", type="primary")
            if create_btn:
                if not s_name:
                    st.error("Please enter a session name.")
                else:
                    success, msg, sid = create_session(s_name, s_start, s_end, s_active)
                    if success:
                        seed_default_questionnaires(sid)
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
                        
    with col_s2:
        if active_session:
            st.markdown(f"#### Lifecycle Actions for `{active_session['name']}`")
            status = active_session["status"]
            st.write(f"Current Status: **{status}**")
            
            if status == "DRAFT":
                st.info("Poll is in DRAFT. Ensure students, teachers, mappings, and questions are ready before launching.")
                if st.button("🚀 Launch Poll (Make Live)", type="primary", use_container_width=True):
                    success, msg = launch_poll(active_session["id"])
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
            elif status == "LIVE":
                st.success("🟢 Poll is currently LIVE! Students can submit feedback.")
                st.markdown("---")
                st.markdown("##### Finalize & Close Poll")
                st.caption("Closing seals all feedback records permanently. A cryptographic SHA-256 fingerprint snapshot will be generated. Responses cannot be modified.")
                
                confirm_close = st.checkbox("I confirm that feedback collection has concluded.")
                if st.button("🔒 Close Poll & Seal Responses", type="primary", disabled=not confirm_close, use_container_width=True):
                    success, msg, chash = close_poll(active_session["id"], admin["username"])
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
            elif status == "CLOSED":
                st.error("🔒 Poll is finalized and CLOSED. Data is read-only and tamper-evident.")
                c_info = get_closure_info(active_session["id"])
                if c_info:
                    st.markdown(f"""
                    - **Closed By:** `{c_info['closed_by']}`
                    - **Closed At:** `{c_info['closed_at']}`
                    - **Total Responses Sealed:** `{c_info['total_responses']}`
                    - **SHA-256 Integrity Hash:** `{c_info['closure_hash']}`
                    """)
        else:
            st.info("Please create or select an active session.")
            
    st.markdown("---")
    st.markdown("#### All Academic Sessions History")
    all_sess = get_all_sessions()
    if all_sess:
        sess_df = pd.DataFrame([
            {
                "ID": s["id"],
                "Name": s["name"],
                "Start Date": s["start_date"],
                "End Date": s["end_date"],
                "Status": s["status"],
                "Active": "⭐ Yes" if s["is_active"] else "No",
                "Students": s["student_count"],
                "Teachers": s["teacher_count"],
                "Responses": s["response_count"]
            }
            for s in all_sess
        ])
        st.dataframe(sess_df, use_container_width=True, hide_index=True)


# ==========================================
# TAB 2: DATA IMPORT & RECORDS
# ==========================================
with tab_data:
    if not active_session:
        st.warning("Please activate a session first.")
    else:
        st.subheader(f"Data Import & Enrolment for `{active_session['name']}`")
        
        # Download Sample Templates
        st.markdown("#### 1. Download Standard Excel Templates")
        t_col1, t_col2 = st.columns(2)
        with t_col1:
            st_bytes = generate_student_excel_template()
            st.download_button(
                "📥 Download Student Import Template (.xlsx)",
                data=st_bytes,
                file_name="student_import_template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        with t_col2:
            tch_bytes = generate_teacher_excel_template()
            st.download_button(
                "📥 Download Teacher Import Template (.xlsx)",
                data=tch_bytes,
                file_name="teacher_import_template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
            
        st.markdown("---")
        
        # Upload Files
        st.markdown("#### 2. Upload and Import Records")
        imp_col1, imp_col2 = st.columns(2)
        
        with imp_col1:
            st.markdown("##### 🎓 Upload Students File")
            st.caption("Supports .xlsx, .xls, .csv. Required: `admission_number`, `student_name`, `class`, `section`.")
            st_file = st.file_uploader("Select Student File", type=["xlsx", "xls", "csv"], key="uploader_students")
            if st_file:
                if st.button("Validate & Import Students ➡️", type="primary"):
                    success, msg, rep = import_students_from_file(active_session["id"], st_file.getvalue(), st_file.name)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
                        if "errors" in rep and rep["errors"]:
                            with st.expander("View Import Errors"):
                                for e in rep["errors"]:
                                    st.write(f"- {e}")
                                    
        with imp_col2:
            st.markdown("##### 👨‍🏫 Upload Teachers File")
            st.caption("Supports .xlsx, .xls, .csv. Required: `teacher_id`, `teacher_name`, `phone_number`, `date_of_birth`.")
            tch_file = st.file_uploader("Select Teacher File", type=["xlsx", "xls", "csv"], key="uploader_teachers")
            if tch_file:
                if st.button("Validate & Import Teachers ➡️", type="primary"):
                    success, msg, rep = import_teachers_from_file(active_session["id"], tch_file.getvalue(), tch_file.name)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
                        if "errors" in rep and rep["errors"]:
                            with st.expander("View Import Errors"):
                                for e in rep["errors"]:
                                    st.write(f"- {e}")

        st.markdown("---")
        # View Enrolled Students & Teachers
        st.markdown("#### 3. View Current Records")
        view_st, view_tch = st.tabs(["Enrolled Students", "Registered Teachers"])
        
        with view_st:
            with get_db_session() as db:
                students = db.query(Student).filter_by(session_id=active_session["id"]).all()
                if not students:
                    st.info("No students enrolled in this session yet.")
                else:
                    st.write(f"Total Enrolled: **{len(students)}**")
                    st_data = pd.DataFrame([
                        {
                            "Admission No": s.admission_number,
                            "Name": s.student_name,
                            "Class": s.class_level,
                            "Section": s.section,
                            "Stream": s.stream or "General",
                            "Roll No": s.roll_number or ""
                        }
                        for s in students
                    ])
                    # Search and filter
                    search_term = st.text_input("Filter by Name or Admission No:", key="st_search")
                    if search_term:
                        st_data = st_data[st_data["Name"].str.contains(search_term, case=False, na=False) | st_data["Admission No"].str.contains(search_term, case=False, na=False)]
                    st.dataframe(st_data, use_container_width=True, hide_index=True)
                    
        with view_tch:
            with get_db_session() as db:
                teachers = db.query(Teacher).filter_by(session_id=active_session["id"]).all()
                if not teachers:
                    st.info("No teachers registered in this session yet.")
                else:
                    st.write(f"Total Teachers: **{len(teachers)}**")
                    tch_data = pd.DataFrame([
                        {
                            "Teacher Code": t.teacher_id,
                            "Name": t.teacher_name,
                            "Phone": t.phone_number,
                            "DOB": t.date_of_birth,
                            "Department": t.department,
                            "Subjects": t.subjects_taught or "",
                            "Email": t.email or ""
                        }
                        for t in teachers
                    ])
                    st.dataframe(tch_data, use_container_width=True, hide_index=True)


# ==========================================
# TAB 3: TEACHER-SUBJECT MAPPING
# ==========================================
with tab_map:
    if not active_session:
        st.warning("Please activate a session first.")
    else:
        st.subheader("Teacher-Subject-Student Mapping")
        st.markdown("""
        Assign teachers to class/sections and choose which evaluation questionnaire applies.
        Use **Select All** for standard class cohorts, or select individual students for specialized streams.
        """)
        
        with get_db_session() as db:
            teachers = db.query(Teacher).filter_by(session_id=active_session["id"]).order_by(Teacher.teacher_name).all()
        q_templates = get_questionnaires_for_session(active_session["id"])
            
        if not teachers:
            st.warning("No teachers available. Please import teachers in the Data Import tab first.")
        else:
            map_form_col, map_list_col = st.columns([1, 1])
            
            with map_form_col:
                st.markdown("#### Create / Update Mapping")
                
                # Class & Section Selection
                c1, c2, c3 = st.columns(3)
                with c1:
                    sel_class = st.selectbox("Class Level", options=list(range(6, 13)), index=0)
                with c2:
                    sel_sec = st.selectbox("Section", options=["A", "B", "C", "D", "E"], index=0)
                with c3:
                    sel_stream = st.selectbox("Stream (Optional)", options=["General", "Science", "Commerce", "Humanities"], index=0)
                    
                # Teacher Selection
                teacher_options = {f"{t.teacher_name} ({t.department} - {t.teacher_id})": t for t in teachers}
                sel_teacher_str = st.selectbox("Select Teacher", options=list(teacher_options.keys()))
                sel_teacher_obj = teacher_options[sel_teacher_str]
                sel_teacher_id = sel_teacher_obj.id
                
                # Subject Selection
                subject_input = st.text_input("Subject Name", placeholder="e.g. Science, Mathematics, Physics").strip()
                
                # Questionnaire Template Dropdown with Auto-Detection
                # Build option labels showing target
                q_options = {}
                preselect_idx = 0
                for idx, q in enumerate(q_templates):
                    tag = "[General]"
                    if q["target_type"] == "TEACHER":
                        tag = f"[Teacher: {', '.join(q['teacher_names']) or 'Custom'}]"
                    elif q["target_type"] == "DEPARTMENT":
                        tag = f"[Dept: {q['category']}]"
                    label = f"{tag} {q['name']} ({q['question_count']} Qs)"
                    q_options[label] = q["id"]
                    
                    # Pre-select if targeted to this teacher
                    if q["target_type"] == "TEACHER" and sel_teacher_id in q["target_teacher_ids"]:
                        preselect_idx = idx
                    elif q["target_type"] == "DEPARTMENT" and q["category"] == sel_teacher_obj.department and preselect_idx == 0:
                        preselect_idx = idx
                        
                q_labels = list(q_options.keys())
                sel_q_label = st.selectbox(
                    "Evaluation Questionnaire for this Teacher & Subject:",
                    options=q_labels if q_labels else ["Default"],
                    index=preselect_idx if q_labels else 0,
                    help="You can give different questions to different teachers. Select or build a custom questionnaire in Tab 4."
                )
                sel_q_id = q_options.get(sel_q_label) if q_labels else None
                
                # Fetch eligible students for this class/section
                eligible_students = get_students_for_class_section(active_session["id"], sel_class, sel_sec)
                
                st.markdown("##### Assign Students:")
                if not eligible_students:
                    st.info(f"No students found in Class {sel_class}-{sel_sec}.")
                    selected_st_ids = []
                else:
                    select_all = st.checkbox(f"Select All ({len(eligible_students)} students in {sel_class}-{sel_sec})", value=True)
                    
                    student_display_map = {
                        f"{s['roll_number'] + '. ' if s['roll_number'] else ''}{s['name']} ({s['admission_number']})": s["id"]
                        for s in eligible_students
                    }
                    
                    if select_all:
                        default_sel = list(student_display_map.keys())
                    else:
                        default_sel = []
                        
                    picked_students = st.multiselect(
                        "Search / Pick Students:",
                        options=list(student_display_map.keys()),
                        default=default_sel
                    )
                    selected_st_ids = [student_display_map[p] for p in picked_students]
                    
                if st.button("💾 Save Subject Mapping", type="primary", use_container_width=True):
                    if not subject_input:
                        st.error("Please specify a subject name.")
                    elif not selected_st_ids:
                        st.error("Please select at least one student for this mapping.")
                    else:
                        success, msg, mid = create_or_update_mapping(
                            session_id=active_session["id"],
                            teacher_id=sel_teacher_id,
                            class_level=sel_class,
                            section=sel_sec,
                            subject=subject_input,
                            student_ids=selected_st_ids,
                            stream=sel_stream,
                            questionnaire_id=sel_q_id
                        )
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                            
            with map_list_col:
                st.markdown("#### Existing Mappings")
                cur_mappings = get_mappings_for_session(active_session["id"])
                if not cur_mappings:
                    st.info("No mappings created yet.")
                else:
                    m_df = pd.DataFrame([
                        {
                            "ID": m["id"],
                            "Class": f"{m['class_level']}-{m['section']}",
                            "Teacher": m["teacher_name"],
                            "Subject": m["subject"],
                            "Stream": m["stream"] or "General",
                            "Students": m["student_count"],
                            "Questionnaire": m["questionnaire_name"]
                        }
                        for m in cur_mappings
                    ])
                    st.dataframe(m_df, use_container_width=True, hide_index=True)
                    
                    # Delete action
                    st.markdown("##### Remove Mapping:")
                    del_id = st.selectbox(
                        "Select Mapping to delete:",
                        options=[m["id"] for m in cur_mappings],
                        format_func=lambda x: f"ID {x}: Class {next(m['class_level'] for m in cur_mappings if m['id']==x)}-{next(m['section'] for m in cur_mappings if m['id']==x)} ({next(m['subject'] for m in cur_mappings if m['id']==x)} - {next(m['teacher_name'] for m in cur_mappings if m['id']==x)})"
                    )
                    if st.button("🗑️ Delete Selected Mapping", type="secondary"):
                        if delete_mapping(del_id):
                            st.success("Mapping deleted.")
                            st.rerun()


# ==========================================
# TAB 4: QUESTIONNAIRE BUILDER (GOOGLE FORM STYLE)
# ==========================================
with tab_q:
    if not active_session:
        st.warning("Please activate a session first.")
    else:
        st.subheader("📝 Dynamic Questionnaire Form Builder (Google Forms Style)")
        st.markdown("""
        Create customized evaluation questionnaires just like **Google Forms**.
        You can write different questions, pick rating scales, and assign each questionnaire directly to **specific teachers** or departments.
        """)
        
        with get_db_session() as db:
            teachers_all = db.query(Teacher).filter_by(session_id=active_session["id"]).order_by(Teacher.teacher_name).all()
        templates_all = get_questionnaires_for_session(active_session["id"])
        
        # Initialize Google Form questions state
        if "gform_questions" not in st.session_state:
            st.session_state.gform_questions = [
                {"id": 1, "text": "Explains subject concepts clearly and uses understandable examples.", "type": "scale_1_5"},
                {"id": 2, "text": "Maintains discipline, punctuality, and encourages student participation.", "type": "scale_1_5"},
                {"id": 3, "text": "Is approachable, patient, and helps in clearing student doubts.", "type": "scale_1_5"},
            ]
        if "gform_editing_id" not in st.session_state:
            st.session_state.gform_editing_id = None
            
        g_mode = st.radio("Choose Action:", ["✨ Create / Edit Form", "📋 View All Questionnaires & Live Preview"], horizontal=True)
        
        if g_mode == "✨ Create / Edit Form":
            # Template selector for editing
            edit_col1, edit_col2 = st.columns([3, 1])
            with edit_col1:
                edit_options = {"[Create Brand New Blank Form]": None}
                for t in templates_all:
                    target_txt = f"Teacher: {', '.join(t['teacher_names'])}" if t['target_type'] == 'TEACHER' else t['category']
                    edit_options[f"Edit: {t['name']} ({target_txt})"] = t["id"]
                    
                selected_edit_label = st.selectbox("Load Template to Edit:", list(edit_options.keys()))
                selected_edit_id = edit_options[selected_edit_label]
                
            with edit_col2:
                if st.button("📥 Load into Editor", use_container_width=True):
                    if selected_edit_id is None:
                        st.session_state.gform_editing_id = None
                        st.session_state.gform_questions = [
                            {"id": 1, "text": "", "type": "scale_1_5"}
                        ]
                        st.session_state.form_title = ""
                        st.session_state.form_desc = ""
                    else:
                        t_data = get_questionnaire_by_id(selected_edit_id)
                        if t_data:
                            st.session_state.gform_editing_id = selected_edit_id
                            st.session_state.gform_questions = t_data["questions"] or [{"id": 1, "text": "", "type": "scale_1_5"}]
                            st.session_state.form_title = t_data["name"]
                            st.session_state.form_desc = t_data["description"]
                    st.rerun()

            st.write("")
            
            # Form Header Container (Google Forms Header)
            st.markdown("""
            <div style="background-color: #673AB7; color: white; padding: 1.2rem; border-radius: 10px 10px 0 0; margin-bottom: 0;">
                <h3 style="margin: 0; color: white;">📋 Questionnaire Form Settings</h3>
                <p style="margin: 0.2rem 0 0 0; font-size: 0.9rem; opacity: 0.9;">Configure title, student instructions, and teacher assignments.</p>
            </div>
            """, unsafe_allow_html=True)
            
            with st.container(border=True):
                f_title = st.text_input(
                    "Form Title *",
                    value=st.session_state.get("form_title", "Custom Teacher Evaluation"),
                    placeholder="e.g. Science Lab & Theory Evaluation - Dr. Veer Malhotra"
                )
                f_desc = st.text_area(
                    "Form Description / Guidance for Students",
                    value=st.session_state.get("form_desc", "Please provide your honest and objective feedback to help improve classroom teaching."),
                    placeholder="Instructions shown to students above the questions..."
                )
                
                st.markdown("##### 🎯 Assign This Questionnaire To:")
                assign_type = st.radio(
                    "Target Audience:",
                    options=["Specific Teacher(s)", "Subject Department", "All Teachers (School Default)"],
                    horizontal=True
                )
                
                target_teacher_ids = []
                target_category = "General"
                
                if assign_type == "Specific Teacher(s)":
                    t_opts = {f"{t.teacher_name} ({t.department} - {t.teacher_id})": t.id for t in teachers_all}
                    picked_tchs = st.multiselect("Select Teacher(s) who will receive these specific questions:", list(t_opts.keys()))
                    target_teacher_ids = [t_opts[p] for p in picked_tchs]
                    target_category = "Teacher"
                    st.caption("💡 When saved, all classes taught by the selected teachers will automatically use this questionnaire!")
                elif assign_type == "Subject Department":
                    dept_opts = sorted(list(set([t.department for t in teachers_all] + ["Academic", "Sports", "Science", "Mathematics", "Languages", "Computer Science"])))
                    target_category = st.selectbox("Select Department:", dept_opts)
                    st.caption(f"💡 Any teacher belonging to the '{target_category}' department will use this questionnaire.")
                else:
                    target_category = "All"
                    st.caption("💡 This will be the general fallback questionnaire for all academic teachers.")
                    
            st.write("")
            
            # Google Forms Dynamic Questions Section
            st.markdown("### ❓ Form Questions")
            st.caption("Add, edit, or remove questions below. Students will rate each statement using the chosen scale.")
            
            questions_to_save = []
            scale_type_keys = list(QUESTION_SCALES.keys())
            scale_type_names = [QUESTION_SCALES[k]["name"] for k in scale_type_keys]
            
            for idx, q_item in enumerate(st.session_state.gform_questions):
                q_id = idx + 1
                with st.container(border=True):
                    q_header_c1, q_header_c2, q_header_c3 = st.columns([3, 4, 1])
                    with q_header_c1:
                        st.markdown(f"**Question {q_id}**")
                    with q_header_c2:
                        cur_type = q_item.get("type", "scale_1_5")
                        cur_type_idx = scale_type_keys.index(cur_type) if cur_type in scale_type_keys else 0
                        sel_type_name = st.selectbox(
                            f"Rating Scale for Q{q_id}",
                            options=scale_type_names,
                            index=cur_type_idx,
                            key=f"scale_type_{idx}"
                        )
                        chosen_scale_key = scale_type_keys[scale_type_names.index(sel_type_name)]
                    with q_header_c3:
                        if len(st.session_state.gform_questions) > 1:
                            if st.button("🗑️", key=f"del_q_btn_{idx}", help="Delete this question"):
                                st.session_state.gform_questions.pop(idx)
                                st.rerun()
                                
                    # Question Text Input
                    q_text_val = st.text_input(
                        f"Enter Question / Statement {q_id}:",
                        value=q_item.get("text", ""),
                        key=f"q_text_input_{idx}",
                        placeholder="e.g. Explains concepts clearly and gives real-world examples."
                    )
                    
                    # Pill preview of options
                    scale_preview = QUESTION_SCALES[chosen_scale_key]["labels"]
                    st.caption(f"Student Options: {' | '.join(scale_preview)}")
                    
                    questions_to_save.append({
                        "id": q_id,
                        "text": q_text_val.strip(),
                        "type": chosen_scale_key,
                        "labels": scale_preview
                    })
                    
            # Builder Action Buttons
            btn_col1, btn_col2, btn_col3 = st.columns([2, 2, 3])
            with btn_col1:
                if st.button("➕ Add Another Question", use_container_width=True):
                    st.session_state.gform_questions.append({
                        "id": len(st.session_state.gform_questions) + 1,
                        "text": "",
                        "type": "scale_1_5"
                    })
                    st.rerun()
            with btn_col2:
                if st.button("🔄 Reset Questions", use_container_width=True):
                    st.session_state.gform_questions = [
                        {"id": 1, "text": "", "type": "scale_1_5"}
                    ]
                    st.rerun()
            with btn_col3:
                save_label = "💾 Save & Apply Questionnaire" if not st.session_state.gform_editing_id else "💾 Update Questionnaire"
                if st.button(save_label, type="primary", use_container_width=True):
                    # Validate
                    empty_qs = [q for q in questions_to_save if not q["text"]]
                    if not f_title.strip():
                        st.error("Please enter a title for the questionnaire.")
                    elif not questions_to_save or empty_qs:
                        st.error(f"Please provide question text for all {len(questions_to_save)} question(s).")
                    elif assign_type == "Specific Teacher(s)" and not target_teacher_ids:
                        st.error("Please select at least one teacher to assign this questionnaire to.")
                    else:
                        target_t_type = "TEACHER" if assign_type == "Specific Teacher(s)" else ("DEPARTMENT" if assign_type == "Subject Department" else "ALL")
                        
                        if st.session_state.gform_editing_id:
                            success, msg = update_questionnaire(
                                questionnaire_id=st.session_state.gform_editing_id,
                                name=f_title,
                                category=target_category,
                                questions=questions_to_save,
                                target_type=target_t_type,
                                target_teacher_ids=target_teacher_ids,
                                description=f_desc
                            )
                        else:
                            success, msg, qid = create_questionnaire(
                                session_id=active_session["id"],
                                name=f_title,
                                category=target_category,
                                questions=questions_to_save,
                                target_type=target_t_type,
                                target_teacher_ids=target_teacher_ids,
                                description=f_desc
                            )
                        if success:
                            st.success(f"🎉 {msg}")
                            st.session_state.form_title = f_title
                            st.rerun()
                        else:
                            st.error(msg)

            # Live Google Forms Student Preview Box
            st.divider()
            st.markdown("#### 📱 Live Student View Preview")
            st.caption("Here is exactly how students will see and rate this form on their screens:")
            
            with st.container(border=True):
                st.markdown(f"## {f_title or 'Untitled Evaluation Form'}")
                if f_desc:
                    st.info(f_desc)
                st.markdown("---")
                for q in questions_to_save:
                    st.markdown(f"**Q{q['id']}. {q['text'] or '(Question statement here)'}**")
                    st.radio(
                        f"Preview Q{q['id']}",
                        options=q["labels"],
                        index=len(q["labels"]) // 2,
                        horizontal=True,
                        key=f"preview_radio_{q['id']}",
                        label_visibility="collapsed"
                    )
                    st.write("")
                st.button("Save & Next Subject ➡️ (Preview)", disabled=True)

        elif g_mode == "📋 View All Questionnaires & Live Preview":
            st.markdown("#### All Configured Questionnaire Forms")
            if not templates_all:
                st.info("No questionnaires configured for this session yet.")
            else:
                for t in templates_all:
                    t_type = t.get("target_type", "ALL")
                    badge = "🌐 All Teachers"
                    if t_type == "TEACHER":
                        badge = f"👨‍🏫 Teacher: {', '.join(t['teacher_names']) if t['teacher_names'] else 'Custom'}"
                    elif t_type == "DEPARTMENT":
                        badge = f"🏷️ Department: {t['category']}"
                        
                    with st.expander(f"📋 {t['name']} &nbsp;|&nbsp; {badge} &nbsp;({t['question_count']} Questions)"):
                        if t.get("description"):
                            st.markdown(f"*{t['description']}*")
                        st.markdown("##### Questions in this form:")
                        for q in t["questions"]:
                            scale_name = QUESTION_SCALES.get(q.get("type", "scale_1_5"), {}).get("name", "1-5 Scale")
                            st.markdown(f"- **Q{q['id']}.** {q['text']} &nbsp; *(Scale: {scale_name})*")
                            
                        # Actions
                        a_col1, a_col2, a_col3 = st.columns(3)
                        with a_col1:
                            if st.button(f"✏️ Edit in Builder", key=f"btn_edit_{t['id']}"):
                                st.session_state.gform_editing_id = t["id"]
                                st.session_state.gform_questions = t["questions"]
                                st.session_state.form_title = t["name"]
                                st.session_state.form_desc = t.get("description", "")
                                st.rerun()
                        with a_col2:
                            clone_name = f"{t['name']} (Copy)"
                            if st.button(f"📑 Clone / Duplicate", key=f"btn_clone_{t['id']}"):
                                succ, msg, new_id = duplicate_questionnaire(t["id"], clone_name)
                                if succ:
                                    st.success(msg)
                                    st.rerun()
                                else:
                                    st.error(msg)
                        with a_col3:
                            if st.button(f"🗑️ Delete Form", key=f"btn_del_q_{t['id']}"):
                                delete_questionnaire(t["id"])
                                st.success("Form deleted.")
                                st.rerun()


# ==========================================
# TAB 5: SCHOOL REPORTS & ANALYTICS
# ==========================================
with tab_rep:
    if not active_session:
        st.warning("Please activate a session first.")
    else:
        st.subheader("School-Wide Reports & Evaluation Matrix")
        
        overview = get_admin_school_overview(active_session["id"])
        
        # High Level KPIs
        kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
        with kpi1:
            st.metric("Enrolled Students", overview["total_students"])
        with kpi2:
            st.metric("Submitted Students", overview["submitted_students"])
        with kpi3:
            st.metric("Participation Rate", f"{overview['participation_rate']}%")
        with kpi4:
            st.metric("Responses Collected", overview["total_responses"])
        with kpi5:
            st.metric("School Average", f"{overview['school_avg']} / 5.0" if overview['total_responses'] > 0 else "N/A")
            
        st.divider()
        
        # Participation Chart
        c_stats = overview["class_stats"]
        if c_stats:
            c_df = pd.DataFrame(c_stats)
            fig_part = px.bar(
                c_df,
                x="class_level",
                y="rate",
                text="rate",
                title="Student Participation Rate by Class (%)",
                range_y=[0, 105],
                labels={"rate": "Participation Rate (%)", "class_level": "Class"},
                color="rate",
                color_continuous_scale="Blues"
            )
            fig_part.update_traces(texttemplate="%{text}%", textposition="outside")
            st.plotly_chart(fig_part, use_container_width=True)
            
        st.markdown("---")
        
        # Official School Report Matrix (PRD Section 6.3)
        st.markdown("#### 📋 School Report Matrix (PRD Section 6.3 Standard Format)")
        st.caption("Class | Section | Teacher | Subject | Q1 Avg | Q2 Avg | Q3 Avg ... | Overall Avg | Responses")
        
        matrix_df = get_school_report_matrix(active_session["id"])
        if matrix_df.empty:
            st.info("No mapping or response data available to generate report matrix.")
        else:
            st.dataframe(matrix_df, use_container_width=True, hide_index=True)
            
        st.markdown("---")
        
        # Teacher Comparison Leaderboard
        st.markdown("#### 👨‍🏫 Teacher Evaluation Summary")
        tch_comp_df = get_teacher_comparisons(active_session["id"])
        if not tch_comp_df.empty:
            st.dataframe(tch_comp_df, use_container_width=True, hide_index=True)
            
        st.markdown("---")
        
        # Individual Teacher Deep Dive
        st.markdown("#### 🔍 Individual Teacher Profile Inspector")
        with get_db_session() as db:
            teachers_all = db.query(Teacher).filter_by(session_id=active_session["id"]).all()
            
        if teachers_all:
            tch_dict = {f"{t.teacher_name} ({t.department} - {t.teacher_id})": t.id for t in teachers_all}
            sel_tch_label = st.selectbox("Select Teacher to inspect:", list(tch_dict.keys()))
            target_tch_id = tch_dict[sel_tch_label]
            
            t_rep = get_teacher_report(active_session["id"], target_tch_id, min_threshold=0) # Admin bypasses suppression for full audit
            
            pcol1, pcol2, pcol3 = st.columns(3)
            with pcol1:
                st.metric("Overall Average Rating", f"{t_rep['overall_average']} / 5.0" if t_rep['total_responses'] > 0 else "N/A")
            with pcol2:
                st.metric("Total Responses", t_rep["total_responses"])
            with pcol3:
                st.metric("Total Classes Taught", t_rep["total_classes"])
                
            if t_rep["overall_questions"]:
                q_df = pd.DataFrame([
                    {"Question": q["question_text"], "Average Rating": q["average"], "Responses": q["count"]}
                    for q in t_rep["overall_questions"]
                ])
                fig_t = px.bar(q_df, x="Question", y="Average Rating", text="Average Rating", range_y=[0, 5.2], title=f"Question Breakdown for {sel_tch_label}")
                fig_t.update_traces(textposition="outside")
                st.plotly_chart(fig_t, use_container_width=True)


# ==========================================
# TAB 6: EXPORT CENTER
# ==========================================
with tab_exp:
    if not active_session:
        st.warning("Please activate a session first.")
    else:
        st.subheader("Data Export Center")
        st.markdown("Download full analytical reports in Excel (.xlsx) and CSV formats for school records.")
        
        exp1, exp2 = st.columns(2)
        
        with exp1:
            st.markdown("##### 📥 Export Official School Report Matrix")
            st.caption("Complete breakdown by Class, Section, Teacher, Subject, and Question Averages.")
            matrix_df = get_school_report_matrix(active_session["id"])
            if not matrix_df.empty:
                excel_matrix = export_dataframe_to_excel(matrix_df, sheet_name="School_Matrix")
                st.download_button(
                    "Download School Matrix (Excel .xlsx)",
                    data=excel_matrix,
                    file_name=f"school_report_matrix_{active_session['name']}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                csv_matrix = matrix_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "Download School Matrix (CSV)",
                    data=csv_matrix,
                    file_name=f"school_report_matrix_{active_session['name']}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.info("No report data available to export.")
                
        with exp2:
            st.markdown("##### 📥 Export Teacher Evaluation Summary")
            st.caption("Aggregated teacher ratings, class counts, and total response counts.")
            tch_comp_df = get_teacher_comparisons(active_session["id"])
            if not tch_comp_df.empty:
                excel_tch = export_dataframe_to_excel(tch_comp_df, sheet_name="Teachers_Summary")
                st.download_button(
                    "Download Teacher Summary (Excel .xlsx)",
                    data=excel_tch,
                    file_name=f"teacher_summary_{active_session['name']}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                csv_tch = tch_comp_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "Download Teacher Summary (CSV)",
                    data=csv_tch,
                    file_name=f"teacher_summary_{active_session['name']}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.info("No teacher summary available to export.")


# ==========================================
# TAB 7: AUDIT & INTEGRITY
# ==========================================
with tab_audit:
    st.subheader("🛡️ Audit Logs & Cryptographic Integrity")
    st.markdown("Every privileged action, poll state transition, and tamper-evident closure hash is permanently logged.")
    
    with get_db_session() as db:
        logs = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(100).all()
        if not logs:
            st.info("No audit logs recorded yet.")
        else:
            log_data = pd.DataFrame([
                {
                    "Timestamp": l.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "Actor": l.actor,
                    "Action": l.action,
                    "Details": l.details,
                    "IP Address": l.ip_address or "Local"
                }
                for l in logs
            ])
            st.dataframe(log_data, use_container_width=True, hide_index=True)
            
    if active_session:
        c_info = get_closure_info(active_session["id"])
        if c_info:
            st.markdown("---")
            st.success("🔒 **Cryptographic Closure Verified:** This session is sealed.")
            st.code(f"""
Poll Closure Certificate:
Session Name:       {active_session['name']}
Closed By:          {c_info['closed_by']}
Closed At:          {c_info['closed_at']}
Total Responses:    {c_info['total_responses']}
SHA-256 Digest:     {c_info['closure_hash']}
            """, language="text")
