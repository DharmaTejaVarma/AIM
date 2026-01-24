from pydantic import BaseModel
from typing import Optional, List
from datetime import date, time

# -- ACADEMIC YEAR --
class AcademicYearCreate(BaseModel):
    name: str # "2024-2025"
    start_date: str # YYYY-MM-DD
    end_date: str # YYYY-MM-DD
    is_active: bool = True
    is_current: bool = False

class AcademicYearResponse(AcademicYearCreate):
    id: int
    created_at: str

# -- SEMESTER --
class SemesterCreate(BaseModel):
    academic_year_id: str # UUID str now
    name: str # "Semester 1", "Odd"
    start_date: str
    end_date: str
    sequence_number: int
    status: str = "Upcoming" # Upcoming, Active, Closed

class SemesterResponse(SemesterCreate):
    id: str

# -- COURSE --
class CourseCreate(BaseModel):
    name: str # "B.Tech"
    code: str # "BTECH"
    duration_years: int = 4
    total_semesters: int = 8
    status: str = "Active"

# -- BRANCH --
class BranchCreate(BaseModel):
    name: str # "Computer Science..."
    code: str # "CSE"
    course_id: str # UUID of Course
    department_id: Optional[str] = None # Optional link to DB department
    status: str = "Active"

# -- DEPARTMENT (DB) --
class DepartmentCreateV2(BaseModel):
    name: str
    code: str
    hod_faculty_id: Optional[int] = None
    status: str = "active"

# -- SECTION --
class SectionCreate(BaseModel):
    name: str
    academic_year_id: str
    course_id: str
    branch_id: str
    semester_id: str
    class_teacher_id: Optional[int] = None
    max_students: int = 60
    status: str = "active"

# -- ALLOCATION --
class AllocationCreate(BaseModel):
    academic_year_id: int
    semester_id: int
    section_id: int
    subject_id: int
    faculty_id: int
    is_primary: bool = True

# -- BATCH --
class BatchCreate(BaseModel):
    name: str # "2024-2028"
    start_year: int
    end_year: int
    is_active: bool = True
