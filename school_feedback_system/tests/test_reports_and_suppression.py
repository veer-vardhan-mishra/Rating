import pytest
from database import init_db, get_db_session, AcademicSession, Teacher
from report_service import get_teacher_report, get_admin_school_overview, get_school_report_matrix, get_teacher_comparisons

@pytest.fixture(autouse=True)
def setup_db():
    init_db()

def test_reports_and_k_anonymity_suppression():
    with get_db_session() as db:
        sess = db.query(AcademicSession).filter_by(name="2026-27").first()
        assert sess is not None
        
        # Test Admin Overview
        overview = get_admin_school_overview(sess.id)
        assert overview["total_students"] > 0
        assert overview["total_teachers"] > 0
        assert overview["total_responses"] > 0
        assert overview["school_avg"] > 0
        
        # Test School Report Matrix
        matrix_df = get_school_report_matrix(sess.id)
        assert not matrix_df.empty
        assert "Class" in matrix_df.columns
        assert "Section" in matrix_df.columns
        assert "Teacher" in matrix_df.columns
        assert "Subject" in matrix_df.columns
        assert "Overall Avg" in matrix_df.columns
        
        # Test Teacher Report & K-Anonymity
        teacher = db.query(Teacher).filter_by(session_id=sess.id, teacher_id="TCH-001").first()
        assert teacher is not None
        
        t_rep = get_teacher_report(sess.id, teacher.id, min_threshold=5)
        assert t_rep["total_responses"] > 0
        assert t_rep["overall_average"] > 0
        
        # Class 6-A had 6 responses -> should NOT be suppressed
        c6a = next((c for c in t_rep["classes"] if c["class_level"] == 6 and c["section"] == "A"), None)
        assert c6a is not None
        assert c6a["response_count"] == 6
        assert c6a["is_suppressed"] is False
        assert c6a["class_average"] is not None
        
        # Class 6-B had 0 responses -> should be suppressed or empty
        c6b = next((c for c in t_rep["classes"] if c["class_level"] == 6 and c["section"] == "B"), None)
        assert c6b is not None
        assert c6b["response_count"] < 5
        assert c6b["is_suppressed"] is True
        assert c6b["class_average"] is None
