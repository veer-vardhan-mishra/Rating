import pytest
from datetime import date
from database import init_db, get_db_session, AcademicSession, Student, Teacher
from auth_service import authenticate_admin, authenticate_teacher, authenticate_student, _check_rate_limit, _reset_rate_limit

@pytest.fixture(autouse=True)
def setup_db():
    init_db()

def test_admin_authentication():
    # Success
    success, msg, data = authenticate_admin("admin", "admin123")
    assert success is True
    assert data["username"] == "admin"
    
    # Wrong password
    success, msg, data = authenticate_admin("admin", "wrongpass")
    assert success is False
    assert "Invalid" in msg

def test_teacher_authentication():
    with get_db_session() as db:
        sess = db.query(AcademicSession).first()
        assert sess is not None
        
        # Test authenticating Dr. Veer Malhotra
        success, msg, data = authenticate_teacher(sess.id, "TCH-001", "9876543210", date(1985, 4, 12))
        assert success is True
        assert data["teacher_name"] == "Dr. Veer Malhotra"
        
        # Wrong phone
        success, msg, data = authenticate_teacher(sess.id, "TCH-001", "0000000000", date(1985, 4, 12))
        assert success is False

def test_student_authentication_and_duplicate():
    with get_db_session() as db:
        sess = db.query(AcademicSession).filter_by(status="LIVE").first()
        assert sess is not None
        
        # ADM-6001 (already voted in demo seed)
        success, msg, data = authenticate_student(sess.id, "ADM-6001")
        assert success is False
        assert msg == "Unable to access feedback. Check your admission number or contact the school administrator."
        assert data is None
        
        # ADM-6007 (has not submitted yet)
        success, msg, data = authenticate_student(sess.id, "ADM-6007")
        assert success is True
        assert data["student_name"] == "Kabir Reddy"

        invalid_success, invalid_msg, invalid_data = authenticate_student(sess.id, "NOT-A-STUDENT")
        assert invalid_success is False
        assert invalid_msg == "Unable to access feedback. Check your admission number or contact the school administrator."
        assert invalid_data is None
