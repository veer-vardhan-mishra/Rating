import pytest
from datetime import date
from database import (
    init_db, get_db_session, AcademicSession, TeacherSubjectMapping,
    QuestionnaireTemplate, MappingStudent
)
from session_service import (
    create_session, get_all_sessions, set_active_session,
    validate_prelaunch, launch_poll, close_poll, get_closure_info
)
from questionnaire_service import seed_default_questionnaires
from mapping_service import create_or_update_mapping, delete_mapping
from questionnaire_service import (
    create_questionnaire, update_questionnaire, duplicate_questionnaire,
    assign_questionnaire_to_teachers, assign_questionnaire_to_mapping,
    delete_questionnaire
)
from import_export_service import import_students_from_file

@pytest.fixture(autouse=True)
def setup_db():
    init_db()

def test_session_creation_and_lifecycle():
    # Create new session
    success, msg, sid = create_session("2028-29-Test", date(2028, 4, 1), date(2029, 3, 31), is_active=False)
    assert success is True
    assert sid is not None
    
    # Try launching without data -> prelaunch validation should fail
    is_valid, errors = validate_prelaunch(sid)
    assert is_valid is False
    assert len(errors) > 0
    
    # Attempting to launch should return error
    success, msg = launch_poll(sid)
    assert success is False
    assert "Cannot launch" in msg

def test_poll_closure_and_tamper_evidence():
    with get_db_session() as db:
        sess = db.query(AcademicSession).filter_by(status="LIVE").first()
        assert sess is not None
        
        # Close poll
        success, msg, chash = close_poll(sess.id, "TestAdmin")
        assert success is True
        assert len(chash) == 64 # SHA-256 length
        
        # Verify closure info
        c_info = get_closure_info(sess.id)
        assert c_info is not None
        assert c_info["closure_hash"] == chash
        assert c_info["closed_by"] == "TestAdmin"
        
        # Verify poll status is CLOSED
        db.refresh(sess)
        assert sess.status == "CLOSED"
        
        # Try to launch again -> prohibited
        success, msg = launch_poll(sess.id)
        assert success is False
        assert "Cannot reopen" in msg


def test_live_poll_configuration_is_locked():
    with get_db_session() as db:
        sess = db.query(AcademicSession).filter_by(name="2026-27").first()
        mapping = db.query(TeacherSubjectMapping).filter_by(session_id=sess.id).first()
        questionnaire = db.query(QuestionnaireTemplate).filter_by(session_id=sess.id).first()
        student_ids = [
            row.student_id
            for row in db.query(MappingStudent).filter_by(mapping_id=mapping.id).all()
        ]

        success, _, mapping_id = create_or_update_mapping(
            sess.id, mapping.teacher_id, mapping.class_level, mapping.section,
            "Locked Test Subject", student_ids
        )
        assert success is False
        assert mapping_id is None
        assert delete_mapping(mapping.id) is False

        success, _, questionnaire_id = create_questionnaire(
            sess.id, "Locked Template", "Academic", []
        )
        assert success is False
        assert questionnaire_id is None
        assert update_questionnaire(
            questionnaire.id, questionnaire.name, questionnaire.category, []
        )[0] is False
        assert duplicate_questionnaire(questionnaire.id, "Locked Copy")[0] is False
        assert assign_questionnaire_to_teachers(questionnaire.id, [mapping.teacher_id]) is False
        assert assign_questionnaire_to_mapping(mapping.id, questionnaire.id) is False
        assert delete_questionnaire(questionnaire.id)[0] is False

        csv_data = b"admission_number,student_name,class,section\nLOCK-1,Locked Student,6,A\n"
        success, _, report = import_students_from_file(sess.id, csv_data, "locked.csv")
        assert success is False
        assert report["imported"] == 0
