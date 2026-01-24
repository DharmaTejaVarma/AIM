-- B.TECH CAMPUS MANAGEMENT SYSTEM - PRODUCTION SCHEMA
-- REVISED: Matches Python Backend (Singular Naming + UUIDs)

-- MODULE 1: ACADEMIC YEAR
CREATE TABLE IF NOT EXISTS public.academic_year (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT NOT NULL, -- "2024-2025"
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    is_current BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- MODULE 2: SEMESTER
CREATE TABLE IF NOT EXISTS public.semester (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    academic_year_id UUID REFERENCES public.academic_year(id) ON DELETE CASCADE,
    name TEXT NOT NULL, -- "Semester 1"
    semester_number INT,
    year_number INT,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    type TEXT, -- Odd/Even
    status TEXT DEFAULT 'Upcoming', -- Upcoming, Active, Closed
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- MODULE 3: COURSE (e.g. B.Tech)
CREATE TABLE IF NOT EXISTS public.course (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT NOT NULL,
    code TEXT NOT NULL,
    duration_years INT DEFAULT 4,
    total_semesters INT DEFAULT 8,
    status TEXT DEFAULT 'Active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- MODULE 4: DEPARTMENT (Functions as Branch in Backend logic)
CREATE TABLE IF NOT EXISTS public.department (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT NOT NULL, -- "Computer Science & Engineering"
    code TEXT NOT NULL, -- "CSE"
    course_id UUID REFERENCES public.course(id),
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(code, course_id)
);

-- MODULE 5: BATCH
CREATE TABLE IF NOT EXISTS public.batch (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT NOT NULL UNIQUE, -- "2024-2028"
    start_year INT,
    end_year INT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- MODULE 6: SECTION
CREATE TABLE IF NOT EXISTS public.section (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT NOT NULL, -- "A"
    academic_year_id UUID REFERENCES public.academic_year(id),
    semester_id UUID REFERENCES public.semester(id),
    course_id UUID REFERENCES public.course(id),
    department_id UUID REFERENCES public.department(id), -- Branch
    year_number INT,
    class_teacher_id UUID, -- References faculty(id)
    max_students INT DEFAULT 60,
    status TEXT DEFAULT 'Active',
    UNIQUE(department_id, semester_id, name)
);

-- MODULE 7: STUDENT
CREATE TABLE IF NOT EXISTS public.student (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID UNIQUE, -- Links to auth/users table
    student_id TEXT NOT NULL UNIQUE, -- Register Number
    name TEXT NOT NULL,
    email TEXT,
    
    course_id UUID REFERENCES public.course(id),
    branch_id UUID REFERENCES public.department(id), 
    branch TEXT, -- Backend inserts 'branch' name here 
    
    section_id UUID REFERENCES public.section(id),
    section TEXT,
    
    year INT DEFAULT 1,
    semester INT DEFAULT 1,
    current_year INT GENERATED ALWAYS AS (year) STORED, 
    current_semester INT GENERATED ALWAYS AS (semester) STORED,
    
    batch TEXT, -- "2024-2028"
    
    -- Personal Info
    phone TEXT,
    address TEXT,
    father_name TEXT,
    mother_name TEXT,
    parents_phone TEXT,
    date_of_birth DATE,
    admission_date DATE,
    
    counselor_id UUID, -- References faculty
    status TEXT DEFAULT 'Active'
);

-- MODULE 8: SUBJECT
CREATE TABLE IF NOT EXISTS public.subject (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT NOT NULL,
    code TEXT NOT NULL UNIQUE,
    course_id UUID REFERENCES public.course(id),
    department_id UUID REFERENCES public.department(id),
    semester_number INT,
    credits FLOAT DEFAULT 3.0,
    type TEXT CHECK (type IN ('Theory', 'Lab', 'Project', 'Elective')), 
    subject_type TEXT, 
    weekly_hours INT DEFAULT 4,
    status TEXT DEFAULT 'Active'
);

-- MODULE 9: CLASS OFFERING (Faculty Allocation)
CREATE TABLE IF NOT EXISTS public.class_offering (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    faculty_id UUID, -- References faculty
    subject_id UUID REFERENCES public.subject(id),
    section_id UUID REFERENCES public.section(id),
    academic_year_id UUID REFERENCES public.academic_year(id),
    semester_id UUID REFERENCES public.semester(id),
    
    branch TEXT, 
    year INT,
    semester INT,
    section TEXT,
    
    is_primary BOOLEAN DEFAULT TRUE,
    is_mentor BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- MODULE 10: TIMETABLE
CREATE TABLE IF NOT EXISTS public.timetable (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    academic_year_id UUID REFERENCES public.academic_year(id),
    semester_id UUID REFERENCES public.semester(id),
    section_id UUID REFERENCES public.section(id),
    
    day_of_week TEXT NOT NULL,
    period_number INT NOT NULL,
    start_time TIME,
    end_time TIME,
    
    subject_id UUID REFERENCES public.subject(id),
    faculty_id UUID, -- References faculty
    
    branch TEXT,
    year INT,
    section TEXT,
    
    original_faculty_id UUID, -- For substitutions
    current_faculty_id UUID,
    is_proxy BOOLEAN DEFAULT FALSE,
    
    status TEXT DEFAULT 'Active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(section_id, day_of_week, period_number)
);

-- MODULE 11: ATTENDANCE
CREATE TABLE IF NOT EXISTS public.attendance (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    student_id UUID REFERENCES public.student(id),
    subject_id UUID REFERENCES public.subject(id),
    date DATE NOT NULL,
    period_number INT,
    status TEXT CHECK (status IN ('Present', 'Absent', 'Late', 'Excused', 'On Duty')),
    marked_by UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(student_id, date, period_number)
);

-- MODULE 12: MARK (External/Internal)
CREATE TABLE IF NOT EXISTS public.mark (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    student_id UUID REFERENCES public.student(id),
    subject_id UUID REFERENCES public.subject(id),
    assessment_type TEXT, 
    marks FLOAT DEFAULT 0,
    max_marks FLOAT DEFAULT 100,
    date DATE,
    entered_by UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- MODULE 13: PERIOD ALERT (Faculty Substitution)
CREATE TABLE IF NOT EXISTS public.period_alert (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    alerted_by UUID NOT NULL, 
    alerted_to UUID NOT NULL, 
    period_id UUID NOT NULL, 
    period_date DATE NOT NULL,
    period_time TEXT NOT NULL,
    subject TEXT,
    class_name TEXT,
    reason TEXT,
    status TEXT DEFAULT 'PENDING',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- MODULE 14: FACULTY (Basic Definition)
CREATE TABLE IF NOT EXISTS public.faculty (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID UNIQUE,
    faculty_id TEXT UNIQUE,
    name TEXT NOT NULL,
    email TEXT,
    department TEXT,
    designation TEXT,
    phone TEXT,
    is_hod BOOLEAN DEFAULT FALSE,
    status TEXT DEFAULT 'Active'
);

-- UTILS: GLOBAL SETTINGS
CREATE TABLE IF NOT EXISTS public.global_setting (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- RLS POLICIES (Simulated Allow All for correct dev function)
ALTER TABLE public.period_alert DISABLE ROW LEVEL SECURITY;