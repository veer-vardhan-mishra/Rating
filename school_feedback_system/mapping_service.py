from typing import List, Dict, Optional, Tuple
from database import (
    get_db_session, TeacherSubjectMapping, MappingStudent,
    Student, Teacher, QuestionnaireTemplate, MappingQuestionnaire,
    AcademicSession
)
import json

def get_students_for_class_section(session_id: int, class_level: int, section: str, stream: Optional[str] = None) -> List[Dict]:
    with get_db_session() as db:
        query = db.query(Student).filter_by(
            session_id=session_id,
            class_level=class_level,
            section=section
        )
        if stream and stream != "All":
            query = query.filter_by(stream=stream)
            
        students = query.order_by(Student.roll_number.asc(), Student.student_name.asc()).all()
        return [
            {
                "id": s.id,
                "admission_number": s.admission_number,
                "name": s.student_name,
                "roll_number": s.roll_number or "",
                "stream": s.stream or ""
            }
            for s in students
        ]

def create_or_update_mapping(
    session_id: int,
    teacher_id: int,
    class_level: int,
    section: str,
    subject: str,
    student_ids: List[int],
    stream: Optional[str] = None,
    questionnaire_id: Optional[int] = None
) -> Tuple[bool, str, Optional[int]]:
    with get_db_session() as db:
        session = db.query(AcademicSession).filter_by(id=session_id).first()
        if not session or session.status != "DRAFT":
            return False, "Mappings are locked after poll launch.", None

        # Check if identical mapping exists
        mapping = db.query(TeacherSubjectMapping).filter_by(
            session_id=session_id,
            teacher_id=teacher_id,
            class_level=class_level,
            section=section,
            subject=subject
        ).first()
        
        if not mapping:
            mapping = TeacherSubjectMapping(
                session_id=session_id,
                teacher_id=teacher_id,
                class_level=class_level,
                section=section,
                subject=subject,
                stream=stream
            )
            db.add(mapping)
            db.flush()
        else:
            mapping.stream = stream
            
        # Update student associations
        db.query(MappingStudent).filter_by(mapping_id=mapping.id).delete()
        for sid in student_ids:
            ms = MappingStudent(mapping_id=mapping.id, student_id=sid)
            db.add(ms)
            
        # Link questionnaire if provided
        if questionnaire_id:
            db.query(MappingQuestionnaire).filter_by(mapping_id=mapping.id).delete()
            mq = MappingQuestionnaire(mapping_id=mapping.id, questionnaire_id=questionnaire_id)
            db.add(mq)
        else:
            # Check if default questionnaire exists for session
            default_q = db.query(QuestionnaireTemplate).filter_by(session_id=session_id).first()
            if default_q:
                existing_link = db.query(MappingQuestionnaire).filter_by(mapping_id=mapping.id).first()
                if not existing_link:
                    db.add(MappingQuestionnaire(mapping_id=mapping.id, questionnaire_id=default_q.id))
                    
        return True, f"Mapping saved for Class {class_level}-{section} ({subject}) with {len(student_ids)} students.", mapping.id

def get_mappings_for_session(session_id: int) -> List[Dict]:
    with get_db_session() as db:
        mappings = db.query(TeacherSubjectMapping).filter_by(session_id=session_id).all()
        results = []
        for m in mappings:
            student_count = db.query(MappingStudent).filter_by(mapping_id=m.id).count()
            teacher = db.query(Teacher).filter_by(id=m.teacher_id).first()
            q_link = db.query(MappingQuestionnaire).filter_by(mapping_id=m.id).first()
            q_name = "Default"
            if q_link:
                q = db.query(QuestionnaireTemplate).filter_by(id=q_link.questionnaire_id).first()
                if q:
                    q_name = q.name
                    
            results.append({
                "id": m.id,
                "teacher_id": m.teacher_id,
                "teacher_code": teacher.teacher_id if teacher else "N/A",
                "teacher_name": teacher.teacher_name if teacher else "Unknown",
                "department": teacher.department if teacher else "Academic",
                "class_level": m.class_level,
                "section": m.section,
                "subject": m.subject,
                "stream": m.stream or "",
                "student_count": student_count,
                "questionnaire_name": q_name
            })
        return results

def get_student_assigned_cards(session_id: int, student_id: int) -> List[Dict]:
    """
    Returns all teacher-subject cards that this student is eligible to rate.
    Includes questions snapshot from assigned questionnaire template.
    """
    with get_db_session() as db:
        mapping_ids = [
            ms.mapping_id for ms in db.query(MappingStudent).filter_by(student_id=student_id).all()
        ]
        
        cards = []
        for mid in mapping_ids:
            mapping = db.query(TeacherSubjectMapping).filter_by(id=mid, session_id=session_id).first()
            if not mapping:
                continue
                
            teacher = db.query(Teacher).filter_by(id=mapping.teacher_id).first()
            
            # Find questionnaire
            q_link = db.query(MappingQuestionnaire).filter_by(mapping_id=mapping.id).first()
            questionnaire = None
            if q_link:
                questionnaire = db.query(QuestionnaireTemplate).filter_by(id=q_link.questionnaire_id).first()
            if not questionnaire and teacher:
                # 1. Check if a questionnaire is targeted directly to this teacher
                all_q = db.query(QuestionnaireTemplate).filter_by(session_id=session_id).all()
                for q_candidate in all_q:
                    if getattr(q_candidate, "target_type", "") == "TEACHER" and q_candidate.target_teacher_ids:
                        try:
                            t_ids = json.loads(q_candidate.target_teacher_ids)
                            if teacher.id in t_ids:
                                questionnaire = q_candidate
                                break
                        except Exception:
                            pass
                # 2. Check department match
                if not questionnaire and teacher.department:
                    questionnaire = db.query(QuestionnaireTemplate).filter_by(session_id=session_id, category=teacher.department).first()
            # 3. Fallback to default session questionnaire
            if not questionnaire:
                questionnaire = db.query(QuestionnaireTemplate).filter_by(session_id=session_id).first()
                    
            questions = []
            if questionnaire and questionnaire.questions_json:
                try:
                    questions = json.loads(questionnaire.questions_json)
                except Exception:
                    questions = []
                    
            cards.append({
                "mapping_id": mapping.id,
                "teacher_id": teacher.id if teacher else 0,
                "teacher_name": teacher.teacher_name if teacher else "Teacher",
                "department": teacher.department if teacher else "Academic",
                "subject": mapping.subject,
                "class_level": mapping.class_level,
                "section": mapping.section,
                "questionnaire_id": questionnaire.id if questionnaire else None,
                "questions": questions
            })
        return cards

def delete_mapping(mapping_id: int) -> bool:
    with get_db_session() as db:
        m = db.query(TeacherSubjectMapping).filter_by(id=mapping_id).first()
        if m:
            session = db.query(AcademicSession).filter_by(id=m.session_id).first()
            if not session or session.status != "DRAFT":
                return False
            db.delete(m)
            return True
        return False
