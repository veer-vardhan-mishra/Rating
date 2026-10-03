import os
import sys
from pathlib import Path
from datetime import date, datetime, timedelta
import random
import pandas as pd

# Add parent directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import (
    init_db, get_db_session, AcademicSession, Student, Teacher,
    TeacherSubjectMapping, MappingStudent, QuestionnaireTemplate,
    MappingQuestionnaire, FeedbackResponse, SubmissionRecord, CardSubmission
)
from questionnaire_service import seed_default_questionnaires
from session_service import create_session, set_active_session, launch_poll

SAMPLE_STUDENTS = [
    # Class 6-A
    ("ADM-6001", "Aarav Sharma", 6, "A", "General", "1"),
    ("ADM-6002", "Ananya Patel", 6, "A", "General", "2"),
    ("ADM-6003", "Rohan Gupta", 6, "A", "General", "3"),
    ("ADM-6004", "Diya Mukherjee", 6, "A", "General", "4"),
    ("ADM-6005", "Ishaan Verma", 6, "A", "General", "5"),
    ("ADM-6006", "Saanvi Iyer", 6, "A", "General", "6"),
    ("ADM-6007", "Kabir Reddy", 6, "A", "General", "7"),
    ("ADM-6008", "Meera Joshi", 6, "A", "General", "8"),
    
    # Class 6-B
    ("ADM-6101", "Aryan Singh", 6, "B", "General", "1"),
    ("ADM-6102", "Tanvi Bhatia", 6, "B", "General", "2"),
    ("ADM-6103", "Aditya Nair", 6, "B", "General", "3"),
    ("ADM-6104", "Pari Saxena", 6, "B", "General", "4"),
    ("ADM-6105", "Vivaan Chopra", 6, "B", "General", "5"),
    ("ADM-6106", "Anika Deshmukh", 6, "B", "General", "6"),
    
    # Class 11-A (Science)
    ("ADM-1101", "Devansh Sen", 11, "A", "Science", "1"),
    ("ADM-1102", "Rhea Kapoor", 11, "A", "Science", "2"),
    ("ADM-1103", "Kunal Roy", 11, "A", "Science", "3"),
    ("ADM-1104", "Avni Jain", 11, "A", "Science", "4"),
    ("ADM-1105", "Shaurya Das", 11, "A", "Science", "5"),
    ("ADM-1106", "Navya Pillai", 11, "A", "Science", "6"),
    
    # Class 12-A (Commerce)
    ("ADM-1201", "Pranav Mittal", 12, "A", "Commerce", "1"),
    ("ADM-1202", "Siya Agarwal", 12, "A", "Commerce", "2"),
    ("ADM-1203", "Harsh Singhania", 12, "A", "Commerce", "3"),
    ("ADM-1204", "Tara Sethi", 12, "A", "Commerce", "4"),
    ("ADM-1205", "Yash Khandelwal", 12, "A", "Commerce", "5"),
]

SAMPLE_TEACHERS = [
    ("TCH-001", "Dr. Veer Malhotra", "9876543210", date(1985, 4, 12), "Science", "Science, Physics", "veer.malhotra@school.edu"),
    ("TCH-002", "Mrs. Sunita Verma", "9812345678", date(1988, 8, 25), "Mathematics", "Mathematics", "sunita.verma@school.edu"),
    ("TCH-003", "Mr. Rajesh Khanna", "9823456789", date(1982, 11, 5), "Languages", "English", "rajesh.khanna@school.edu"),
    ("TCH-004", "Coach Vikram Rana", "9834567890", date(1991, 2, 18), "Sports", "Physical Education", "vikram.rana@school.edu"),
    ("TCH-005", "Ms. Neha Singhal", "9845678901", date(1993, 7, 30), "Computer Science", "Computer Science, AI", "neha.singhal@school.edu"),
    ("TCH-006", "Mr. Arvind Swamy", "9856789012", date(1980, 1, 15), "Social Sciences", "Social Studies, History", "arvind.swamy@school.edu"),
]

