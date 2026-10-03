import json
from typing import List, Dict, Optional, Tuple
from database import (
    get_db_session, QuestionnaireTemplate, MappingQuestionnaire, TeacherSubjectMapping,
    Teacher, AcademicSession
)

# Standard Rating Scales Definition
QUESTION_SCALES = {
    "scale_1_5": {
        "name": "1 to 5 Stars / Numeric Scale",
        "labels": ["1 - Poor", "2 - Fair", "3 - Good", "4 - Very Good", "5 - Excellent"],
        "values": [1.0, 2.0, 3.0, 4.0, 5.0],
        "default": 3.0
    },
    "scale_3": {
        "name": "3-Point Evaluation Scale",
        "labels": ["Needs Improvement", "Satisfactory", "Exemplary"],
        "values": [1.0, 3.0, 5.0],
        "default": 3.0
    },
    "agreement_5": {
        "name": "5-Point Agreement Scale",
        "labels": ["Strongly Disagree", "Disagree", "Neutral", "Agree", "Strongly Agree"],
        "values": [1.0, 2.0, 3.0, 4.0, 5.0],
        "default": 3.0
    },
    "yes_no": {
        "name": "Yes / Needs Attention / No",
        "labels": ["No", "Needs Attention", "Yes"],
        "values": [1.0, 3.0, 5.0],
        "default": 5.0
    }
}

DEFAULT_ACADEMIC_QUESTIONS = [
    {
        "id": 1,
        "text": "Explains subject concepts clearly and uses understandable examples.",
        "type": "scale_1_5",
        "labels": ["1 - Poor", "2 - Fair", "3 - Good", "4 - Very Good", "5 - Excellent"]
    },
    {
        "id": 2,
        "text": "Maintains discipline, punctuality, and encourages student participation in class.",
        "type": "scale_1_5",
        "labels": ["1 - Poor", "2 - Fair", "3 - Good", "4 - Very Good", "5 - Excellent"]
    },
    {
        "id": 3,
        "text": "Is approachable, patient, and helps in clearing student doubts.",
        "type": "scale_1_5",
        "labels": ["1 - Poor", "2 - Fair", "3 - Good", "4 - Very Good", "5 - Excellent"]
    },
    {
        "id": 4,
        "text": "Provides regular feedback, evaluations, and guidance on homework/tests.",
        "type": "scale_1_5",
        "labels": ["1 - Poor", "2 - Fair", "3 - Good", "4 - Very Good", "5 - Excellent"]
    },
    {
        "id": 5,
        "text": "Inspires interest in the subject and supports students' overall development.",
        "type": "scale_1_5",
        "labels": ["1 - Poor", "2 - Fair", "3 - Good", "4 - Very Good", "5 - Excellent"]
    }
]

DEFAULT_SPORTS_QUESTIONS = [
    {
        "id": 1,
        "text": "Provides clear instructions on sports techniques, rules, and fitness exercises.",
        "type": "scale_1_5",
        "labels": ["1 - Poor", "2 - Fair", "3 - Good", "4 - Very Good", "5 - Excellent"]
    },
    {
        "id": 2,
        "text": "Promotes sportsmanship, teamwork, safety, and positive discipline during games.",
        "type": "scale_1_5",
        "labels": ["1 - Poor", "2 - Fair", "3 - Good", "4 - Very Good", "5 - Excellent"]
    },
    {
        "id": 3,
        "text": "Encourages and motivates every student to participate actively regardless of skill level.",
        "type": "scale_1_5",
        "labels": ["1 - Poor", "2 - Fair", "3 - Good", "4 - Very Good", "5 - Excellent"]
    },
    {
        "id": 4,
        "text": "Ensures proper warm-up, safety measures, and sports equipment handling.",
        "type": "scale_1_5",
        "labels": ["1 - Poor", "2 - Fair", "3 - Good", "4 - Very Good", "5 - Excellent"]
    }
]

def seed_default_questionnaires(session_id: int, db=None):
    """Creates default Academic and Sports questionnaire templates if none exist."""
    def _seed(session):
        academic_session = session.query(AcademicSession).filter_by(id=session_id).first()
        if not academic_session or academic_session.status != "DRAFT":
            return
        existing = session.query(QuestionnaireTemplate).filter_by(session_id=session_id).first()
        if not existing:
            academic_q = QuestionnaireTemplate(
                session_id=session_id,
                name="General Academic Evaluation",
                category="Academic",
                description="Standard evaluation questions for subject teachers.",
                target_type="ALL",
                target_teacher_ids=json.dumps([]),
                questions_json=json.dumps(DEFAULT_ACADEMIC_QUESTIONS)
            )
            sports_q = QuestionnaireTemplate(
                session_id=session_id,
                name="Physical Education & Sports Evaluation",
                category="Sports",
                description="Evaluation questions specifically for physical education teachers and sports coaches.",
                target_type="DEPARTMENT",
                target_teacher_ids=json.dumps([]),
                questions_json=json.dumps(DEFAULT_SPORTS_QUESTIONS)
            )
            session.add(academic_q)
            session.add(sports_q)

    if db is not None:
        _seed(db)
    else:
        with get_db_session() as s:
            _seed(s)

