import io
from datetime import datetime, date
from typing import Tuple, List, Dict, Any, Optional
import pandas as pd
from database import (
    get_db_session, Student, Teacher, AuditLog, AcademicSession
)

def generate_student_excel_template() -> io.BytesIO:
    """Generates a downloadable Excel template for importing students."""
    df = pd.DataFrame([
        {
            "admission_number": "ADM-1001",
            "student_name": "Aarav Sharma",
            "class": 6,
            "section": "A",
            "stream": "General",
            "roll_number": "1"
        },
        {
            "admission_number": "ADM-1002",
            "student_name": "Ananya Patel",
            "class": 6,
            "section": "A",
            "stream": "General",
            "roll_number": "2"
        },
        {
            "admission_number": "ADM-1201",
            "student_name": "Rohan Gupta",
            "class": 11,
            "section": "B",
            "stream": "Science",
            "roll_number": "15"
        }
    ])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Students")
    output.seek(0)
    return output

def generate_teacher_excel_template() -> io.BytesIO:
    """Generates a downloadable Excel template for importing teachers."""
    df = pd.DataFrame([
        {
            "teacher_id": "TCH-001",
            "teacher_name": "Dr. Veer Malhotra",
            "phone_number": "9876543210",
            "date_of_birth": "1985-04-12",
            "department": "Science",
            "subjects_taught": "Science, Physics",
            "email": "veer.malhotra@school.edu"
        },
        {
            "teacher_id": "TCH-002",
            "teacher_name": "Mrs. Sunita Verma",
            "phone_number": "9812345678",
            "date_of_birth": "1990-08-25",
            "department": "Mathematics",
            "subjects_taught": "Mathematics",
            "email": "sunita.verma@school.edu"
        }
    ])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Teachers")
    output.seek(0)
    return output

