from datetime import datetime, date
from contextlib import contextmanager
import json
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, DateTime, Date, Boolean,
    ForeignKey, Float, UniqueConstraint, Index, event, text
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, Session
import bcrypt
from config import Config

Base = declarative_base()

# Configure engine
connect_args = {}
if Config.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False, "timeout": 60}

engine = create_engine(
    Config.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True
)

# Enable WAL mode for SQLite to maximize concurrent read/write throughput
if Config.DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@contextmanager
def get_db_session():
    db: Session = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


class AcademicSession(Base):
    __tablename__ = "academic_sessions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False) # e.g. "2026-27"
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    status = Column(String(20), default="DRAFT", nullable=False) # DRAFT, LIVE, CLOSED
    is_active = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    students = relationship("Student", back_populates="session", cascade="all, delete-orphan")
    teachers = relationship("Teacher", back_populates="session", cascade="all, delete-orphan")
    mappings = relationship("TeacherSubjectMapping", back_populates="session", cascade="all, delete-orphan")
    questionnaires = relationship("QuestionnaireTemplate", back_populates="session", cascade="all, delete-orphan")
    submissions = relationship("SubmissionRecord", back_populates="session", cascade="all, delete-orphan")
    responses = relationship("FeedbackResponse", back_populates="session", cascade="all, delete-orphan")


class Student(Base):
    __tablename__ = "students"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("academic_sessions.id", ondelete="CASCADE"), nullable=False)
    admission_number = Column(String(50), nullable=False)
    student_name = Column(String(200), nullable=False)
    class_level = Column(Integer, nullable=False) # 6 to 12
    section = Column(String(10), nullable=False)   # A, B, C...
    stream = Column(String(50), nullable=True)     # Science, Commerce, Humanities...
    roll_number = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    session = relationship("AcademicSession", back_populates="students")
    mappings = relationship("TeacherSubjectMapping", secondary="mapping_students", back_populates="students")
    submission = relationship("SubmissionRecord", back_populates="student", uselist=False, cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint("session_id", "admission_number", name="uq_session_admission"),
        Index("ix_student_lookup", "session_id", "admission_number"),
        Index("ix_student_class_sec", "session_id", "class_level", "section"),
    )


class Teacher(Base):
    __tablename__ = "teachers"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("academic_sessions.id", ondelete="CASCADE"), nullable=False)
    teacher_id = Column(String(50), nullable=False)
    teacher_name = Column(String(200), nullable=False)
    phone_number = Column(String(20), nullable=False) # For teacher authentication
    date_of_birth = Column(Date, nullable=False)       # For teacher authentication
    email = Column(String(200), nullable=True)
    department = Column(String(100), default="Academic") # e.g. Academic, Sports, Science
    subjects_taught = Column(String(255), nullable=True) # e.g. "Science, Physics"
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    session = relationship("AcademicSession", back_populates="teachers")
    mappings = relationship("TeacherSubjectMapping", back_populates="teacher", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint("session_id", "teacher_id", name="uq_session_teacher_id"),
        Index("ix_teacher_auth", "session_id", "teacher_id"),
    )


class TeacherSubjectMapping(Base):
    __tablename__ = "teacher_subject_mappings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("academic_sessions.id", ondelete="CASCADE"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False)
    class_level = Column(Integer, nullable=False)
    section = Column(String(10), nullable=False)
    subject = Column(String(100), nullable=False)
    stream = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    session = relationship("AcademicSession", back_populates="mappings")
    teacher = relationship("Teacher", back_populates="mappings")
    students = relationship("Student", secondary="mapping_students", back_populates="mappings")
    responses = relationship("FeedbackResponse", back_populates="mapping", cascade="all, delete-orphan")
    questionnaire_link = relationship("MappingQuestionnaire", back_populates="mapping", uselist=False, cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("ix_mapping_lookup", "session_id", "class_level", "section", "subject"),
    )


class MappingStudent(Base):
    __tablename__ = "mapping_students"
    
    mapping_id = Column(Integer, ForeignKey("teacher_subject_mappings.id", ondelete="CASCADE"), primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), primary_key=True)


