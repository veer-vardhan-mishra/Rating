import streamlit as st
from config import Config
from database import init_db
from session_service import get_active_session, get_closure_info

# Initialize database schema and default admin
init_db()

st.set_page_config(
    page_title="School Teacher Feedback System",
    page_icon="🏫",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .role-card {
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid #E5E7EB;
        background-color: #FFFFFF;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        transition: transform 0.2s, box-shadow 0.2s;
        text-align: center;
        min-height: 260px;
    }
    .role-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
    }
    .status-badge {
        display: inline-block;
        padding: 0.35rem 0.8rem;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .status-live {
        background-color: #DEF7EC;
        color: #03543F;
        border: 1px solid #31C48D;
    }
    .status-draft {
        background-color: #FEF08A;
        color: #713F12;
        border: 1px solid #EAB308;
    }
    .status-closed {
        background-color: #FEE2E2;
        color: #991B1B;
        border: 1px solid #F87171;
    }
</style>
""", unsafe_allow_html=True)

# App Header
st.markdown('<div class="main-header">🏫 School Teacher Feedback & Evaluation System</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">A secure, reusable, and privacy-preserving platform for student ratings and teacher performance analytics.</div>', unsafe_allow_html=True)

# Active Session Status Banner
active_session = get_active_session()

if active_session:
    status = active_session["status"]
    status_class = "status-live" if status == "LIVE" else ("status-closed" if status == "CLOSED" else "status-draft")
    status_icon = "🟢" if status == "LIVE" else ("🔴" if status == "CLOSED" else "🟡")
    
    col_stat1, col_stat2, col_stat3, col_stat4 = st.columns([3, 2, 2, 2])
    with col_stat1:
        st.markdown(f"**Current Academic Session:** `{active_session['name']}` ({active_session['start_date']} to {active_session['end_date']})")
    with col_stat2:
        st.markdown(f'<span class="status-badge {status_class}">{status_icon} Poll Status: {status}</span>', unsafe_allow_html=True)
    with col_stat3:
        st.markdown(f"👥 **Enrolled Students:** {active_session['student_count']}")
    with col_stat4:
        st.markdown(f"📊 **Responses Collected:** {active_session['response_count']}")
else:
    st.warning("⚠️ No active academic session found. Please log in as Administrator to create or activate a session.")

st.divider()

# Portal Selection
st.subheader("Select Your Portal")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    <div class="role-card">
        <h2 style="font-size: 2.5rem; margin-bottom: 0.5rem;">🎓</h2>
        <h3 style="color: #1F2937; margin-bottom: 0.5rem;">Student Feedback</h3>
        <p style="color: #6B7280; font-size: 0.95rem; margin-bottom: 1.5rem;">
            Log in with your admission number to submit anonymous evaluations for your assigned subject teachers.
        </p>
    </div>
    """, unsafe_allow_html=True)
    st.write("")
    if st.button("Open Student Feedback Portal ➡️", use_container_width=True, type="primary", key="btn_student"):
        st.switch_page("pages/1_🎓_Student_Feedback.py")

with col2:
    st.markdown("""
    <div class="role-card">
        <h2 style="font-size: 2.5rem; margin-bottom: 0.5rem;">👨‍🏫</h2>
        <h3 style="color: #1F2937; margin-bottom: 0.5rem;">Teacher Analytics</h3>
        <p style="color: #6B7280; font-size: 0.95rem; margin-bottom: 1.5rem;">
            Authenticate with Teacher ID, Phone, and DOB to inspect aggregated performance reports and class ratings.
        </p>
    </div>
    """, unsafe_allow_html=True)
    st.write("")
    if st.button("Open Teacher Portal ➡️", use_container_width=True, key="btn_teacher"):
        st.switch_page("pages/2_👨‍🏫_Teacher_Portal.py")

with col3:
    st.markdown("""
    <div class="role-card">
        <h2 style="font-size: 2.5rem; margin-bottom: 0.5rem;">🔐</h2>
        <h3 style="color: #1F2937; margin-bottom: 0.5rem;">Admin Control Center</h3>
        <p style="color: #6B7280; font-size: 0.95rem; margin-bottom: 1.5rem;">
            Manage academic sessions, Excel data imports, subject mappings, questionnaire forms, and exports.
        </p>
    </div>
    """, unsafe_allow_html=True)
    st.write("")
    if st.button("Open Admin Dashboard ➡️", use_container_width=True, key="btn_admin"):
        st.switch_page("pages/3_🔐_Admin_Dashboard.py")

st.divider()

# Privacy, Integrity & Operational Notice
st.subheader("🛡️ Privacy & Security Guarantees")
sec_col1, sec_col2, sec_col3 = st.columns(3)

with sec_col1:
    st.markdown("""
    **🔒 Strict Anonymity Architecture**
    - Feedback responses are decoupled from student identities.
    - No student admission number or name is recorded in response records.
    - Teachers and peers cannot link ratings to any individual student.
    """)

with sec_col2:
    st.markdown("""
    **🛡️ K-Anonymity Suppression**
    - Detailed class question averages are suppressed for groups with fewer than 5 responses.
    - Prevents statistical deduction or reverse-identification in small groups.
    """)

with sec_col3:
    st.markdown("""
    **🔏 Cryptographic Tamper-Evidence**
    - When an administrator closes a poll, a SHA-256 fingerprint snapshot of all responses is sealed.
    - Once closed, ratings become strictly read-only and immutable.
    """)

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #9CA3AF; font-size: 0.85rem;'>"
    "School Teacher Feedback & Evaluation System v1.2 | Deployable on School LAN/Intranet"
    "</div>",
    unsafe_allow_html=True
)
