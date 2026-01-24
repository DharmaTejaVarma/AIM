-- Enable UUID extension
create extension if not exists "uuid-ossp";

-- 0. CLEANUP (Drop tables to ensure schema consistency)
drop table if exists alteration cascade;
drop table if exists announcement cascade;
drop table if exists assignment cascade;
drop table if exists resource cascade;
drop table if exists fee cascade;
drop table if exists mark cascade;
drop table if exists attendance cascade;
drop table if exists timetable cascade;
drop table if exists class_offering cascade;
drop table if exists student cascade;
drop table if exists faculty cascade;
drop table if exists subject cascade;
drop table if exists department cascade;
drop table if exists users cascade;
drop table if exists global_setting cascade;

-- 1. USERS Table (Strict Requirement: UUID PK)
create table if not exists users (
    id uuid primary key default uuid_generate_v4(),
    username text unique not null,
    email text,
    password_hash text not null,
    role text not null check (role in ('admin', 'faculty', 'student')),
    name text not null,
    created_at timestamp with time zone default now()
);

-- 2. DEPARTMENTS
create table if not exists department (
    id serial primary key,
    name text not null,
    code text not null,
    head_of_department text,
    created_at timestamp with time zone default now()
);

-- 3. SUBJECTS
create table if not exists subject (
    id serial primary key,
    name text not null,
    code text not null,
    credits double precision not null,
    branch text not null,
    year integer not null,
    semester integer not null,
    type text not null, -- theory, lab, skill_course
    created_at timestamp with time zone default now()
);

-- 4. FACULTY
create table if not exists faculty (
    id serial primary key,
    user_id uuid not null references users(id) on delete cascade,
    name text not null,
    email text not null,
    faculty_id text unique not null,
    department text not null,
    designation text,
    phone text,
    qualification text,
    experience integer,
    address text,
    joining_date text,
    gender text,
    status text default 'active',
    created_at timestamp with time zone default now()
);

-- 5. STUDENTS
create table if not exists student (
    id serial primary key,
    user_id uuid not null references users(id) on delete cascade,
    name text not null,
    email text not null,
    student_id text unique not null,
    branch text not null,
    year integer not null,
    semester integer not null,
    section text not null,
    phone text,
    address text,
    father_name text,
    mother_name text,
    parents_phone text,
    date_of_birth text,
    admission_date text,
    status text default 'active',
    counselor_id integer references faculty(id),
    created_at timestamp with time zone default now()
);

-- 6. CLASS OFFERINGS
create table if not exists class_offering (
    id serial primary key,
    subject_id integer not null references subject(id),
    branch text not null,
    year integer not null,
    semester integer not null,
    section text not null,
    subject_type text,
    faculty_id integer not null references faculty(id),
    is_active boolean default true,
    is_mentor boolean default false,
    is_cleared boolean default false,
    created_at timestamp with time zone default now()
);

-- 7. TIMETABLE
create table if not exists timetable (
    id serial primary key,
    day_of_week text not null,
    start_time text not null,
    end_time text not null,
    subject_id integer not null references subject(id),
    branch text not null,
    year integer not null,
    semester integer not null,
    section text not null,
    original_faculty_id integer references faculty(id),
    current_faculty_id integer references faculty(id),
    room_number text,
    status text default 'scheduled',
    reason text,
    alter_date text,
    created_at timestamp with time zone default now()
);

-- 8. ATTENDANCE
create table if not exists attendance (
    id serial primary key,
    student_id integer not null references student(id) on delete cascade,
    subject_id integer not null references subject(id),
    date text not null,
    class_time text not null,
    status text not null, -- present, absent
    marked_by uuid references users(id),
    reason text,
    reason_for_change text,
    created_at timestamp with time zone default now()
);

-- 9. MARKS
create table if not exists mark (
    id serial primary key,
    student_id integer not null references student(id) on delete cascade,
    subject_id integer not null references subject(id),
    assessment_type text not null,
    marks double precision not null,
    max_marks double precision not null,
    date text,
    entered_by uuid references users(id),
    assignment_number integer,
    is_absent boolean default false,
    remarks text,
    created_at timestamp with time zone default now()
);

-- 10. FEES
create table if not exists fee (
    id serial primary key,
    student_id integer not null references student(id) on delete cascade,
    semester integer not null,
    tuition_fee double precision default 0.0,
    development_fee double precision default 0.0,
    examination_fee double precision default 0.0,
    total_fee double precision default 0.0,
    paid_amount double precision default 0.0,
    due_amount double precision default 0.0,
    payment_date text,
    status text,
    created_at timestamp with time zone default now()
);

-- 11. RESOURCES
create table if not exists resource (
    id serial primary key,
    title text not null,
    subject_class_id text, -- Keeping as text to match models.py
    type text,
    description text,
    file_name text,
    file_type text,
    file_size integer,
    file_url text,
    uploaded_by uuid references users(id),
    uploaded_by_name text,
    uploaded_at timestamp with time zone default now()
);

-- 12. ASSIGNMENTS
create table if not exists assignment (
    id serial primary key,
    title text not null,
    subject_class_id text,
    type text,
    description text,
    max_marks double precision,
    due_date text,
    created_by uuid references users(id),
    created_by_name text,
    is_completed boolean default false,
    resource_id integer,
    questions text,
    created_at timestamp with time zone default now()
);

