from datetime import datetime, date
import hashlib
import json
from typing import List, Optional, Tuple, Dict
from database import (
    get_db_session, AcademicSession, Student, Teacher, TeacherSubjectMapping,
    QuestionnaireTemplate, FeedbackResponse, PollClosure, AuditLog
)

def create_session(name: str, start_date: date, end_date: date, is_active: bool = False) -> Tuple[bool, str, Optional[AcademicSession]]:
    name = name.strip()
    if not name:
        return False, "Session name is required.", None
    if start_date > end_date:
        return False, "Session start date must be on or before its end date.", None
    with get_db_session() as db:
        existing = db.query(AcademicSession).filter_by(name=name).first()
        if existing:
            return False, f"A session with name '{name}' already exists.", None
            
        if is_active:
            db.query(AcademicSession).update({"is_active": False})
            
        new_session = AcademicSession(
            name=name,
            start_date=start_date,
            end_date=end_date,
            status="DRAFT",
            is_active=is_active
        )
        db.add(new_session)
        db.flush()
        
        # Log action
        log = AuditLog(
            session_id=new_session.id,
            actor="Admin",
            action="CREATE_SESSION",
            details=f"Created academic session '{name}' ({start_date} to {end_date})"
        )
        db.add(log)
        
        session_id = new_session.id
        return True, "Session created successfully.", session_id

def get_all_sessions() -> List[Dict]:
    with get_db_session() as db:
        sessions = db.query(AcademicSession).order_by(AcademicSession.id.desc()).all()
        result = []
        for s in sessions:
            st_count = db.query(Student).filter_by(session_id=s.id).count()
            tch_count = db.query(Teacher).filter_by(session_id=s.id).count()
            resp_count = db.query(FeedbackResponse).filter_by(session_id=s.id).count()
            result.append({
                "id": s.id,
                "name": s.name,
                "start_date": s.start_date,
                "end_date": s.end_date,
                "status": s.status,
                "is_active": s.is_active,
                "student_count": st_count,
                "teacher_count": tch_count,
                "response_count": resp_count,
                "created_at": s.created_at
            })
        return result

def get_active_session() -> Optional[Dict]:
    with get_db_session() as db:
        s = db.query(AcademicSession).filter_by(is_active=True).first()
        if not s:
            # Fallback to latest session if none explicitly set as active
            s = db.query(AcademicSession).order_by(AcademicSession.id.desc()).first()
        if not s:
            return None
            
        st_count = db.query(Student).filter_by(session_id=s.id).count()
        tch_count = db.query(Teacher).filter_by(session_id=s.id).count()
        resp_count = db.query(FeedbackResponse).filter_by(session_id=s.id).count()
        return {
            "id": s.id,
            "name": s.name,
            "start_date": s.start_date,
            "end_date": s.end_date,
            "status": s.status,
            "is_active": s.is_active,
            "student_count": st_count,
            "teacher_count": tch_count,
            "response_count": resp_count
        }

def set_active_session(session_id: int) -> bool:
    with get_db_session() as db:
        db.query(AcademicSession).update({"is_active": False})
        sess = db.query(AcademicSession).filter_by(id=session_id).first()
        if sess:
            sess.is_active = True
            log = AuditLog(
                session_id=session_id,
                actor="Admin",
                action="SWITCH_ACTIVE_SESSION",
                details=f"Active session changed to '{sess.name}'"
            )
            db.add(log)
            return True
        return False

def validate_prelaunch(session_id: int) -> Tuple[bool, List[str]]:
    """Checks checklist before launching poll."""
    errors = []
    with get_db_session() as db:
        st_count = db.query(Student).filter_by(session_id=session_id).count()
        if st_count == 0:
            errors.append("No students imported in this session.")
            
        tch_count = db.query(Teacher).filter_by(session_id=session_id).count()
        if tch_count == 0:
            errors.append("No teachers imported in this session.")
            
        map_count = db.query(TeacherSubjectMapping).filter_by(session_id=session_id).count()
        if map_count == 0:
            errors.append("No teacher-subject mappings configured.")
            
        q_count = db.query(QuestionnaireTemplate).filter_by(session_id=session_id).count()
        if q_count == 0:
            errors.append("No questionnaires created for this session.")
            
    return len(errors) == 0, errors

