# Campus Management System (CampusIQ) - Project Documentation

## 1. Project Overview
This project is a comprehensive **Campus Management System** designed to streamline administrative, academic, and student-related operations within an educational institution. It is built using **Python Flask** for the backend and **server-side rendered HTML/CSS/JavaScript** for the frontend.

The system features robust **Role-Based Access Control (RBAC)** with three distinct portals:
- **Admin Portal**: For overall management of the institution (students, faculty, departments, fees, etc.).
- **Faculty Portal**: For academic management (attendance, marks, resources, schedule).
- **Student Portal**: For students to track their academic progress, attendance, and fees.

---

## 2. Technology Stack

### Backend
- **Language**: Python 3.x
- **Framework**: Flask (Microframework)
- **Database ORM**: SQLAlchemy
- **Authentication**: Flask-Login
- **Configuration**: Environment-based (supports Development/Production modes via `.env`)

### Frontend
- **Templating Engine**: Jinja2 (Serverside rendering)
- **Styling**: Vanilla CSS (Custom design system variables)
- **Scripting**: Vanilla JavaScript
- **Assets**: Stored in `static/` directory

### Database
- **Primary**: SQLite (`campus.db`) for development/default.
- **Compatibility**: Configured to support PostgreSQL (Supabase) via connection strings in `config.py`.

---

## 3. Project Structure

```text
/
├── app.py                  # Application entry point & Factory function
├── config.py               # Configuration classes (Dev, Prod, Test)
├── extensions.py           # Flask extensions setup (db, login_manager)
├── models.py               # Database Models (SQLAlchemy entities)
│
├── routes_admin.py         # Controller logic for Admin features
├── routes_faculty.py       # Controller logic for Faculty features
├── routes_student.py       # Controller logic for Student features
├── routes_auth.py          # Authentication routes (Login/Logout)
│
├── templates/              # HTML Templates (Jinja2)
│   ├── admin/              # Admin-specific templates
│   ├── faculty/            # Faculty-specific templates
│   ├── student/            # Student-specific templates
│   └── auth/               # Login templates
│
├── static/                 # Static Assets
│   ├── css/                # Stylesheets
│   └── js/                 # Client-side scripts
│
└── .env                    # Environment variables (Secrets/Config)
```

---

## 4. Key Components & Data Models

### User Management (`models.py`)
- **User**: Central authentication entity containing username, password hash, and role.
- **Student**: Extended profile linked to `User`, containing academic details (Branch, Year, Sem) and personal info.
- **Faculty**: Extended profile linked to `User`, containing professional details (Dept, Designation, Experience).

### Academic Management
- **Department**: Manages headers and codes (e.g., CSE, ECE).
- **Subject**: Course definitions with credits and types (Theory/Lab).
- **ClassOffering**: Links a Subject to a Faculty and a specific Class (Branch/Year/Sem/Section).
- **Timetable**: Weekly schedule configurations.
- **Attendance**: Daily attendance records per student per subject.
- **Mark**: Assessment scores (Mid-terms, Assignments, Finals).

### Administration
- **Fee**: Student fee tracking (Tuition, Exam fees) and payment status.
- **Announcement**: System-wide notifications with target audiences.
- **Resource**: File sharing/uploading for academic materials.

---

## 5. Portal Features

### 🛡️ Admin Portal (`/admin`)
- **Dashboard**: High-level statistics (Student/Faculty counts, Fee collection rates, Dept overview).
- **Student Management**: Add, Edit, Delete, Bulk Delete, Import (CSV), Export (CSV).
- **Faculty Management**: Add, Edit, Delete, Assign Departments.
- **Academics**:
    - **Departments**: Manage department codes and heads.
    - **Subjects**: Create curriculum and credit systems.
    - **Timetable**: generate and modify class schedules.
- **Fees**: Track payments and dues.

### 👨‍🏫 Faculty Portal (`/faculty`)
- **Dashboard**: schedule view and quick stats.
- **Attendance**: Mark and View student attendance.
- **Marks**: Enter and update student assessment scores.
- **Resources**: Upload study materials for students.
- **Profile**: View and manage professional details.

### 👨‍🎓 Student Portal (`/student`)
- **Dashboard**: Overview of attendance, recent marks, and notifications.
- **My Academics**: View Timetable, Attendance history, and Marks history.
- **Resources**: Download materials uploaded by faculty.
- **Fee Status**: Check due amounts and payment history.

---

## 6. Setup & Running

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Environment Setup**:
   - Ensure a `.env` file exists (see `.env.example`).
   - Define `FLASK_ENV`, `SECRET_KEY`, and `SQLALCHEMY_DATABASE_URI`.

3. **Initialize Database**:
   - The app attempts to auto-create tables on first run via `db.create_all()` in `app.py`.
   - Use `seed_data.py` (if available) to populate initial dummy data.

4. **Run Application**:
   ```bash
   python app.py
   ```
   - Access the app at `http://localhost:5000`.

---

## 7. Developer Notes
- **Factory Pattern**: The app uses `create_app()` for better testability and configuration management.
- **Blueprints**: Routes are modularized using Flask Blueprints (`admin_bp`, `faculty_bp`, etc.).
- **Validation**:
    - Input validation is handled both client-side (HTML5) and server-side.
    - CSV Imports include rigorous validation for duplicates and data integrity.
