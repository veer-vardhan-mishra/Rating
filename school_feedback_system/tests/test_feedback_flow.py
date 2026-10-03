import pytest
from uuid import uuid4
from database import init_db, get_db_session, AcademicSession, Student, FeedbackResponse, SubmissionRecord
from database import MappingStudent
from mapping_service import get_student_assigned_cards
from feedback_service import (
    save_card_responses, finalize_student_submission, is_student_submitted,
    get_completed_card_ids
)

@pytest.fixture(autouse=True)
def setup_db():
    init_db()

def test_feedback_card_assignment_and_anonymous_response():
    with get_db_session() as db:
        # Re-open or use active session
        sess = db.query(AcademicSession).filter_by(name="2026-27").first()
        sess.status = "LIVE"
        db.commit()
        
        # Get student Kabir Reddy (ADM-6007)
        st = db.query(Student).filter_by(session_id=sess.id, admission_number="ADM-6007").first()
        assert st is not None
        
        # Check student has assigned cards
        cards = get_student_assigned_cards(sess.id, st.id)
        assert len(cards) > 0

        # Use a fresh student so the test is independent of seeded completion data.
        test_student = Student(
            session_id=sess.id,
            admission_number=f"ADM-FLOW-{uuid4().hex}",
            student_name="Feedback Flow Test",
            class_level=st.class_level,
            section=st.section,
            stream=st.stream
        )
        db.add(test_student)
        db.flush()
        for card in cards:
            db.add(MappingStudent(mapping_id=card["mapping_id"], student_id=test_student.id))
        db.commit()
        st = test_student
        
        card = cards[0]
        mapping_id = card["mapping_id"]
        
        # Submit answers for this card
        answers = [
            {"question_id": 1, "question_text": "Q1", "rating_value": 5.0, "choice_label": "5 - Excellent"},
            {"question_id": 2, "question_text": "Q2", "rating_value": 4.0, "choice_label": "4 - Very Good"}
        ]
        
        success, msg = save_card_responses(sess.id, st.id, mapping_id, answers)
        assert success is True
        
        # Verify anonymous storage: Check response row in DB
        resp = db.query(FeedbackResponse).filter_by(session_id=sess.id, mapping_id=mapping_id, question_id=1).first()
        assert resp is not None
        # Assert response table has NO student_id or admission_number column
        assert not hasattr(resp, "student_id")
        assert not hasattr(resp, "admission_number")

        assert mapping_id in get_completed_card_ids(sess.id, st.id)
        duplicate_success, _ = save_card_responses(sess.id, st.id, mapping_id, answers)
        assert duplicate_success is False

        other_student = db.query(Student).filter_by(
            session_id=sess.id, admission_number="ADM-6101"
        ).first()
        if other_student:
            unauthorized_success, _ = save_card_responses(sess.id, other_student.id, mapping_id, answers)
            assert unauthorized_success is False
        
        # Finalization is blocked until every assigned card has been saved.
        assert not is_student_submitted(sess.id, st.id)
        success, msg = finalize_student_submission(sess.id, st.id)
        assert success is False
        assert "every assigned" in msg

        remaining_cards = [c for c in get_student_assigned_cards(sess.id, st.id) if c["mapping_id"] != mapping_id]
        for remaining_card in remaining_cards:
            success, msg = save_card_responses(
                sess.id,
                st.id,
                remaining_card["mapping_id"],
                [{"question_id": 1, "question_text": "Q1", "rating_value": 4.0}]
            )
            assert success is True

        success, msg = finalize_student_submission(sess.id, st.id)
        assert success is True
        assert is_student_submitted(sess.id, st.id)
        
        # Attempting duplicate finalization fails
        dup_success, dup_msg = finalize_student_submission(sess.id, st.id)
        assert dup_success is False
        assert "already been submitted" in dup_msg