def launch_poll(session_id: int) -> Tuple[bool, str]:
    with get_db_session() as db:
        sess = db.query(AcademicSession).filter_by(id=session_id).first()
        if not sess:
            return False, "Session not found."
        if sess.status == "CLOSED" or db.query(PollClosure).filter_by(session_id=session_id).first():
            return False, "Cannot reopen a finalized and closed poll session."
        if sess.status != "DRAFT":
            return False, "Only draft sessions can be launched."

    is_valid, errors = validate_prelaunch(session_id)
    if not is_valid:
        return False, "Cannot launch poll: " + " | ".join(errors)
        
    with get_db_session() as db:
        sess = db.query(AcademicSession).filter_by(id=session_id).first()
        if not sess:
            return False, "Session not found."
        if sess.status == "CLOSED" or db.query(PollClosure).filter_by(session_id=session_id).first():
            return False, "Cannot reopen a finalized and closed poll session."
        if sess.status != "DRAFT":
            return False, "Only draft sessions can be launched."
        if db.query(PollClosure).filter_by(session_id=session_id).first():
            return False, "Cannot reopen a finalized and closed poll session."
            
        sess.status = "LIVE"
        log = AuditLog(
            session_id=session_id,
            actor="Admin",
            action="LAUNCH_POLL",
            details=f"Feedback poll launched and marked LIVE for session '{sess.name}'"
        )
        db.add(log)
        return True, "Feedback poll is now LIVE. Students can submit ratings."

def close_poll(session_id: int, admin_name: str = "Admin") -> Tuple[bool, str, Optional[str]]:
    """
    Closes the poll and computes a cryptographic SHA-256 integrity hash snapshot
    of all responses. Responses become strictly immutable.
    """
    with get_db_session() as db:
        sess = db.query(AcademicSession).filter_by(id=session_id).first()
        if not sess:
            return False, "Session not found.", None
        if sess.status != "LIVE" or db.query(PollClosure).filter_by(session_id=session_id).first():
            return False, "Poll is already closed.", None
            
        responses = db.query(FeedbackResponse).filter_by(session_id=session_id).order_by(FeedbackResponse.id.asc()).all()
        
        # Serialize response records deterministically for hash computation
        data_to_hash = []
        for r in responses:
            data_to_hash.append({
                "id": r.id,
                "mapping_id": r.mapping_id,
                "question_id": r.question_id,
                "rating": r.rating_value,
                "time": r.submitted_at.isoformat()
            })
            
        serialized = json.dumps(data_to_hash, sort_keys=True)
        closure_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        
        sess.status = "CLOSED"
        closure_record = PollClosure(
            session_id=session_id,
            closed_by=admin_name,
            closure_hash=closure_hash,
            total_responses=len(responses)
        )
        db.add(closure_record)
        
        log = AuditLog(
            session_id=session_id,
            actor=admin_name,
            action="CLOSE_POLL",
            details=f"Poll closed and sealed. {len(responses)} responses captured. SHA-256: {closure_hash[:16]}..."
        )
        db.add(log)
        
        return True, f"Poll successfully closed and sealed with {len(responses)} responses.", closure_hash

def get_closure_info(session_id: int) -> Optional[Dict]:
    with get_db_session() as db:
        closure = db.query(PollClosure).filter_by(session_id=session_id).first()
        if not closure:
            return None
        return {
            "closed_by": closure.closed_by,
            "closed_at": closure.closed_at,
            "closure_hash": closure.closure_hash,
            "total_responses": closure.total_responses
        }
