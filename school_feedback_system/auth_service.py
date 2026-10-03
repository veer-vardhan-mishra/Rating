from datetime import datetime, date, timedelta
from typing import Optional, Tuple, Dict
import bcrypt
from database import get_db_session, AdminUser, Teacher, Student, AcademicSession, SubmissionRecord, AuditLog
from config import Config

# In-memory rate limiting tracker: {key: [timestamps]}
_rate_limit_cache: Dict[str, list] = {}

def _check_rate_limit(key: str) -> bool:
    """Returns True if allowed, False if rate limit exceeded."""
    now = datetime.utcnow()
    window_start = now - timedelta(seconds=Config.RATE_LIMIT_WINDOW_SECONDS)
    
    attempts = _rate_limit_cache.get(key, [])
    # Filter attempts within window
    attempts = [t for t in attempts if t > window_start]
    if len(attempts) >= Config.RATE_LIMIT_MAX_ATTEMPTS:
        _rate_limit_cache[key] = attempts
        return False
    attempts.append(now)
    _rate_limit_cache[key] = attempts
    return True

def _reset_rate_limit(key: str):
    if key in _rate_limit_cache:
        del _rate_limit_cache[key]

# --- Admin Authentication ---
def authenticate_admin(username: str, password: str, client_ip: str = "127.0.0.1") -> Tuple[bool, str, Optional[AdminUser]]:
    key = f"admin_{client_ip}"
    if not _check_rate_limit(key):
        return False, "Too many login attempts. Please wait 5 minutes before retrying.", None
        
    with get_db_session() as db:
        admin = db.query(AdminUser).filter_by(username=username.strip()).first()
        if not admin:
            return False, "Invalid username or password.", None
            
        if not bcrypt.checkpw(password.encode("utf-8"), admin.password_hash.encode("utf-8")):
            return False, "Invalid username or password.", None
            
        _reset_rate_limit(key)
        # Detach object attributes
        admin_data = {
            "id": admin.id,
            "username": admin.username,
            "full_name": admin.full_name,
            "email": admin.email
        }
        
        log = AuditLog(
            actor=f"Admin:{admin.username}",
            action="LOGIN_SUCCESS",
            details="Admin logged in successfully",
            ip_address=client_ip
        )
        db.add(log)
        return True, "Login successful", admin_data

# --- Teacher Authentication ---
def authenticate_teacher(session_id: int, teacher_id: str, phone: str, dob: date, client_ip: str = "127.0.0.1") -> Tuple[bool, str, Optional[dict]]:
    clean_tid = teacher_id.strip()
    clean_phone = phone.strip().replace(" ", "").replace("-", "")
    key = f"teacher_{clean_tid}_{client_ip}"
    
    if not _check_rate_limit(key):
        return False, "Too many failed attempts. Please wait 5 minutes before trying again.", None
        
    with get_db_session() as db:
        teacher = db.query(Teacher).filter_by(session_id=session_id, teacher_id=clean_tid).first()
        if not teacher:
            # Generic response to prevent enumeration
            return False, "Invalid Teacher ID, Phone Number, or Date of Birth.", None
            
        db_phone = teacher.phone_number.strip().replace(" ", "").replace("-", "")
        if db_phone != clean_phone or teacher.date_of_birth != dob:
            return False, "Invalid Teacher ID, Phone Number, or Date of Birth.", None
            
        _reset_rate_limit(key)
        teacher_info = {
            "id": teacher.id,
            "teacher_id": teacher.teacher_id,
            "teacher_name": teacher.teacher_name,
            "department": teacher.department,
            "session_id": teacher.session_id
        }
        return True, "Authentication successful", teacher_info

# --- Student Authentication ---
def authenticate_student(session_id: int, admission_number: str, client_ip: str = "127.0.0.1") -> Tuple[bool, str, Optional[dict]]:
    clean_adm = admission_number.strip()
    key = f"student_{client_ip}"
    generic_error = "Unable to access feedback. Check your admission number or contact the school administrator."
    
    if not _check_rate_limit(key):
        return False, "Too many submission attempts. Please wait 5 minutes before retrying.", None
        
    with get_db_session() as db:
        # Check active session status
        session = db.query(AcademicSession).filter_by(id=session_id).first()
        if not session or session.status != "LIVE":
            return False, generic_error, None
            
        student = db.query(Student).filter_by(session_id=session_id, admission_number=clean_adm).first()
        if not student:
            return False, generic_error, None
            
        # Check if already submitted
        submission = db.query(SubmissionRecord).filter_by(session_id=session_id, student_id=student.id).first()
        if submission and submission.is_complete:
            return False, generic_error, None
            
        _reset_rate_limit(key)
        student_info = {
            "id": student.id,
            "admission_number": student.admission_number,
            "student_name": student.student_name,
            "class_level": student.class_level,
            "section": student.section,
            "stream": student.stream,
            "session_id": session_id
        }
        return True, "Login successful", student_info
