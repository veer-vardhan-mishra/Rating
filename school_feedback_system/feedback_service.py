from datetime import datetime
from typing import List, Dict, Tuple
from sqlalchemy.exc import IntegrityError
from database import (
    get_db_session, AcademicSession, FeedbackResponse, SubmissionRecord,
    CardSubmission, MappingStudent, Student, TeacherSubjectMapping
)

def save_card_responses(
    session_id: int,
    student_id: int,
    mapping_id: int,
    answers: List[Dict]
) -> Tuple[bool, str]:
    """
    Saves feedback responses for one teacher-subject card.
    PRIVACY: NO student ID or admission number is stored with the response!
    """
    if not answers:
        return False, "Cannot save an empty feedback card."

    try:
        with get_db_session() as db:
            sess = db.query(AcademicSession).filter_by(id=session_id).first()
            if not sess or sess.status != "LIVE":
                return False, "Cannot submit feedback: Poll is not active."

            student = db.query(Student).filter_by(id=student_id, session_id=session_id).first()
            mapping = db.query(TeacherSubjectMapping).filter_by(id=mapping_id, session_id=session_id).first()
            assigned = db.query(MappingStudent).filter_by(
                mapping_id=mapping_id, student_id=student_id
            ).first()
            if not student or not mapping or not assigned:
                return False, "This feedback card is not assigned to this student."

            existing = db.query(CardSubmission).filter_by(
                session_id=session_id, student_id=student_id, mapping_id=mapping_id
            ).first()
            if existing:
                return False, "This feedback card has already been submitted."

            question_ids = [answer.get("question_id") for answer in answers]
            if any(question_id is None for question_id in question_ids) or len(set(question_ids)) != len(question_ids):
                return False, "Feedback answers contain missing or duplicate questions."

            db.add(CardSubmission(
                session_id=session_id,
                student_id=student_id,
                mapping_id=mapping_id
            ))
            for answer in answers:
                try:
                    rating_value = float(answer["rating_value"])
                except (KeyError, TypeError, ValueError):
                    return False, "Feedback answer has an invalid rating."
                if not 1 <= rating_value <= 5:
                    return False, "Feedback rating must be between 1 and 5."
                db.add(FeedbackResponse(
                    session_id=session_id,
                    mapping_id=mapping_id,
                    question_id=answer["question_id"],
                    question_text=answer.get("question_text", ""),
                    rating_value=rating_value,
                    choice_label=answer.get("choice_label", "")
                ))

        return True, "Card response saved successfully."
    except IntegrityError:
        return False, "This feedback card has already been submitted."


def get_completed_card_ids(session_id: int, student_id: int) -> set:
    with get_db_session() as db:
        return {
            row.mapping_id
            for row in db.query(CardSubmission.mapping_id).filter_by(
                session_id=session_id, student_id=student_id
            ).all()
        }

def finalize_student_submission(session_id: int, student_id: int) -> Tuple[bool, str]:
    """
    Marks the student's submission as complete in the submission registry.
    Locks the student from ever submitting or editing again for this session.
    """
    with get_db_session() as db:
        sess = db.query(AcademicSession).filter_by(id=session_id).first()
        if not sess or sess.status != "LIVE":
            return False, "Cannot finalize submission: Poll is closed or inactive."

        assigned_mapping_ids = {
            row.mapping_id
            for row in db.query(MappingStudent.mapping_id).join(
                TeacherSubjectMapping, TeacherSubjectMapping.id == MappingStudent.mapping_id
            ).filter(
                MappingStudent.student_id == student_id,
                TeacherSubjectMapping.session_id == session_id
            ).all()
        }
        if not assigned_mapping_ids:
            return False, "Cannot finalize submission: No feedback cards are assigned."

        completed_mapping_ids = {
            row.mapping_id
            for row in db.query(CardSubmission.mapping_id).filter_by(
                session_id=session_id, student_id=student_id
            ).all()
        }
        if completed_mapping_ids != assigned_mapping_ids:
            return False, "Cannot finalize submission: Complete every assigned feedback card first."
            
        record = db.query(SubmissionRecord).filter_by(
            session_id=session_id,
            student_id=student_id
        ).first()
        
        if record and record.is_complete:
            return False, "Feedback has already been submitted and locked for this admission number."
            
        if not record:
            record = SubmissionRecord(
                session_id=session_id,
                student_id=student_id,
                is_complete=True,
                submitted_at=datetime.utcnow()
            )
            db.add(record)
        else:
            record.is_complete = True
            record.submitted_at = datetime.utcnow()
            
        return True, "All feedback records successfully finalized."

def is_student_submitted(session_id: int, student_id: int) -> bool:
    with get_db_session() as db:
        record = db.query(SubmissionRecord).filter_by(
            session_id=session_id,
            student_id=student_id
        ).first()
        return bool(record and record.is_complete)