def create_questionnaire(
    session_id: int,
    name: str,
    category: str,
    questions: List[Dict],
    target_type: str = "ALL",
    target_teacher_ids: Optional[List[int]] = None,
    description: str = ""
) -> Tuple[bool, str, Optional[int]]:
    """
    Creates a new questionnaire.
    If target_type is 'TEACHER' and target_teacher_ids are given, automatically
    binds any active mappings of those teachers to this new questionnaire!
    """
    teacher_ids = target_teacher_ids or []
    with get_db_session() as db:
        academic_session = db.query(AcademicSession).filter_by(id=session_id).first()
        if not academic_session or academic_session.status != "DRAFT":
            return False, "Questionnaires are locked after poll launch.", None

        q = QuestionnaireTemplate(
            session_id=session_id,
            name=name.strip(),
            category=category.strip(),
            description=description.strip(),
            target_type=target_type,
            target_teacher_ids=json.dumps(teacher_ids),
            questions_json=json.dumps(questions)
        )
        db.add(q)
        db.flush()
        
        # If assigned directly to teachers, update their mappings
        if target_type == "TEACHER" and teacher_ids:
            mappings = db.query(TeacherSubjectMapping).filter(
                TeacherSubjectMapping.session_id == session_id,
                TeacherSubjectMapping.teacher_id.in_(teacher_ids)
            ).all()
            for m in mappings:
                db.query(MappingQuestionnaire).filter_by(mapping_id=m.id).delete()
                db.add(MappingQuestionnaire(mapping_id=m.id, questionnaire_id=q.id))
                
        return True, "Questionnaire template created successfully.", q.id

def update_questionnaire(
    questionnaire_id: int,
    name: str,
    category: str,
    questions: List[Dict],
    target_type: str = "ALL",
    target_teacher_ids: Optional[List[int]] = None,
    description: str = ""
) -> Tuple[bool, str]:
    teacher_ids = target_teacher_ids or []
    with get_db_session() as db:
        q = db.query(QuestionnaireTemplate).filter_by(id=questionnaire_id).first()
        if not q:
            return False, "Questionnaire not found."
        academic_session = db.query(AcademicSession).filter_by(id=q.session_id).first()
        if not academic_session or academic_session.status != "DRAFT":
            return False, "Questionnaires are locked after poll launch."
            
        q.name = name.strip()
        q.category = category.strip()
        q.description = description.strip()
        q.target_type = target_type
        q.target_teacher_ids = json.dumps(teacher_ids)
        q.questions_json = json.dumps(questions)
        
        # If assigned directly to teachers, update their mappings
        if target_type == "TEACHER" and teacher_ids:
            mappings = db.query(TeacherSubjectMapping).filter(
                TeacherSubjectMapping.session_id == q.session_id,
                TeacherSubjectMapping.teacher_id.in_(teacher_ids)
            ).all()
            for m in mappings:
                db.query(MappingQuestionnaire).filter_by(mapping_id=m.id).delete()
                db.add(MappingQuestionnaire(mapping_id=m.id, questionnaire_id=q.id))
                
        return True, "Questionnaire updated successfully."

def duplicate_questionnaire(questionnaire_id: int, new_name: str) -> Tuple[bool, str, Optional[int]]:
    with get_db_session() as db:
        q = db.query(QuestionnaireTemplate).filter_by(id=questionnaire_id).first()
        if not q:
            return False, "Original questionnaire not found.", None
        academic_session = db.query(AcademicSession).filter_by(id=q.session_id).first()
        if not academic_session or academic_session.status != "DRAFT":
            return False, "Questionnaires are locked after poll launch.", None
            
        new_q = QuestionnaireTemplate(
            session_id=q.session_id,
            name=new_name.strip(),
            category=q.category,
            description=q.description or "",
            target_type="ALL",
            target_teacher_ids=json.dumps([]),
            questions_json=q.questions_json
        )
        db.add(new_q)
        db.flush()
        return True, f"Cloned successfully as '{new_name}'.", new_q.id

