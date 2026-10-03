import pytest
import io
import pandas as pd
from datetime import date
from database import init_db, get_db_session, AcademicSession, Student, Teacher
from session_service import create_session
from import_export_service import (
    generate_student_excel_template, generate_teacher_excel_template,
    import_students_from_file, import_teachers_from_file
)

@pytest.fixture(autouse=True)
def setup_db():
    init_db()

def test_template_generation():
    st_tpl = generate_student_excel_template()
    assert st_tpl.getbuffer().nbytes > 0
    df_st = pd.read_excel(st_tpl)
    assert "admission_number" in df_st.columns
    assert "student_name" in df_st.columns
    assert "class" in df_st.columns
    assert "section" in df_st.columns
    
    tch_tpl = generate_teacher_excel_template()
    assert tch_tpl.getbuffer().nbytes > 0
    df_tch = pd.read_excel(tch_tpl)
    assert "teacher_id" in df_tch.columns
    assert "phone_number" in df_tch.columns
    assert "date_of_birth" in df_tch.columns

def test_import_students_and_validation():
    success, _, session_id = create_session(
        "Import Test Session", date(2028, 4, 1), date(2029, 3, 31)
    )
    assert success is True

    with get_db_session() as db:
        sess = db.query(AcademicSession).filter_by(id=session_id).first()
        assert sess is not None
        
        # Valid Excel
        df_valid = pd.DataFrame([
            {"admission_number": "ADM-TEST-9901", "student_name": "Test Student 1", "class": 8, "section": "A", "stream": "General", "roll_number": "1"},
            {"admission_number": "ADM-TEST-9902", "student_name": "Test Student 2", "class": 8, "section": "A", "stream": "General", "roll_number": "2"}
        ])
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_valid.to_excel(writer, index=False)
        buffer.seek(0)
        
        success, msg, rep = import_students_from_file(sess.id, buffer.getvalue(), "test_students.xlsx")
        assert success is True
        assert rep["imported"] == 2
        
        # Verify in DB
        st1 = db.query(Student).filter_by(session_id=sess.id, admission_number="ADM-TEST-9901").first()
        assert st1 is not None
        assert st1.student_name == "Test Student 1"
        
        # Duplicate import rejection
        dup_success, dup_msg, dup_rep = import_students_from_file(sess.id, buffer.getvalue(), "test_students.xlsx")
        assert dup_rep["imported"] == 0
        assert len(dup_rep["errors"]) == 2