def import_students_from_file(session_id: int, file_bytes: bytes, filename: str) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Parses, validates, and imports students from Excel or CSV file.
    Returns success status, summary message, and report details.
    """
    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(file_bytes), dtype={"admission_number": str, "roll_number": str})
        else:
            df = pd.read_excel(io.BytesIO(file_bytes), dtype={"admission_number": str, "roll_number": str})
    except Exception as e:
        return False, f"Failed to parse file: {str(e)}", {}

    # Normalize column names
    col_mapping = {c.strip().lower().replace(" ", "_"): c for c in df.columns}
    
    # Required columns check
    req_cols = ["admission_number", "student_name", "class", "section"]
    missing = [c for c in req_cols if c not in col_mapping]
    if missing:
        return False, f"Missing required columns: {', '.join(missing)}", {}
        
    valid_rows = []
    errors = []
    seen_adm = set()
    
    with get_db_session() as db:
        session = db.query(AcademicSession).filter_by(id=session_id).first()
        if not session or session.status != "DRAFT":
            return False, "Student imports are locked after poll launch.", {"errors": [], "imported": 0}

        # Check existing admission numbers in session
        existing_adm = {s.admission_number for s in db.query(Student.admission_number).filter_by(session_id=session_id).all()}
        
        for idx, row in df.iterrows():
            row_num = idx + 2 # Header is line 1
            adm = str(row[col_mapping["admission_number"]]).strip()
            name = str(row[col_mapping["student_name"]]).strip()
            
            # Extract class
            raw_class = row[col_mapping["class"]]
            try:
                class_lvl = int(float(raw_class))
            except Exception:
                errors.append(f"Row {row_num}: Invalid class '{raw_class}'. Must be an integer between 6 and 12.")
                continue
                
            sec = str(row[col_mapping["section"]]).strip().upper()
            stream = str(row[col_mapping.get("stream", "")]).strip() if "stream" in col_mapping and pd.notna(row[col_mapping["stream"]]) else "General"
            roll = str(row[col_mapping.get("roll_number", "")]).strip() if "roll_number" in col_mapping and pd.notna(row[col_mapping["roll_number"]]) else ""

            if not adm or adm == "nan":
                errors.append(f"Row {row_num}: Missing admission number.")
                continue
            if not name or name == "nan":
                errors.append(f"Row {row_num}: Missing student name.")
                continue
            if class_lvl < 1 or class_lvl > 12:
                errors.append(f"Row {row_num}: Class {class_lvl} out of valid range (6-12).")
                continue
            if not sec or sec == "NAN":
                errors.append(f"Row {row_num}: Missing section.")
                continue
                
            if adm in seen_adm:
                errors.append(f"Row {row_num}: Duplicate admission number '{adm}' in uploaded file.")
                continue
            if adm in existing_adm:
                errors.append(f"Row {row_num}: Admission number '{adm}' already exists in this session.")
                continue
                
            seen_adm.add(adm)
            valid_rows.append(Student(
                session_id=session_id,
                admission_number=adm,
                student_name=name,
                class_level=class_lvl,
                section=sec,
                stream=stream,
                roll_number=roll
            ))
            
        if not valid_rows and errors:
            return False, f"Validation failed with {len(errors)} error(s).", {"errors": errors, "imported": 0}
            
        for s in valid_rows:
            db.add(s)
            
        log = AuditLog(
            session_id=session_id,
            actor="Admin",
            action="IMPORT_STUDENTS",
            details=f"Imported {len(valid_rows)} students from file '{filename}'."
        )
        db.add(log)
        
    summary = f"Successfully imported {len(valid_rows)} students."
    if errors:
        summary += f" ({len(errors)} rows skipped due to errors)."
        
    return True, summary, {"imported": len(valid_rows), "errors": errors}

def import_teachers_from_file(session_id: int, file_bytes: bytes, filename: str) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Parses, validates, and imports teachers from Excel or CSV file.
    """
    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(file_bytes), dtype={"teacher_id": str, "phone_number": str})
        else:
            df = pd.read_excel(io.BytesIO(file_bytes), dtype={"teacher_id": str, "phone_number": str})
    except Exception as e:
        return False, f"Failed to parse file: {str(e)}", {}

    col_mapping = {c.strip().lower().replace(" ", "_"): c for c in df.columns}
    
    req_cols = ["teacher_id", "teacher_name", "phone_number", "date_of_birth"]
    missing = [c for c in req_cols if c not in col_mapping]
    if missing:
        return False, f"Missing required columns: {', '.join(missing)}", {}
        
    valid_rows = []
    errors = []
    seen_tid = set()
    
    with get_db_session() as db:
        session = db.query(AcademicSession).filter_by(id=session_id).first()
        if not session or session.status != "DRAFT":
            return False, "Teacher imports are locked after poll launch.", {"errors": [], "imported": 0}

        existing_tids = {t.teacher_id for t in db.query(Teacher.teacher_id).filter_by(session_id=session_id).all()}
        
        for idx, row in df.iterrows():
            row_num = idx + 2
            tid = str(row[col_mapping["teacher_id"]]).strip()
            name = str(row[col_mapping["teacher_name"]]).strip()
            phone = str(row[col_mapping["phone_number"]]).strip().replace(".0", "")
            raw_dob = row[col_mapping["date_of_birth"]]
            
            dept = str(row[col_mapping.get("department", "")]).strip() if "department" in col_mapping and pd.notna(row[col_mapping["department"]]) else "Academic"
            subjects = str(row[col_mapping.get("subjects_taught", "")]).strip() if "subjects_taught" in col_mapping and pd.notna(row[col_mapping["subjects_taught"]]) else ""
            email = str(row[col_mapping.get("email", "")]).strip() if "email" in col_mapping and pd.notna(row[col_mapping["email"]]) else ""

            if not tid or tid == "nan":
                errors.append(f"Row {row_num}: Missing teacher ID.")
                continue
            if not name or name == "nan":
                errors.append(f"Row {row_num}: Missing teacher name.")
                continue
            if not phone or phone == "nan":
                errors.append(f"Row {row_num}: Missing phone number.")
                continue
                
            # Parse Date of Birth
            dob = None
            if isinstance(raw_dob, (datetime, date)):
                dob = raw_dob.date() if isinstance(raw_dob, datetime) else raw_dob
            else:
                try:
                    dob = pd.to_datetime(raw_dob).date()
                except Exception:
                    errors.append(f"Row {row_num}: Invalid date of birth '{raw_dob}'. Use YYYY-MM-DD.")
                    continue
                    
            if tid in seen_tid:
                errors.append(f"Row {row_num}: Duplicate teacher ID '{tid}' in uploaded file.")
                continue
            if tid in existing_tids:
                errors.append(f"Row {row_num}: Teacher ID '{tid}' already exists in this session.")
                continue
                
            seen_tid.add(tid)
            valid_rows.append(Teacher(
                session_id=session_id,
                teacher_id=tid,
                teacher_name=name,
                phone_number=phone,
                date_of_birth=dob,
                department=dept,
                subjects_taught=subjects,
                email=email
            ))
            
        if not valid_rows and errors:
            return False, f"Validation failed with {len(errors)} error(s).", {"errors": errors, "imported": 0}
            
        for t in valid_rows:
            db.add(t)
            
        log = AuditLog(
            session_id=session_id,
            actor="Admin",
            action="IMPORT_TEACHERS",
            details=f"Imported {len(valid_rows)} teachers from file '{filename}'."
        )
        db.add(log)
        
    summary = f"Successfully imported {len(valid_rows)} teachers."
    if errors:
        summary += f" ({len(errors)} rows skipped due to errors)."
        
    return True, summary, {"imported": len(valid_rows), "errors": errors}

def export_dataframe_to_excel(df: pd.DataFrame, sheet_name: str = "Report") -> io.BytesIO:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    output.seek(0)
    return output