def assign_questionnaire_to_teachers(questionnaire_id: int, teacher_ids: List[int]) -> bool:
    """Assigns questionnaire directly to a list of teachers."""
    with get_db_session() as db:
        q = db.query(QuestionnaireTemplate).filter_by(id=questionnaire_id).first()
        if not q:
            return False
        academic_session = db.query(AcademicSession).filter_by(id=q.session_id).first()
        if not academic_session or academic_session.status != "DRAFT":
            return False
            
        q.target_type = "TEACHER"
        q.target_teacher_ids = json.dumps(teacher_ids)
        
        mappings = db.query(TeacherSubjectMapping).filter(
            TeacherSubjectMapping.session_id == q.session_id,
            TeacherSubjectMapping.teacher_id.in_(teacher_ids)
        ).all()
        for m in mappings:
            db.query(MappingQuestionnaire).filter_by(mapping_id=m.id).delete()
            db.add(MappingQuestionnaire(mapping_id=m.id, questionnaire_id=q.id))
        return True

def get_questionnaires_for_session(session_id: int) -> List[Dict]:
    with get_db_session() as db:
        qs = db.query(QuestionnaireTemplate).filter_by(session_id=session_id).order_by(QuestionnaireTemplate.id.asc()).all()
        result = []
        for q in qs:
            questions = []
            try:
                questions = json.loads(q.questions_json)
            except Exception:
                pass
                
            teacher_ids = []
            if getattr(q, "target_teacher_ids", None):
                try:
                    teacher_ids = json.loads(q.target_teacher_ids)
                except Exception:
                    teacher_ids = []
                    
            # Get teacher names if targeted
            teacher_names = []
            if teacher_ids:
                tchs = db.query(Teacher).filter(Teacher.id.in_(teacher_ids)).all()
                teacher_names = [t.teacher_name for t in tchs]
                
            result.append({
                "id": q.id,
                "name": q.name,
                "category": q.category,
                "description": getattr(q, "description", "") or "",
                "target_type": getattr(q, "target_type", "ALL") or "ALL",
                "target_teacher_ids": teacher_ids,
                "teacher_names": teacher_names,
                "question_count": len(questions),
                "questions": questions,
                "created_at": q.created_at
            })
        return result

def get_questionnaire_by_id(questionnaire_id: int) -> Optional[Dict]:
    with get_db_session() as db:
        q = db.query(QuestionnaireTemplate).filter_by(id=questionnaire_id).first()
        if not q:
            return None
        questions = []
        try:
            questions = json.loads(q.questions_json)
        except Exception:
            pass
            
        teacher_ids = []
        if getattr(q, "target_teacher_ids", None):
            try:
                teacher_ids = json.loads(q.target_teacher_ids)
            except Exception:
                pass
                
        return {
            "id": q.id,
            "session_id": q.session_id,
            "name": q.name,
            "category": q.category,
            "description": getattr(q, "description", "") or "",
            "target_type": getattr(q, "target_type", "ALL") or "ALL",
            "target_teacher_ids": teacher_ids,
            "questions": questions
        }

def assign_questionnaire_to_mapping(mapping_id: int, questionnaire_id: int) -> bool:
    with get_db_session() as db:
        mapping = db.query(TeacherSubjectMapping).filter_by(id=mapping_id).first()
        questionnaire = db.query(QuestionnaireTemplate).filter_by(id=questionnaire_id).first()
        if not mapping or not questionnaire or mapping.session_id != questionnaire.session_id:
            return False
        academic_session = db.query(AcademicSession).filter_by(id=mapping.session_id).first()
        if not academic_session or academic_session.status != "DRAFT":
            return False
        db.query(MappingQuestionnaire).filter_by(mapping_id=mapping_id).delete()
        link = MappingQuestionnaire(mapping_id=mapping_id, questionnaire_id=questionnaire_id)
        db.add(link)
        return True

def delete_questionnaire(questionnaire_id: int) -> Tuple[bool, str]:
    with get_db_session() as db:
        q = db.query(QuestionnaireTemplate).filter_by(id=questionnaire_id).first()
        if not q:
            return False, "Questionnaire not found."
        academic_session = db.query(AcademicSession).filter_by(id=q.session_id).first()
        if not academic_session or academic_session.status != "DRAFT":
            return False, "Questionnaires are locked after poll launch."
            
        # Remove mapping links
        db.query(MappingQuestionnaire).filter_by(questionnaire_id=questionnaire_id).delete()
        db.delete(q)
        return True, "Questionnaire deleted."