def generate_sample_excel_files(out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Students Excel
    df_st = pd.DataFrame([
        {
            "admission_number": s[0],
            "student_name": s[1],
            "class": s[2],
            "section": s[3],
            "stream": s[4],
            "roll_number": s[5]
        }
        for s in SAMPLE_STUDENTS
    ])
    df_st.to_excel(out_dir / "sample_students.xlsx", index=False)
    
    # Teachers Excel
    df_tch = pd.DataFrame([
        {
            "teacher_id": t[0],
            "teacher_name": t[1],
            "phone_number": t[2],
            "date_of_birth": t[3].strftime("%Y-%m-%d"),
            "department": t[4],
            "subjects_taught": t[5],
            "email": t[6]
        }
        for t in SAMPLE_TEACHERS
    ])
    df_tch.to_excel(out_dir / "sample_teachers.xlsx", index=False)
    print(f"Generated sample Excel files in {out_dir}")

def seed_complete_demo_data():
    """Seeds a full realistic session with students, teachers, mappings, and responses."""
    init_db()
    with get_db_session() as db:
        # Check if 2026-27 session already exists
        sess = db.query(AcademicSession).filter_by(name="2026-27").first()
        if not sess:
            sess = AcademicSession(
                name="2026-27",
                start_date=date(2026, 4, 1),
                end_date=date(2027, 3, 31),
                status="LIVE",
                is_active=True
            )
            db.add(sess)
            db.flush()
            session_id = sess.id
        else:
            session_id = sess.id
            sess.status = "LIVE"
            sess.is_active = True

        # Default Questionnaires
        seed_default_questionnaires(session_id, db=db)
        academic_q = db.query(QuestionnaireTemplate).filter_by(session_id=session_id, category="Academic").first()
        sports_q = db.query(QuestionnaireTemplate).filter_by(session_id=session_id, category="Sports").first()

        # Add Teachers
        teachers_map = {}
        for t in SAMPLE_TEACHERS:
            existing = db.query(Teacher).filter_by(session_id=session_id, teacher_id=t[0]).first()
            if not existing:
                teacher = Teacher(
                    session_id=session_id,
                    teacher_id=t[0],
                    teacher_name=t[1],
                    phone_number=t[2],
                    date_of_birth=t[3],
                    department=t[4],
                    subjects_taught=t[5],
                    email=t[6]
                )
                db.add(teacher)
                db.flush()
                teachers_map[t[0]] = teacher
            else:
                teachers_map[t[0]] = existing

        # Add Students
        students_map = {}
        for s in SAMPLE_STUDENTS:
            existing = db.query(Student).filter_by(session_id=session_id, admission_number=s[0]).first()
            if not existing:
                st = Student(
                    session_id=session_id,
                    admission_number=s[0],
                    student_name=s[1],
                    class_level=s[2],
                    section=s[3],
                    stream=s[4],
                    roll_number=s[5]
                )
                db.add(st)
                db.flush()
                students_map[s[0]] = st
            else:
                students_map[s[0]] = existing

        # Create Mappings for Class 6-A
        st_6a = [s for s in students_map.values() if s.class_level == 6 and s.section == "A"]
        
        mappings_to_create = [
            (teachers_map["TCH-001"], 6, "A", "Science", "General", st_6a, academic_q),
            (teachers_map["TCH-002"], 6, "A", "Mathematics", "General", st_6a, academic_q),
            (teachers_map["TCH-003"], 6, "A", "English", "General", st_6a, academic_q),
            (teachers_map["TCH-004"], 6, "A", "Physical Education", "General", st_6a, sports_q),
            (teachers_map["TCH-005"], 6, "A", "Computer Science", "General", st_6a, academic_q),
            (teachers_map["TCH-006"], 6, "A", "Social Studies", "General", st_6a, academic_q),
        ]
        
        # Mappings for Class 6-B
        st_6b = [s for s in students_map.values() if s.class_level == 6 and s.section == "B"]
        mappings_to_create.extend([
            (teachers_map["TCH-001"], 6, "B", "Science", "General", st_6b, academic_q),
            (teachers_map["TCH-002"], 6, "B", "Mathematics", "General", st_6b, academic_q),
            (teachers_map["TCH-004"], 6, "B", "Physical Education", "General", st_6b, sports_q),
        ])

        created_mappings = []
        for tch, cl, sec, subj, strm, st_list, q_tmpl in mappings_to_create:
            m = db.query(TeacherSubjectMapping).filter_by(
                session_id=session_id,
                teacher_id=tch.id,
                class_level=cl,
                section=sec,
                subject=subj
            ).first()
            if not m:
                m = TeacherSubjectMapping(
                    session_id=session_id,
                    teacher_id=tch.id,
                    class_level=cl,
                    section=sec,
                    subject=subj,
                    stream=strm
                )
                db.add(m)
                db.flush()
                for st in st_list:
                    db.add(MappingStudent(mapping_id=m.id, student_id=st.id))
                if q_tmpl:
                    db.add(MappingQuestionnaire(mapping_id=m.id, questionnaire_id=q_tmpl.id))
            created_mappings.append((m, q_tmpl, st_list))

        # Seed realistic feedback responses for some students (e.g. 5 students in 6A)
        # to test k-anonymity, charts, and student completion locks
        voting_students = st_6a[:6]
        for st in voting_students:
            sub = db.query(SubmissionRecord).filter_by(session_id=session_id, student_id=st.id).first()
            if not sub:
                db.add(SubmissionRecord(session_id=session_id, student_id=st.id, is_complete=True, submitted_at=datetime.utcnow() - timedelta(hours=random.randint(1, 48))))
                
        # Seed anonymous feedback responses
        for m, q_tmpl, st_list in created_mappings:
            if m.class_level == 6 and m.section == "A":
                for st in voting_students:
                    card_submission = db.query(CardSubmission).filter_by(
                        session_id=session_id, student_id=st.id, mapping_id=m.id
                    ).first()
                    if not card_submission:
                        db.add(CardSubmission(
                            session_id=session_id,
                            student_id=st.id,
                            mapping_id=m.id
                        ))

                existing_resp = db.query(FeedbackResponse).filter_by(mapping_id=m.id).count()
                if existing_resp == 0:
                    # Add 6 realistic responses for each question
                    for _ in range(6):
                        for q_id in range(1, 6):
                            # Realistic score 3.5 to 5.0
                            val = random.choice([4.0, 5.0, 4.0, 5.0, 3.0, 5.0])
                            db.add(FeedbackResponse(
                                session_id=session_id,
                                mapping_id=m.id,
                                question_id=q_id,
                                question_text=f"Question {q_id}",
                                rating_value=val,
                                submitted_at=datetime.utcnow()
                            ))

    print("Complete demo session seeded successfully!")

if __name__ == "__main__":
    out = Path(__file__).resolve().parent
    generate_sample_excel_files(out)
    seed_complete_demo_data()
