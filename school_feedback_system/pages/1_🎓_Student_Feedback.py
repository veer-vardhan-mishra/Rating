import streamlit as st
from session_service import get_active_session
from auth_service import authenticate_student
from mapping_service import get_student_assigned_cards
from feedback_service import save_card_responses, finalize_student_submission, get_completed_card_ids

st.set_page_config(page_title="Student Feedback Portal", page_icon="🎓", layout="wide")

st.title("🎓 Student Feedback Portal")

active_session = get_active_session()
if not active_session:
    st.error("No active academic session found. Please contact your school administrator.")
    st.stop()

if active_session["status"] != "LIVE":
    st.warning(f"⚠️ Feedback collection is currently **{active_session['status']}** for session {active_session['name']}. Submissions are only accepted when the poll is LIVE.")
    if st.button("⬅️ Back to Home"):
        st.switch_page("app.py")
    st.stop()

# Initialize session state for student login
if "student_user" not in st.session_state:
    st.session_state.student_user = None
if "student_cards" not in st.session_state:
    st.session_state.student_cards = []
if "completed_cards" not in st.session_state:
    st.session_state.completed_cards = set()
if "active_card_idx" not in st.session_state:
    st.session_state.active_card_idx = 0
if "submission_done" not in st.session_state:
    st.session_state.submission_done = False

# --- Login View ---
if not st.session_state.student_user:
    st.markdown(f"**Session:** `{active_session['name']}` | Please enter your School Admission Number to access your feedback form.")
    
    with st.container():
        col1, col2 = st.columns([1, 1])
        with col1:
            st.info("💡 **Instructions:** Each student evaluates only their assigned subject teachers. Your ratings are completely anonymous and cannot be edited after final submission.")
            
            with st.form("student_login_form"):
                admission_no = st.text_input("Admission Number", placeholder="e.g. ADM-6001 or 1001", help="Enter your unique school admission number").strip()
                submitted = st.form_submit_button("Enter Feedback Portal ➡️", type="primary", use_container_width=True)
                
                if submitted:
                    if not admission_no:
                        st.error("Please enter your admission number.")
                    else:
                        success, msg, data = authenticate_student(active_session["id"], admission_no)
                        if success:
                            st.session_state.student_user = data
                            # Fetch assigned cards
                            cards = get_student_assigned_cards(active_session["id"], data["id"])
                            st.session_state.student_cards = cards
                            st.session_state.completed_cards = get_completed_card_ids(active_session["id"], data["id"])
                            st.session_state.active_card_idx = 0
                            st.session_state.submission_done = False
                            st.rerun()
                        else:
                            st.error(msg)
                            
        with col2:
            st.markdown("""
            ### 🛡️ Student Privacy Notice
            - **No Identity Linking:** Your ratings are recorded anonymously. Teachers and staff will never see which student gave which score.
            - **Single Submission:** Once all subject cards are finalized, your admission number is locked to prevent duplication.
            - **Direct Feedback:** Provide honest and constructive ratings to help improve teaching quality.
            """)
            
    if st.button("⬅️ Back to Main Menu"):
        st.switch_page("app.py")
    st.stop()

# --- Post-Login Feedback Flow ---
student = st.session_state.student_user
cards = st.session_state.student_cards

# Student Header Bar
head_col1, head_col2, head_col3 = st.columns([3, 2, 1])
with head_col1:
    st.markdown(f"### 👋 Welcome, **{student['student_name']}**")
    st.markdown(f"**Class:** {student['class_level']}-{student['section']} | **Stream:** {student.get('stream', 'General')} | **Adm No:** `{student['admission_number']}`")
with head_col2:
    total_cards = len(cards)
    completed_count = len(st.session_state.completed_cards)
    progress_val = (completed_count / total_cards) if total_cards > 0 else 1.0
    st.progress(progress_val, text=f"Progress: {completed_count} of {total_cards} subjects completed")
with head_col3:
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.student_user = None
        st.session_state.student_cards = []
        st.session_state.completed_cards = set()
        st.session_state.active_card_idx = 0
        st.session_state.submission_done = False
        st.rerun()

st.divider()

if not cards:
    st.info("ℹ️ No teacher-subject feedback cards are currently assigned to your class and section. Please check back later.")
    st.stop()

# Check if final submission already completed in this session
if st.session_state.submission_done:
    st.balloons()
    st.success("🎉 All feedback submitted successfully! Thank you for participating in the school evaluation.")
    st.markdown("""
    Your responses have been securely and anonymously recorded.  
    You may now close this window or log out.
    """)
    if st.button("Return to Home Screen"):
        st.session_state.student_user = None
        st.switch_page("app.py")
    st.stop()

