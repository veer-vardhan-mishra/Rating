from typing import List, Dict, Optional, Any
from sqlalchemy import func
import pandas as pd
from database import (
    get_db_session, Teacher, TeacherSubjectMapping, FeedbackResponse,
    Student, SubmissionRecord, AcademicSession, MappingStudent, CardSubmission
)
from config import Config

def get_teacher_report(session_id: int, teacher_id: int, min_threshold: int = Config.MIN_RESPONSES_FOR_REPORT) -> Dict[str, Any]:
    """
    Computes teacher personal analytics.
    Strictly aggregates data with k-anonymity suppression.
    Never exposes individual student identities.
    """
    with get_db_session() as db:
        teacher = db.query(Teacher).filter_by(id=teacher_id, session_id=session_id).first()
        if not teacher:
            return {"error": "Teacher not found"}
            
        mappings = db.query(TeacherSubjectMapping).filter_by(
            session_id=session_id,
            teacher_id=teacher_id
        ).all()
        
        mapping_ids = [m.id for m in mappings]
        
        # Total responses for this teacher
        all_responses = db.query(FeedbackResponse).filter(
            FeedbackResponse.mapping_id.in_(mapping_ids)
        ).all() if mapping_ids else []
        
        total_responses = len(all_responses)
        participant_query = db.query(CardSubmission.student_id).filter(
            CardSubmission.session_id == session_id,
            CardSubmission.mapping_id.in_(mapping_ids)
        ) if mapping_ids else None
        total_participants = participant_query.distinct().count() if participant_query is not None else 0
        
        # Overall average score
        overall_avg = 0.0
        if all_responses:
            overall_avg = round(sum(r.rating_value for r in all_responses) / total_responses, 2)
        overall_suppressed = total_participants < min_threshold
        if overall_suppressed:
            overall_avg = None

        mapping_participant_counts = {}
        if mapping_ids:
            mapping_participant_counts = dict(
                db.query(CardSubmission.mapping_id, func.count(CardSubmission.id)).filter(
                    CardSubmission.session_id == session_id,
                    CardSubmission.mapping_id.in_(mapping_ids)
                ).group_by(CardSubmission.mapping_id).all()
            )
            
        # Class-wise breakdowns
        classes_data = []
        for m in mappings:
            class_responses = [r for r in all_responses if r.mapping_id == m.id]
            eligible_count = db.query(MappingStudent).filter_by(mapping_id=m.id).count()
            participant_count = mapping_participant_counts.get(m.id, 0)
            
            # Question averages for this mapping
            q_map = {}
            for r in class_responses:
                q_id = r.question_id
                q_text = r.question_text
                if q_id not in q_map:
                    q_map[q_id] = {"text": q_text, "scores": []}
                q_map[q_id]["scores"].append(r.rating_value)
                
            is_suppressed = participant_count < min_threshold
            q_averages = []
            for q_id, q_info in q_map.items():
                avg = round(sum(q_info["scores"]) / len(q_info["scores"]), 2) if q_info["scores"] else 0.0
                q_averages.append({
                    "question_id": q_id,
                    "question_text": q_info["text"],
                    "average": avg if not is_suppressed else None,
                    "count": len(q_info["scores"]) if not is_suppressed else None
                })
                
            classes_data.append({
                "mapping_id": m.id,
                "class_level": m.class_level,
                "section": m.section,
                "subject": m.subject,
                "stream": m.stream or "",
                "eligible_count": eligible_count,
                "response_count": participant_count,
                "is_suppressed": is_suppressed,
                "class_average": round(sum(r.rating_value for r in class_responses) / len(class_responses), 2) if (class_responses and not is_suppressed) else None,
                "question_breakdown": q_averages
            })
            
        # Overall question breakdown across all classes
        all_q_map = {}
        for r in all_responses:
            q_id = r.question_id
            if q_id not in all_q_map:
                all_q_map[q_id] = {"text": r.question_text, "scores": []}
            all_q_map[q_id]["scores"].append(r.rating_value)
            
        overall_questions = []
        for q_id, q_info in all_q_map.items():
            avg = round(sum(q_info["scores"]) / len(q_info["scores"]), 2) if q_info["scores"] else 0.0
            overall_questions.append({
                "question_id": q_id,
                "question_text": q_info["text"],
                "average": avg if not overall_suppressed else None,
                "count": len(q_info["scores"]) if not overall_suppressed else None
            })
            
        return {
            "teacher_id": teacher.id,
            "teacher_name": teacher.teacher_name,
            "department": teacher.department,
            "total_classes": len(mappings),
            "total_responses": total_participants,
            "overall_average": overall_avg,
            "overall_is_suppressed": overall_suppressed,
            "classes": classes_data,
            "overall_questions": overall_questions
        }