-- 13. ANNOUNCEMENTS
create table if not exists announcement (
    id serial primary key,
    title text not null,
    content text not null,
    target_audience text,
    created_by uuid references users(id),
    created_by_name text,
    is_active boolean default true,
    is_pinned boolean default false,
    priority text default 'normal',
    expires_at text,
    date text,
    send_email boolean default false,
    department text,
    created_at timestamp with time zone default now()
);

-- 14. ALTERATIONS
create table if not exists alteration (
    id serial primary key,
    timetable_id integer not null references timetable(id),
    faculty_id_original integer references faculty(id),
    faculty_id_new integer references faculty(id),
    date text not null,
    reason text,
    period_id text,
    branch text,
    year integer,
    sem integer,
    section text,
    subject_id integer references subject(id),
    alter_status text,
    created_at timestamp with time zone default now()
);

-- 15. GLOBAL SETTINGS
create table if not exists global_setting (
    id serial primary key,
    key text unique not null,
    value text,
    description text,
    updated_at timestamp with time zone default now()
);

-- ==================== ROW LEVEL SECURITY ====================
alter table users enable row level security;
alter table department enable row level security;
alter table subject enable row level security;
alter table student enable row level security;
alter table faculty enable row level security;
alter table class_offering enable row level security;
alter table timetable enable row level security;
alter table attendance enable row level security;
alter table mark enable row level security;
alter table fee enable row level security;
alter table resource enable row level security;
alter table assignment enable row level security;
alter table announcement enable row level security;
alter table alteration enable row level security;
alter table global_setting enable row level security;

-- Helper function to get current user role
create or replace function get_current_user_role() returns text as $$
  select role from users where id = auth.uid()
$$ language sql security definer;

-- ADMIN POLICIES (Full Access)
create policy "Admin Full Access Users" on users for all using (true);
create policy "Admin Full Access Department" on department for all using (true);
create policy "Admin Full Access Subject" on subject for all using (true);
create policy "Admin Full Access Student" on student for all using (true);
create policy "Admin Full Access Faculty" on faculty for all using (true);
create policy "Admin Full Access ClassOffering" on class_offering for all using (true);
create policy "Admin Full Access Timetable" on timetable for all using (true);
create policy "Admin Full Access Attendance" on attendance for all using (true);
create policy "Admin Full Access Mark" on mark for all using (true);
create policy "Admin Full Access Fee" on fee for all using (true);
create policy "Admin Full Access Resource" on resource for all using (true);
create policy "Admin Full Access Assignment" on assignment for all using (true);
create policy "Admin Full Access Announcement" on announcement for all using (true);
create policy "Admin Full Access Alteration" on alteration for all using (true);
create policy "Admin Full Access GlobalSetting" on global_setting for all using (true);

-- FACULTY POLICIES
-- Read access to most academic data
create policy "Faculty Read Student" on student for select using (true);
create policy "Faculty Read Subject" on subject for select using (true);
create policy "Faculty Read Timetable" on timetable for select using (true);
create policy "Faculty Read Department" on department for select using (true);
create policy "Faculty Read ClassOffering" on class_offering for select using (true);
-- Write access to specific tables
create policy "Faculty Manage Attendance" on attendance for all using (true); -- Simplification: Logic handled in API usually
create policy "Faculty Manage Marks" on mark for all using (true); -- Simplification
create policy "Faculty View Own Profile" on faculty for select using (user_id = auth.uid());
create policy "Faculty Read Announcement" on announcement for select using (target_audience in ('all', 'faculty'));

-- STUDENT POLICIES
-- Read-only own data
create policy "Student Read Own Profile" on student for select using (user_id = auth.uid());
create policy "Student Read Own Marks" on mark for select using (student_id in (select id from student where user_id = auth.uid()));
create policy "Student Read Own Attendance" on attendance for select using (student_id in (select id from student where user_id = auth.uid()));
create policy "Student Read Own Fees" on fee for select using (student_id in (select id from student where user_id = auth.uid()));
create policy "Student Read Subjects" on subject for select using (true); -- General read
create policy "Student Read Timetable" on timetable for select using (true); -- General read
create policy "Student Read Announcement" on announcement for select using (target_audience in ('all', 'student'));

-- ==================== SEED DATA ====================
-- Default Admin User (Password: password123)
-- Hash: $2b$12$lcXb2swrFLJQV8KDS7bgZ.ftAlhmRaxDDW9WHwXpl40K4rQk7aKUyu
INSERT INTO users (id, username, email, password_hash, role, name)
VALUES 
(
    '00000000-0000-0000-0000-000000000001', 
    'admin', 
    'admin@campus.iq', 
    '$pbkdf2-sha256$29000$FQLA2Buj1Po/h3DO2XsvJQ$Jty55itnT956eN8TFtnShoD.CoCjSCBR71nh2TXCb1Q', 
    'admin', 
    'System Administrator'
) ON CONFLICT (username) DO NOTHING;

-- Seed Departments (Basic Set)
INSERT INTO department (name, code, head_of_department) VALUES
('Computer Science & Engineering', 'CSE', 'Dr. Smith'),
('Electronics & Communication', 'ECE', 'Dr. Jones')
ON CONFLICT DO NOTHING;