# Subject Cards Navigation Bar
st.markdown("#### Your Assigned Subjects:")
card_cols = st.columns(len(cards))
for i, c in enumerate(cards):
    is_done = c["mapping_id"] in st.session_state.completed_cards
    is_current = i == st.session_state.active_card_idx
    badge = "✅" if is_done else ("👉" if is_current else "⏳")
    btn_type = "primary" if is_current else "secondary"
    with card_cols[i]:
        label = f"{badge} {c['subject']}\n({c['teacher_name'].split()[-1]})"
        if st.button(label, key=f"nav_card_{i}", use_container_width=True, type=btn_type):
            st.session_state.active_card_idx = i
            st.rerun()

st.write("")

# Display Active Card
active_card = cards[st.session_state.active_card_idx]
is_card_completed = active_card["mapping_id"] in st.session_state.completed_cards

st.markdown(f"""
<div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; padding: 1.2rem; border-radius: 10px; margin-bottom: 1.5rem;">
    <h3 style="color: #1E3A8A; margin-top: 0; margin-bottom: 0.3rem;">Subject: {active_card['subject']}</h3>
    <p style="font-size: 1.05rem; color: #334155; margin-bottom: 0;">
        👨‍🏫 <strong>Teacher:</strong> {active_card['teacher_name']} &nbsp;|&nbsp; 
        🏷️ <strong>Department:</strong> {active_card['department']} &nbsp;|&nbsp;
        🏫 <strong>Class:</strong> {active_card['class_level']}-{active_card['section']}
    </p>
</div>
""", unsafe_allow_html=True)

if is_card_completed:
    st.success(f"✅ Feedback for **{active_card['subject']} ({active_card['teacher_name']})** has already been saved and locked.")
    st.caption("Per evaluation rules, submitted subject cards cannot be modified.")
    
    # Next button or final submission
    all_done = len(st.session_state.completed_cards) == len(cards)
    if not all_done:
        # Find next uncompleted card
        next_idx = None
        for idx, c in enumerate(cards):
            if c["mapping_id"] not in st.session_state.completed_cards:
                next_idx = idx
                break
        if next_idx is not None and st.button(f"Go to next pending subject ➡️ ({cards[next_idx]['subject']})", type="primary"):
            st.session_state.active_card_idx = next_idx
            st.rerun()
    else:
        st.markdown("---")
        st.markdown("### 🏁 Ready for Final Submission")
        st.info("You have answered questions for all your assigned subjects! Click below to complete your evaluation.")
        if st.button("🚀 Final Submit All Evaluations", type="primary", use_container_width=True):
            success, message = finalize_student_submission(active_session["id"], student["id"])
            if success:
                st.session_state.submission_done = True
                st.rerun()
            else:
                st.error(message)
else:
    # Display evaluation questionnaire for this card
    questions = active_card["questions"]
    if not questions:
        st.warning("No questions configured for this subject evaluation.")
    else:
        st.markdown("##### Please rate the following statements honestly (1 = Poor, 5 = Excellent):")
        
        with st.form(f"feedback_card_form_{active_card['mapping_id']}"):
            user_ratings = {}
            from questionnaire_service import QUESTION_SCALES
            
            for q in questions:
                st.markdown(f"**Q{q['id']}. {q['text']}**")
                q_type = q.get("type", "scale_1_5")
                scale_info = QUESTION_SCALES.get(q_type, QUESTION_SCALES["scale_1_5"])
                labels = q.get("labels", scale_info["labels"])
                values = scale_info.get("values", [float(i + 1) for i in range(len(labels))])
                
                choice_idx = st.radio(
                    f"Rating for Q{q['id']}",
                    options=list(range(len(labels))),
                    format_func=lambda i: labels[i],
                    index=len(labels) // 2,
                    horizontal=True,
                    key=f"q_{active_card['mapping_id']}_{q['id']}",
                    label_visibility="collapsed"
                )
                
                val = values[choice_idx] if choice_idx < len(values) else float(choice_idx + 1)
                user_ratings[q['id']] = {
                    "question_id": q["id"],
                    "question_text": q["text"],
                    "rating_value": float(val),
                    "choice_label": labels[choice_idx]
                }
                st.write("")
                
            save_btn = st.form_submit_button(
                label=f"💾 Save & Move to Next Subject ➡️",
                type="primary",
                use_container_width=True
            )
            
            if save_btn:
                answers_list = list(user_ratings.values())
                success, msg = save_card_responses(
                    session_id=active_session["id"],
                    student_id=student["id"],
                    mapping_id=active_card["mapping_id"],
                    answers=answers_list
                )
                if success:
                    st.session_state.completed_cards.add(active_card["mapping_id"])
                    
                    # Check if all cards completed
                    if len(st.session_state.completed_cards) == len(cards):
                        st.session_state.active_card_idx = 0
                    else:
                        # Advance to next uncompleted card
                        for idx, c in enumerate(cards):
                            if c["mapping_id"] not in st.session_state.completed_cards:
                                st.session_state.active_card_idx = idx
                                break
                    st.rerun()
                else:
                    st.error(f"Error saving responses: {msg}")