class QuestionnaireTemplate(Base):
    __tablename__ = "questionnaire_templates"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("academic_sessions.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
    category = Column(String(100), default="All") # "All", "Academic", "Sports", etc.
    description = Column(Text, nullable=True) # Guidance / instructions for students
    target_type = Column(String(50), default="ALL") # "ALL", "TEACHER", "DEPARTMENT"
    target_teacher_ids = Column(Text, nullable=True) # JSON list of teacher IDs e.g. [1, 2]
    questions_json = Column(Text, nullable=False) # JSON array of questions
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    session = relationship("AcademicSession", back_populates="questionnaires")
    mappings = relationship("MappingQuestionnaire", back_populates="questionnaire")


class MappingQuestionnaire(Base):
    __tablename__ = "mapping_questionnaires"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    mapping_id = Column(Integer, ForeignKey("teacher_subject_mappings.id", ondelete="CASCADE"), nullable=False, unique=True)
    questionnaire_id = Column(Integer, ForeignKey("questionnaire_templates.id", ondelete="CASCADE"), nullable=False)
    
    mapping = relationship("TeacherSubjectMapping", back_populates="questionnaire_link")
    questionnaire = relationship("QuestionnaireTemplate", back_populates="mappings")


class SubmissionRecord(Base):
    """
    Tracks which student completed feedback to prevent duplicate voting.
    DOES NOT CONTAIN ANY ANSWERS OR RATINGS (Student Anonymity Guarantee).
    """
    __tablename__ = "submission_records"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("academic_sessions.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    is_complete = Column(Boolean, default=False, nullable=False)
    submitted_at = Column(DateTime, nullable=True)
    
    session = relationship("AcademicSession", back_populates="submissions")
    student = relationship("Student", back_populates="submission")
    
    __table_args__ = (
        UniqueConstraint("session_id", "student_id", name="uq_submission_student_session"),
    )


class CardSubmission(Base):
    """Tracks finalized cards without linking students to their answer rows."""
    __tablename__ = "card_submissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("academic_sessions.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    mapping_id = Column(Integer, ForeignKey("teacher_subject_mappings.id", ondelete="CASCADE"), nullable=False)
    submitted_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("session_id", "student_id", "mapping_id", name="uq_student_mapping_submission"),
    )


class FeedbackResponse(Base):
    """
    Anonymized feedback ratings.
    Notice: NO student_id or admission_number is stored here!
    """
    __tablename__ = "feedback_responses"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("academic_sessions.id", ondelete="CASCADE"), nullable=False)
    mapping_id = Column(Integer, ForeignKey("teacher_subject_mappings.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, nullable=False)
    question_text = Column(String(300), nullable=False)
    rating_value = Column(Float, nullable=False) # e.g. 1.0 to 5.0
    choice_label = Column(String(100), nullable=True)
    submitted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    session = relationship("AcademicSession", back_populates="responses")
    mapping = relationship("TeacherSubjectMapping", back_populates="responses")
    
    __table_args__ = (
        Index("ix_response_mapping_q", "mapping_id", "question_id"),
        Index("ix_response_session", "session_id"),
    )


class AdminUser(Base):
    __tablename__ = "admin_users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(200), default="Administrator")
    email = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, nullable=True)
    actor = Column(String(100), nullable=False)
    action = Column(String(100), nullable=False)
    details = Column(Text, nullable=True)
    ip_address = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PollClosure(Base):
    __tablename__ = "poll_closures"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, unique=True, nullable=False)
    closed_by = Column(String(100), nullable=False)
    closed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    closure_hash = Column(String(64), nullable=False) # SHA-256 fingerprint
    total_responses = Column(Integer, default=0, nullable=False)


def init_db():
    Base.metadata.create_all(bind=engine)
    
    # Safe schema migration for newly added columns if table already exists
    with engine.connect() as conn:
        for col_name, col_type in [
            ("description", "TEXT"),
            ("target_type", "VARCHAR(50) DEFAULT 'ALL'"),
            ("target_teacher_ids", "TEXT")
        ]:
            try:
                conn.execute(text(f"ALTER TABLE questionnaire_templates ADD COLUMN {col_name} {col_type}"))
                conn.commit()
            except Exception:
                pass # Column already exists
    
    # Initialize default admin if not exists
    with get_db_session() as db:
        admin = db.query(AdminUser).filter_by(username=Config.DEFAULT_ADMIN_USERNAME).first()
        if not admin:
            salt = bcrypt.gensalt()
            hashed = bcrypt.hashpw(Config.DEFAULT_ADMIN_PASSWORD.encode("utf-8"), salt).decode("utf-8")
            admin = AdminUser(
                username=Config.DEFAULT_ADMIN_USERNAME,
                password_hash=hashed,
                full_name="System Administrator"
            )
            db.add(admin)
            log = AuditLog(
                actor="System",
                action="INITIALIZE_ADMIN",
                details="Default admin account provisioned."
            )
            db.add(log)
