from pydantic import BaseModel, EmailStr
from typing import Optional, List, Any
from datetime import datetime

# USER & AUTH
class Token(BaseModel):
    access_token: str
    token_type: str
    redirect_url: str

class LoginRequest(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str
    password: str
    email: str
    role: str
    name: str

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    name: str
    created_at: datetime

# STUDENT
class StudentBase(BaseModel):
    student_id: str
    name: str
    email: Any # Can be str or None
    branch: str
    year: int
    semester: int
    section: str
    phone: Optional[str] = None
    address: Optional[str] = None
    father_name: Optional[str] = None
    mother_name: Optional[str] = None
    parents_phone: Optional[str] = None
    date_of_birth: Optional[str] = None
    status: str = 'active'
    counselor_id: Optional[int] = None
    batch: Optional[str] = None # e.g. "2024-2028"

class StudentCreate(StudentBase):
    password: Optional[str] = 'student123' # Default password if creating user
    
class StudentUpdate(StudentBase):
    pass

class StudentResponse(StudentBase):
    id: int
    user_id: str

# FACULTY
class FacultyBase(BaseModel):
    faculty_id: str
    name: str
    email: str
    department: str
    designation: Optional[str] = None
    phone: Optional[str] = None
    qualification: Optional[str] = None
    experience: Optional[int] = 0
    address: Optional[str] = None
    joining_date: Optional[str] = None
    gender: Optional[str] = None
    status: str = 'active'
    
class FacultyCreate(FacultyBase):
    password: Optional[str] = 'password123'

class FacultyResponse(FacultyBase):
    id: int
    user_id: str

# ACADEMIC
class AttendanceMark(BaseModel):
    student_id: int
    status: str # 'present', 'absent'

class AttendanceRequest(BaseModel):
    offering_id: int
    date: str
    time: str
    attendance: List[AttendanceMark]
    update_reason: Optional[str] = None

class MarkEntry(BaseModel):
    student_id: int
    marks: float
    is_absent: bool = False
    remarks: Optional[str] = None

class MarksSubmitRequest(BaseModel):
    offering_id: int
    assessment_type: str
    max_marks: float
    marks_data: List[MarkEntry]
    date: str


# DEPARTMENT
class DepartmentBase(BaseModel):
    name: str
    code: str
    head_of_department: Optional[str] = None

class DepartmentCreate(DepartmentBase):
    pass

class DepartmentUpdate(DepartmentBase):
    pass

# SUBJECT
class SubjectBase(BaseModel):
    name: str
    code: str
    branch: str
    year: int
    semester: int
    type: str
    credits: float

class SubjectCreate(SubjectBase):
    pass

class SubjectUpdate(SubjectBase):
    pass

# CLASS OFFERING (Allocation)
class ClassOfferingBase(BaseModel):
    branch: str
    year: int
    semester: int
    section: str
    subject_id: int
    faculty_id: int
    is_mentor: bool = False
    is_active: bool = True

class ClassOfferingCreate(ClassOfferingBase):
    pass

# TIMETABLE
class TimetableBase(BaseModel):
    day_of_week: str
    start_time: str
    end_time: str
    subject_id: int
    branch: str
    year: int
    semester: int
    section: str
    original_faculty_id: int
    current_faculty_id: int
    room_number: str

class TimetableCreate(TimetableBase):
    pass

# FEES
class FeeBase(BaseModel):
    student_id: int
    semester: int
    total_fee: float
    paid_amount: float
    due_amount: float
    status: str
    payment_date: Optional[str] = None

class FeeCreate(FeeBase):
    pass
    
# ANNOUNCEMENTS
class AnnouncementBase(BaseModel):
    title: str
    content: str
    target_audience: str
    department: Optional[str] = "all"
    priority: str = "normal"
    expires_at: Optional[str] = None
    send_email: bool = False
    is_pinned: bool = False
    is_active: bool = True

class AnnouncementCreate(AnnouncementBase):
    pass

class AnnouncementUpdate(AnnouncementBase):
    pass