def get_admin_school_overview(session_id: int) -> Dict[str, Any]:
    with get_db_session() as db:
        total_students = db.query(Student).filter_by(session_id=session_id).count()
        total_teachers = db.query(Teacher).filter_by(session_id=session_id).count()
        total_mappings = db.query(TeacherSubjectMapping).filter_by(session_id=session_id).count()
        
        submitted_students = db.query(SubmissionRecord).filter_by(
            session_id=session_id,
            is_complete=True
        ).count()
        
        all_responses = db.query(FeedbackResponse).filter_by(session_id=session_id).all()
        total_response_count = len(all_responses)
        school_avg = round(sum(r.rating_value for r in all_responses) / total_response_count, 2) if total_response_count > 0 else 0.0
        
        participation_rate = round((submitted_students / total_students) * 100, 1) if total_students > 0 else 0.0
        
        # Participation by class
        classes = db.query(Student.class_level).filter_by(session_id=session_id).distinct().all()
        class_stats = []
        for c in sorted([c[0] for c in classes]):
            st_in_class = db.query(Student.id).filter_by(session_id=session_id, class_level=c).all()
            st_ids = [s[0] for s in st_in_class]
            st_count = len(st_ids)
            sub_count = db.query(SubmissionRecord).filter(
                SubmissionRecord.session_id == session_id,
                SubmissionRecord.student_id.in_(st_ids),
                SubmissionRecord.is_complete == True
            ).count() if st_ids else 0
            rate = round((sub_count / st_count) * 100, 1) if st_count > 0 else 0.0
            class_stats.append({
                "class_level": f"Class {c}",
                "enrolled": st_count,
                "submitted": sub_count,
                "rate": rate
            })
            
        return {
            "total_students": total_students,
            "total_teachers": total_teachers,
            "total_mappings": total_mappings,
            "submitted_students": submitted_students,
            "participation_rate": participation_rate,
            "total_responses": total_response_count,
            "school_avg": school_avg,
            "class_stats": class_stats
        }

def get_school_report_matrix(session_id: int) -> pd.DataFrame:
    """
    Generates the official School Report Table as defined in PRD Section 6.3:
    Columns: Class | Section | Teacher | Subject | Q1 Avg | Q2 Avg | Q3 Avg ... | Overall Avg | Responses
    """
    with get_db_session() as db:
        mappings = db.query(TeacherSubjectMapping).filter_by(session_id=session_id).all()
        
        rows = []
        for m in mappings:
            teacher = db.query(Teacher).filter_by(id=m.teacher_id).first()
            teacher_name = teacher.teacher_name if teacher else "Unknown"
            
            responses = db.query(FeedbackResponse).filter_by(mapping_id=m.id).all()
            resp_count = len(responses)
            
            row = {
                "Class": m.class_level,
                "Section": m.section,
                "Teacher": teacher_name,
                "Subject": m.subject,
                "Stream": m.stream or "General"
            }
            
            # Group by question_id
            q_scores = {}
            for r in responses:
                if r.question_id not in q_scores:
                    q_scores[r.question_id] = []
                q_scores[r.question_id].append(r.rating_value)
                
            all_scores = []
            # Calculate Q averages dynamically for whatever questions exist
            max_q = max([r.question_id for r in responses] + [5])
            for q_id in range(1, max_q + 1):
                scores = q_scores.get(q_id, [])
                if scores:
                    avg_val = round(sum(scores) / len(scores), 2)
                    row[f"Q{q_id} Avg"] = avg_val
                    all_scores.extend(scores)
                else:
                    # If this teacher had fewer questions, show N/A
                    row[f"Q{q_id} Avg"] = "-"
                    
            row["Overall Avg"] = round(sum(all_scores) / len(all_scores), 2) if all_scores else "-"
            row["Responses"] = resp_count
            rows.append(row)
            
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values(by=["Class", "Section", "Subject"])
        return df

def get_teacher_comparisons(session_id: int) -> pd.DataFrame:
    """
    Aggregates teacher comparisons across shared questions.
    """
    with get_db_session() as db:
        teachers = db.query(Teacher).filter_by(session_id=session_id).all()
        rows = []
        for t in teachers:
            mappings = db.query(TeacherSubjectMapping).filter_by(session_id=session_id, teacher_id=t.id).all()
            m_ids = [m.id for m in mappings]
            responses = db.query(FeedbackResponse).filter(FeedbackResponse.mapping_id.in_(m_ids)).all() if m_ids else []
            
            resp_count = len(responses)
            avg_score = round(sum(r.rating_value for r in responses) / resp_count, 2) if resp_count > 0 else 0.0
            
            rows.append({
                "Teacher Code": t.teacher_id,
                "Teacher Name": t.teacher_name,
                "Department": t.department,
                "Subjects": t.subjects_taught or "N/A",
                "Total Classes": len(mappings),
                "Total Responses": resp_count,
                "Average Rating": avg_score
            })
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values(by="Average Rating", ascending=False)
        return df
