# 🏫 School Teacher Feedback & Evaluation System

A product-grade, privacy-preserving, and reusable web application built with **Python** and **Streamlit** for collecting student feedback, evaluating teachers, and generating comprehensive school analytics.

---

## 🌟 Features & Harmonization with Project Docs

This application synthesizes the requirements from both project documents:
- **`So yeah.docx`** (User workflow, reusability, Excel batch imports, fine-grained subject mapping, Google Forms-style questionnaire builder, card stepper with balloons animation, teacher personal analytics, tamper-evident poll locking)
- **`School_Teacher_Feedback_PRD_v1_2_School_Network_Final.docx`** (Formal PRD v1.2 specifications, local-network deployment, student anonymity isolation, k-anonymity suppression, PRD 6.3 report matrix, cryptographic closure hash)

### 1. Reusable Academic Sessions
- Create and manage yearly academic sessions (e.g., `2026-27`, `2027-28`).
- All configurations (questionnaires, imports, mappings) are managed via the web dashboard without modifying code.
- Historical sessions remain accessible as read-only archives.

### 2. Excel Batch Import & Validation
- **Student Import:** Upload `.xlsx` or `.csv` with `admission_number`, `student_name`, `class`, `section`, `stream`, and `roll_number`. Preserves leading zeroes.
- **Teacher Import:** Upload `.xlsx` or `.csv` with `teacher_id`, `teacher_name`, `phone_number`, `date_of_birth`, `department`, and `subjects_taught`.
- Downloadable Excel templates with built-in validation, deduplication, and error reporting.

### 3. Fine-Grained Teacher-Subject Mapping
- Select Class (6 to 12), Section (A, B, C, D, E), and Teacher.
- Assign Subject name and stream (General, Science, Commerce, Humanities).
- **Select All** checkbox for whole-class subjects.
- Searchable multi-select picker for elective/stream students (Classes 11 & 12).
- Dynamic questionnaire template assignment per mapping.

### 4. Questionnaire Form Builder
- Google Forms-style intuitive creator.
- Pre-seeded with standard 5-question Academic and Sports evaluation templates.
- Custom scale ratings (1 to 5 stars/scores: Poor, Fair, Good, Very Good, Excellent).

### 5. Student Feedback Experience
- **Login:** Admission number only with rate-limiting and generic errors.
- **Subject Cards Stepper:** Cards for all mapped teachers/subjects.
- **Atomic Locking:** Submitting feedback for a subject card locks that card permanently.
- **Celebration & Final Lock:** Streamlit balloons animation (`st.balloons()`) upon final submission. Prevents duplicate submissions permanently for that session.
- **Strict Privacy:** Responses are completely decoupled from student identities. No student ID or admission number is stored in response rows.

### 6. Teacher Portal
- **Login:** Teacher ID + Phone Number + Date of Birth.
- **Privacy First:** Only aggregated data; no individual student names or scores.
- **K-Anonymity Suppression:** If a class group has fewer than 5 responses, detailed scores are suppressed to prevent statistical reverse-identification.
- **Two Analytical Views:** Overall teacher performance and Class-by-Class drilldown.
- Download personal report in formatted Excel (`.xlsx`) or CSV.

### 7. Administrator Analytics & Export Matrix
- High-level KPIs: Enrollment, Completion %, Total Responses, School-wide average.
- **Official School Report Matrix (PRD Section 6.3):**
  `Class | Section | Teacher | Subject | Q1 Avg | Q2 Avg | Q3 Avg | Q4 Avg | Q5 Avg | Overall Avg | Responses`
- Interactive Plotly visualizations: Participation rate by class, teacher comparisons, question score distributions.
- **Export Center:** Download official school report matrix and teacher summaries in Excel and CSV.
- **Cryptographic Tamper-Evidence:** Closing a poll seals all records and generates an immutable SHA-256 fingerprint snapshot.

---

## 🚀 Quickstart Guide

### Option 1: Native Run (Windows / macOS / Linux)

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Generate Demo Data (Optional):**
   ```bash
   python sample_data/generate_sample_data.py
   ```

3. **Launch the Application:**
   - On Windows: Double-click `run.bat` or run:
     ```powershell
     .\run.ps1
     ```
   - Or run directly:
     ```bash
     streamlit run app.py
     ```

4. **Access the App:** Open your browser at `http://localhost:8501`.

---

### Option 2: Docker / Container Deployment

```bash
docker-compose up --build -d
```
Access at `http://<server-ip>:8501`.

---

## 🔑 Demo Login Credentials

The sample data generator provisions a realistic school dataset for session **`2026-27`**:

### 1. Administrator
- **Username:** `admin`
- **Password:** `admin123`

### 2. Teachers
| Teacher Name | Teacher ID | Phone Number | Date of Birth | Department |
| :--- | :--- | :--- | :--- | :--- |
| **Dr. Veer Malhotra** | `TCH-001` | `9876543210` | `1985-04-12` | Science |
| **Mrs. Sunita Verma** | `TCH-002` | `9812345678` | `1988-08-25` | Mathematics |
| **Mr. Rajesh Khanna** | `TCH-003` | `9823456789` | `1982-11-05` | Languages |
| **Coach Vikram Rana** | `TCH-004` | `9834567890` | `1991-02-18` | Sports |

### 3. Students
| Student Name | Admission Number | Class & Section | Status |
| :--- | :--- | :--- | :--- |
| **Kabir Reddy** | `ADM-6007` | Class 6-A | **Eligible to Vote** |
| **Meera Joshi** | `ADM-6008` | Class 6-A | **Eligible to Vote** |
| **Devansh Sen** | `ADM-1101` | Class 11-A (Science) | **Eligible to Vote** |
| **Aarav Sharma** | `ADM-6001` | Class 6-A | *Already Submitted (Locked)* |

---

## 🧪 Automated Testing

A full pytest test suite is included in `tests/`:

```bash
pytest tests/ -v
```

### Test Coverage:
1. `test_auth.py`: Admin bcrypt authentication, teacher multi-field login, student admission validation & duplicate locks.
2. `test_session_lifecycle.py`: Session creation, prelaunch validation checklist, poll launch, and SHA-256 seal.
3. `test_feedback_flow.py`: Subject card assignments, anonymous rating storage (ensuring absence of student IDs), and single-submission locks.
4. `test_reports_and_suppression.py`: PRD 6.3 matrix generation and k-anonymity suppression (< 5 responses).
5. `test_import_export.py`: Template generation, Excel student/teacher batch import, deduplication, and export.

---

## 🌐 School Local-Network (LAN) Deployment Plan

As specified in PRD Section 16:
1. **Host PC:** Assign a reserved static IP on the school local network (e.g. `192.168.1.100`).
2. **Firewall Rule:** Allow inbound TCP traffic on port `8501`.
3. **Execution:** Launch with `streamlit run app.py --server.port=8501 --server.address=0.0.0.0`.
4. **Access for Students & Teachers:** Students and staff connect from computers/tablets on the school Wi-Fi by navigating to:
   ```
   http://192.168.1.100:8501
   ```
5. **Database Options:**
   - **SQLite with WAL mode (Default):** Zero configuration, concurrent write-ahead logging enabled. Suitable for up to 500 simultaneous users.
   - **PostgreSQL:** For larger multi-thousand student deployments, configure `DATABASE_URL=postgresql://...` in `.env`.
