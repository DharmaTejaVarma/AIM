from fastapi import APIRouter, Depends, Request, HTTPException
from ..supabase_client import get_supabase
from ..dependencies import get_current_student
from datetime import datetime, timedelta
from ..utils import (
    templates, 
    process_semester_marks, 
    calculate_cgpa, 
    deduplicate_marks, 
    calculate_subject_internal_marks
)
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/student", tags=["Student"])

# Helper for wrapping dicts to objects (for template compatibility)
class ObjWrapper:
    def __init__(self, d):
        for k, v in d.items():
            if isinstance(v, dict):
                setattr(self, k, ObjWrapper(v))
            elif isinstance(v, list):
                setattr(self, k, [ObjWrapper(i) if isinstance(i, dict) else i for i in v])
            else:
                setattr(self, k, v)
    def __getitem__(self, item): return getattr(self, item)
    def get(self, item, default=None): return getattr(self, item, default)

@router.get("/dashboard", name="student.dashboard")
async def dashboard(request: Request, user: dict = Depends(get_current_student)):
    supabase = get_supabase()
    
    # 1. Profile
    s_res = supabase.table("student").select("*").eq("user_id", user['user_id']).execute()
    if not s_res.data: raise HTTPException(status_code=404, detail="Student Profile Not Found")
    student = s_res.data[0]
    
    # 2. Fees
    fee_res = supabase.table("fee").select("due_amount").eq("student_id", student['id']).execute()
    pending_fees = sum([f['due_amount'] for f in fee_res.data]) if fee_res.data else 0
    
    # 3. Overall Attendance
    att_res = supabase.table("attendance").select("status").eq("student_id", student['id']).execute()
    total = len(att_res.data)
    present = len([a for a in att_res.data if a['status'] == 'present'])
    overall_attendance = round((present / total * 100), 1) if total > 0 else 0
    
    # 4. CGPA & Credits
    subjects = supabase.table("subject").select("*").eq("branch", student['branch']).execute().data
    marks = supabase.table("mark").select("*").eq("student_id", student['id']).execute().data
    
    semester_data = process_semester_marks(student['id'], subjects, marks)
    cgpa_data = calculate_cgpa(semester_data)
    
    current_cgpa = cgpa_data['cgpa']
    credits_completed = cgpa_data['earned_credits']

    # --- Conditional CGPA Logic ---
    # User Request: Show Final CGPA only if ALL subject external marks are entered.
    # We check subjects up to the current semester.
    # If any theory/lab subject is missing an 'External' mark, we hide the CGPA.
    
    # 1. Identify relevant subjects (up to current year/sem)
    relevant_subjects = [
        s for s in subjects 
        if (s['year'] < student['year']) or 
           (s['year'] == student['year'] and s['semester'] <= student['semester'])
    ]
    
    # 2. Check for missing external marks
    all_externals_present = True
    for sub in relevant_subjects:
        # User requirement: All subjects must have external marks.
        # Removed type exclusions to ensure strict compliance.
        
        has_ext = any(
            m['subject_id'] == sub['id'] and 
            m['assessment_type'] == 'External' 
            for m in marks
        )
        
        if not has_ext:
            all_externals_present = False
            break
            
    if not all_externals_present:
        current_cgpa = None
    # ------------------------------
    
    # 5. Today's Classes (with Alterations)
    today_name = datetime.now().strftime('%A')
    today_date = datetime.now().strftime('%Y-%m-%d')
    
    # Fetch Timetable
    timetable_res = supabase.table("timetable").select("*, subject(*), original_faculty:original_faculty_id(name), current_faculty:current_faculty_id(name)").match({
        "branch": student['branch'], "year": student['year'], "semester": student['semester'], "section": student['section'],
        "day_of_week": today_name
    }).order("start_time").execute()
    
    todays_classes = []
    
    # Optimzied Alterations fetch
    alt_res = supabase.table("alteration").select("*").eq("date", today_date).eq("section", student['section']).execute()
    alterations = {a['timetable_id']: a for a in alt_res.data}
    
    for entry in timetable_res.data:
        is_suspended = False
        faculty_name = entry['original_faculty']['name'] if entry.get('original_faculty') else "Unknown"
        room = entry.get('room_number', '')
        subject_name = entry['subject']['name'] if entry.get('subject') else "Unknown"
        subject_code = entry['subject']['code'] if entry.get('subject') else ""
        subject_type = entry['subject'].get('type', 'Lecture') if entry.get('subject') else "Lecture"
        
        # Check active alteration
        if entry['id'] in alterations:
            alt = alterations[entry['id']]
            if alt['alter_status'] == 'suspended':
                is_suspended = True
            elif alt['alter_status'] == 'altered':
                 if alt.get('faculty_id_new'):
                     f_new = supabase.table("faculty").select("name").eq("id", alt['faculty_id_new']).single().execute()
                     if f_new and f_new.data: faculty_name = f_new.data['name']
        
        if not is_suspended:
            # Duration logic
            try:
                start_dt = datetime.strptime(entry['start_time'], '%H:%M:%S')
                end_dt = datetime.strptime(entry['end_time'], '%H:%M:%S')
                duration = int((end_dt - start_dt).total_seconds() // 60)
            except:
                duration = 0
            
            # Attendance Status
            my_att = supabase.table("attendance").select("status").match({
                "student_id": student['id'],
                "subject_id": entry['subject_id'],
                "date": today_date
            }).maybe_single().execute()
            
            att_status = my_att.data['status'].capitalize() if (my_att and my_att.data) else "Not Marked"
            
            todays_classes.append({
                'subject': subject_name,
                'subject_code': subject_code,
                'subject_type': subject_type.capitalize(),
                'room': room,
                'faculty': faculty_name,
                'time': f"{entry['start_time']} - {entry['end_time']}",
                'duration': f"{duration} mins",
                'attendance_status': att_status
            })
            
    # 6. Recent Updates
    recent_updates = []
    rec_att = supabase.table("attendance").select("*, subject(name)").eq("student_id", student['id']).order("date", desc=True).limit(3).execute()
    for a in rec_att.data:
        recent_updates.append({
            'icon': '✅',
            'title': 'Attendance Marked',
            'description': f"{a['subject']['name']}: {a['status']}",
            'time': a['date']
        })
        
    rec_marks = supabase.table("mark").select("*, subject(name)").eq("student_id", student['id']).order("created_at", desc=True).limit(3).execute()
    for m in rec_marks.data:
        recent_updates.append({
            'icon': '💯',
            'title': 'Marks Updated',
            'description': f"{m['subject']['name']}: {m['marks']}/{m['max_marks']}",
            'time': m.get('date', 'Recently')
        })
        
    ann_res = supabase.table("announcement").select("*").or_("target_audience.eq.student,target_audience.eq.all").order("created_at", desc=True).limit(20).execute()
    filtered_anns = []
    for ann in ann_res.data:
        dept = ann.get('department')
        if not dept or dept.lower() == 'all' or dept == student['branch']:
            filtered_anns.append(ann)
            
    for ann in filtered_anns[:3]:
        recent_updates.append({
            'icon': '📣',
            'title': 'Announcement',
            'description': ann['title'],
            'time': ann['date']
        })
        
    recent_updates.sort(key=lambda x: str(x['time']), reverse=True)
    recent_updates = recent_updates[:5]
    
    # 7. Subject Attendance Chart
    subject_attendance = {}
    current_subs = supabase.table("subject").select("*").match({
        "branch": student['branch'], "semester": student['semester']
    }).execute().data
    
    subject_attendance = {} # Keep as dict for backward compat if needed, or change to list?
    # Template uses .items(), so dict is expected. But we need ID.
    # Let's change the template logic.
    # New structure: {'Subject Name': {'id': 1, 'percentage': 80}}
    
    for sub in current_subs:
        s_res = supabase.table("attendance").select("status").match({"student_id": student['id'], "subject_id": sub['id']}).execute()
        recs = s_res.data
        if recs:
            p = len([r for r in recs if r['status'] == 'present'])
            pct = round(p / len(recs) * 100)
            subject_attendance[sub['name']] = {'id': sub['id'], 'percentage': pct}
        else:
            subject_attendance[sub['name']] = {'id': sub['id'], 'percentage': 0}
            
    # 8. Upcoming Events
    today_str = datetime.now().strftime('%Y-%m-%d')
    # No FKs, so just select * from assignment
    ass_res = supabase.table("assignment").select("*").gte("due_date", today_str).order("due_date").execute()
    
    upcoming_events = []
    # Map subject names from current_subs
    sub_map_name = {str(s['id']): s['name'] for s in current_subs}

    for ass in ass_res.data:
        # Determine subject name
        s_name = "Unknown"
        if ass.get('subject_class_id') and str(ass.get('subject_class_id')) in sub_map_name:
            s_name = sub_map_name[str(ass.get('subject_class_id'))]
        
        upcoming_events.append({
            'title': ass['title'],
            'subject': s_name,
            'date': ass['due_date']
        })
        
    student_obj = ObjWrapper(student)
    user_obj = ObjWrapper(user)
    setattr(user_obj, 'student_profile', student_obj)
    if not getattr(user_obj, 'name', None):
         setattr(user_obj, 'name', student.get('name', 'Student'))
    
    return templates.TemplateResponse("student/student-dashboard.html", {
        "request": request,
        "user": user_obj,
        "student": student_obj,
        "new_updates_count": 0,
        "pending_fees": pending_fees,
        "overall_attendance": overall_attendance,
        "current_cgpa": current_cgpa,
        "credits_completed": credits_completed,
        "todays_classes": todays_classes,
        "recent_updates": recent_updates,
        "subject_attendance": subject_attendance,
        "upcoming_events": upcoming_events[:5],
        "announcements": filtered_anns[:5],
        "today_date": datetime.now().strftime('%A, %B %d, %Y'),
        "today_day": today_name,
        "new_updates_count": len(recent_updates)
    })

@router.get("/profile", name="student.profile")
async def profile(request: Request, user: dict = Depends(get_current_student)):
    supabase = get_supabase()
    s_res = supabase.table("student").select("*").eq("user_id", user['user_id']).execute()
    student = s_res.data[0]
    print(f"DEBUG: Student attributes: {student.keys()}")
    
    subjects = supabase.table("subject").select("*").eq("branch", student['branch']).execute().data
    marks = supabase.table("mark").select("*").eq("student_id", student['id']).execute().data
    att_res = supabase.table("attendance").select("status").eq("student_id", student['id']).execute().data
    
    semester_data = process_semester_marks(student['id'], subjects, marks)
    cgpa_data = calculate_cgpa(semester_data)
    
    total = len(att_res)
    present = len([a for a in att_res if a['status'] == 'present'])
    att_pct = round(present/total*100, 1) if total > 0 else 0
    
    academic_summary = {
        'cgpa': cgpa_data['cgpa'],
        'total_credits': cgpa_data['total_credits'],
        'earned_credits': cgpa_data['earned_credits'],
        'attendance_percentage': att_pct,
        'backlogs': cgpa_data['backlogs']
    }
    
    user_obj = ObjWrapper(user)
    student_obj = ObjWrapper(student)
    setattr(user_obj, 'student_profile', student_obj)
    if not getattr(user_obj, 'name', None): setattr(user_obj, 'name', student.get('name', 'Student'))

    return templates.TemplateResponse("student/student-profile.html", {
        "request": request,
        "user": user_obj,
        "student": student_obj,
        "new_updates_count": 0,
        "semester_data": semester_data,
        "academic": academic_summary
    })

@router.get("/attendance", name="student.attendance")
async def attendance(request: Request, user: dict = Depends(get_current_student)):
    supabase = get_supabase()
    s_res = supabase.table("student").select("*").eq("user_id", user['user_id']).execute()
    student = s_res.data[0]
    
    user_obj = ObjWrapper(user)
    student_obj = ObjWrapper(student)
    setattr(user_obj, 'student_profile', student_obj)
    if not getattr(user_obj, 'name', None): setattr(user_obj, 'name', student.get('name', 'Student'))
    
    return templates.TemplateResponse("student/student-attendance.html", {
        "request": request,
        "user": user_obj,
        "student": student_obj,
        "new_updates_count": 0
    })

@router.get("/attendance/subject/{subject_id}", name="student.attendance_detail")
async def attendance_detail(subject_id: int, request: Request, user: dict = Depends(get_current_student)):
    supabase = get_supabase()
    s_res = supabase.table("student").select("*").eq("user_id", user['user_id']).execute()
    student = s_res.data[0]
    
    # Subject Info
    sub_res = supabase.table("subject").select("*").eq("id", subject_id).single().execute()
    if not sub_res.data: raise HTTPException(status_code=404, detail="Subject not found")
    subject = sub_res.data

    # Attendance Logs
    att_res = supabase.table("attendance").select("*").match({
        "student_id": student['id'],
        "subject_id": subject_id
    }).order("date", desc=True).execute()
    logs = att_res.data or []
    
    # Stats
    total = len(logs)
    present = len([r for r in logs if r['status'].lower() == 'present'])
    absent = len([r for r in logs if r['status'].lower() == 'absent'])
    percentage = round((present / total * 100), 1) if total > 0 else 0
    
    stats = {
        "total": total,
        "present": present,
        "absent": absent,
        "percentage": percentage
    }
    
    # Format logs
    periods_map = {
        1: {'start': '09:15', 'end': '10:05'},
        2: {'start': '10:05', 'end': '10:55'},
        3: {'start': '10:55', 'end': '11:45'},
        4: {'start': '11:45', 'end': '12:35'},
        5: {'start': '13:30', 'end': '14:20'},
        6: {'start': '14:20', 'end': '15:10'},
        7: {'start': '15:10', 'end': '16:00'}
    }

    formatted_logs = []
    for l in logs:
        # Determine Time Range
        p_num = l.get('period_number')
        time_display = "Unknown"
        
        print(f"DEBUG: Date={l['date']}, PeriodNum={p_num} (Type: {type(p_num)}), ClassTime={l.get('class_time')}")
        
        if p_num and p_num in periods_map:
            time_display = f"{periods_map[p_num]['start']} - {periods_map[p_num]['end']}"
        else:
            # Fallback: Try to infer from class_time
            ct_raw = str(l.get('class_time', ''))
            ct = ct_raw[:5] if len(ct_raw) >= 5 else ct_raw
            
            # 1. Reverse lookup in map
            found_period = None
            for pid, times in periods_map.items():
                if times['start'] == ct:
                    found_period = times
                    break
            
            if found_period:
                time_display = f"{found_period['start']} - {found_period['end']}"
            elif ct:
                # 2. Manual calculation (add 50 mins)
                try:
                    start_dt = datetime.strptime(ct, '%H:%M')
                    end_dt = start_dt + timedelta(minutes=50)
                    time_display = f"{ct} - {end_dt.strftime('%H:%M')}"
                except:
                    time_display = ct
            else:
                 time_display = f"Period {p_num}" if p_num else "Unknown"
        
        formatted_logs.append({
            "date": l['date'],
            "time": time_display,
            "status": l['status'],
            "reason": l.get('reason')
        })

    user_obj = ObjWrapper(user)
    student_obj = ObjWrapper(student)
    setattr(user_obj, 'student_profile', student_obj)
    if not getattr(user_obj, 'name', None): setattr(user_obj, 'name', student.get('name', 'Student'))

    return templates.TemplateResponse("student/student-attendance-detail.html", {
        "request": request,
        "user": user_obj,
        "student": student_obj,
        "subject": subject,
        "stats": stats,
        "logs": formatted_logs,
        "today": datetime.now().strftime('%A, %B %d, %Y'),
        "new_updates_count": 0
    })

@router.post("/attendance/fetch", name="student.fetch_attendance_data")
async def fetch_attendance_data(request: Request, user: dict = Depends(get_current_student)):
    supabase = get_supabase()
    s_res = supabase.table("student").select("*").eq("user_id", user['user_id']).execute()
    student = s_res.data[0]
    
    # 1. Overall Stats
    total_recs = supabase.table("attendance").select("*, subject(name)").eq("student_id", student['id']).execute().data
    total = len(total_recs)
    present = len([r for r in total_recs if r['status'] == 'present'])
    absent = len([r for r in total_recs if r['status'] == 'absent'])
    overall = round((present/total*100), 1) if total > 0 else 0
    
    # 2. Subject-wise
    # Get subjects from class_offering or basic filter
    subjects = supabase.table("subject").select("*").match({
        "branch": student['branch'], "semester": student['semester']
    }).execute().data
    
    subject_stats = []
    for sub in subjects:
        sub_recs = [r for r in total_recs if r['subject_id'] == sub['id']]
        s_total = len(sub_recs)
        s_present = len([r for r in sub_recs if r['status'] == 'present'])
        s_absent = len([r for r in sub_recs if r['status'] == 'absent'])
        s_pct = round((s_present/s_total*100), 1) if s_total > 0 else 0
        
        status_label = "Good"
        if s_pct < 75: status_label = "Low"
        
        subject_stats.append({
            'subject_id': sub['id'],
            'subject_name': sub['name'],
            'subject_code': sub['code'],
            'total': s_total,
            'present': s_present,
            'absent': s_absent,
            'percentage': s_pct,
            'status': status_label
        })
        
    # 3. Calendar Data
    logs = [{
        'date': r['date'],
        'subject': r['subject']['name'] if r.get('subject') else 'Unknown',
        'status': r['status'].capitalize(),
        'reason': r.get('reason'),
        'marked_by': 'Faculty'
    } for r in total_recs]
    
    return {
        "stats": {
            "overall": overall,
            "total": total,
            "present": present,
            "absent": absent
        },
        "subject_wise": subject_stats,
        "logs": logs
    }

@router.get("/marks", name="student.marks")
async def marks(request: Request, user: dict = Depends(get_current_student)):
    supabase = get_supabase()
    s_res = supabase.table("student").select("*").eq("user_id", user['user_id']).execute()
    student = s_res.data[0]
    user_obj = ObjWrapper(user)
    student_obj = ObjWrapper(student)
    setattr(user_obj, 'student_profile', student_obj)
    if not getattr(user_obj, 'name', None): setattr(user_obj, 'name', student.get('name', 'Student'))

    return templates.TemplateResponse("student/student-marks.html", {
        "request": request,
        "user": user_obj,
        "student": student_obj,
        "new_updates_count": 0
    })

@router.post("/marks/fetch", name="student.fetch_marks_data")
async def fetch_marks_data(request: Request, user: dict = Depends(get_current_student)):
    supabase = get_supabase()
    s_res = supabase.table("student").select("*").eq("user_id", user['user_id']).execute()
    student = s_res.data[0]
    
    all_marks = supabase.table("mark").select("*").eq("student_id", student['id']).execute().data
    subjects = supabase.table("subject").select("*").eq("branch", student['branch']).execute().data
    
    # Check publication setting
    setting = supabase.table("global_setting").select("value").eq("key", "show_external_marks").maybe_single().execute()
    published = True
    if setting and setting.data:
        val = str(setting.data['value']).strip().lower()
        print(f"DEBUG: show_external_marks value: '{val}'")
        if val == 'false':
            published = False
    
    semester_data = process_semester_marks(student['id'], subjects, all_marks, published=published)
    
    current_max_sem = (student['year'] - 1) * 2 + student['semester']
    filtered_semester_data = {k: v for k, v in semester_data.items() if k <= current_max_sem}
    semester_data = filtered_semester_data
    
    cgpa_data = calculate_cgpa(semester_data)
    
    # Calculate overall percentage (CGPA * 9.5)
    overall_pct = round((cgpa_data['cgpa'] * 9.5), 2)
        
    return {
        "stats": {
            "cgpa": cgpa_data['cgpa'],
            "earned_credits": cgpa_data['earned_credits'],
            "total_credits": cgpa_data['total_credits'],
            "overall_percentage": overall_pct,
            "backlogs": cgpa_data['backlogs']
        },
        "semester_data": semester_data
    }

@router.get("/marks/subject/{subject_id}", name="student.subject_marks_detail")
async def subject_marks_detail(subject_id: int, request: Request, user: dict = Depends(get_current_student)):
    supabase = get_supabase()
    s_res = supabase.table("student").select("*").eq("user_id", user['user_id']).execute()
    student = s_res.data[0]
    
    # Get Subject
    sub_res = supabase.table("subject").select("*").eq("id", subject_id).single().execute()
    if not sub_res.data: raise HTTPException(status_code=404, detail="Subject not found")
    subject = sub_res.data
    
    # Fetch Marks
    marks_raw = supabase.table("mark").select("*").eq("student_id", student['id']).eq("subject_id", subject_id).order("date", desc=True).execute().data
    
    marks = deduplicate_marks(marks_raw)
    
    # Calculate Internals
    internal_data = calculate_subject_internal_marks(subject_id, marks, subject.get('type'), {})
    
    # Check Global Settings
    show_ext = True
    setting = supabase.table("global_setting").select("value").eq("key", "show_external_marks").maybe_single().execute()
    if setting and setting.data:
        val = str(setting.data['value']).strip().lower()
        if val == 'false':
            show_ext = False
        
    external_record = next((m for m in marks if m['assessment_type'] == 'External'), None)
    external_marks = external_record['marks'] if (external_record and show_ext) else None
    
    if not show_ext:
        marks = [m for m in marks if m['assessment_type'] != 'External']
        
    user_obj = ObjWrapper(user)
    student_obj = ObjWrapper(student)
    setattr(user_obj, 'student_profile', student_obj)
    if not getattr(user_obj, 'name', None): setattr(user_obj, 'name', student.get('name', 'Student'))

    return templates.TemplateResponse("student/student-subject-details.html", {
        "request": request,
        "user": user_obj,
        "student": student_obj,
        "new_updates_count": 0,
        "subject": subject,
        "internal_data": internal_data,
        "external_marks": external_marks,
        "marks": marks
    })

@router.get("/timetable", name="student.timetable")
async def timetable(request: Request, user: dict = Depends(get_current_student)):
    supabase = get_supabase()
    s_res = supabase.table("student").select("*").eq("user_id", user['user_id']).execute()
    student = s_res.data[0]
    
    user_obj = ObjWrapper(user)
    student_obj = ObjWrapper(student)
    setattr(user_obj, 'student_profile', student_obj)
    if not getattr(user_obj, 'name', None): setattr(user_obj, 'name', student.get('name', 'Student'))

    return templates.TemplateResponse("student/student-timetable.html", {
        "request": request,
        "user": user_obj,
        "student": student_obj,
        "new_updates_count": 0
    })

class FetchTimetableRequest(BaseModel):
    date: str

@router.post("/timetable/fetch", name="student.fetch_timetable")
async def fetch_timetable(req: FetchTimetableRequest, user: dict = Depends(get_current_student)):
    supabase = get_supabase()
    s_res = supabase.table("student").select("*").eq("user_id", user['user_id']).execute()
    student = s_res.data[0]
    
    date_str = req.date
    
    # --- Semester Validation ---
    sem_res = supabase.table("semester").select("*").eq("status", "Active").execute()
    active_semesters = sem_res.data or []
    
    is_allowed = False
    validation_msg = "Timetable View Disabled. No active semester found."
    
    if active_semesters:
        validation_msg = "Timetable View Disabled. Date outside active semester."
        for sem in active_semesters:
            if sem['start_date'] <= date_str <= sem['end_date']:
                is_allowed = True
                validation_msg = ""
                break
            elif date_str < sem['start_date']:
                validation_msg = f"Timetable not available. Semester '{sem['name']}' starts {sem['start_date']}."
            elif date_str > sem['end_date']:
                 validation_msg = f"Timetable disabled. Semester '{sem['name']}' ended {sem['end_date']}."
    
    if not is_allowed:
         return {
            "days": [], "periods": [], "timetable": {}, 
            "semester_validation": { "allowed": False, "message": validation_msg }
        }
    # --- End Validation ---

    try:
        if not date_str:
            raise ValueError("Empty date")
        view_date = datetime.strptime(date_str, '%Y-%m-%d')
    except (ValueError, TypeError):
        view_date = datetime.now()
    start_of_week = view_date - timedelta(days=view_date.weekday())
    
    week_dates = {}
    days_map = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    for i, day_name in enumerate(days_map):
        day_date = start_of_week + timedelta(days=i)
        week_dates[day_name] = day_date.strftime('%Y-%m-%d')
        
    # Fetch entries
    entries = supabase.table("timetable").select("*, subject(*), original_faculty:original_faculty_id(name), current_faculty:current_faculty_id(name)").match({
        "branch": student['branch'], "year": student['year'], "semester": student['semester'], "section": student['section']
    }).execute().data
    
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    periods = [
        {'start': '09:15', 'end': '10:05', 'label': 'P1'},
        {'start': '10:05', 'end': '10:55', 'label': 'P2'},
        {'start': '10:55', 'end': '11:45', 'label': 'P3'},
        {'start': '11:45', 'end': '12:35', 'label': 'P4'},
        {'start': '13:30', 'end': '14:20', 'label': 'P5'},
        {'start': '14:20', 'end': '15:10', 'label': 'P6'},
        {'start': '15:10', 'end': '16:00', 'label': 'P7'}
    ]
    
    timetable_data = {day: {} for day in days}
    
    for entry in entries:
        if entry['day_of_week'] not in days: continue
        
        target_date_str = week_dates.get(entry['day_of_week'])
        
        is_relevant_alteration = False
        if entry.get('alter_date') and str(entry['alter_date']) == target_date_str:
            is_relevant_alteration = True
            
        status = 'scheduled'
        reason = ''
        faculty_name = entry['original_faculty']['name'] if entry.get('original_faculty') else "Unknown"
        
        if is_relevant_alteration:
            status = entry.get('status', 'scheduled')
            reason = entry.get('reason', '')
            if status == 'suspended':
                faculty_name = "Suspended"
            elif status == 'altered' and entry.get('current_faculty'):
                faculty_name = entry['current_faculty']['name']
                
        subject_name = entry['subject']['name'] if entry.get('subject') else "Unknown"
        type_ = entry['subject']['type'] if entry.get('subject') else "Lecture"
        
        # Match time slot
        try:
            entry_start = datetime.strptime(entry['start_time'], '%H:%M:%S').time()
            entry_end = datetime.strptime(entry['end_time'], '%H:%M:%S').time()
        except:
            # Fallback for HH:MM
             entry_start = datetime.strptime(entry['start_time'], '%H:%M').time()
             entry_end = datetime.strptime(entry['end_time'], '%H:%M').time()
             
        for period in periods:
            p_start = datetime.strptime(period['start'], '%H:%M').time()
            if entry_start <= p_start < entry_end:
                 if period['start'] not in timetable_data[entry['day_of_week']]:
                     timetable_data[entry['day_of_week']][period['start']] = {'entries': []}
                
                 timetable_data[entry['day_of_week']][period['start']]['entries'].append({
                    'id': entry['id'],
                    'subject_name': subject_name,
                    'faculty_name': faculty_name,
                    'room': entry.get('room_number', ''),
                    'status': status,
                    'reason': reason,
                    'branch': entry['branch'],
                    'year': entry['year'],
                    'section': entry['section'],
                    'type': type_
                 })
                 
    return {"days": days, "periods": periods, "timetable": timetable_data}

@router.get("/resources", name="student.resources")
async def resources(request: Request, user: dict = Depends(get_current_student)):
    supabase = get_supabase()
    s_res = supabase.table("student").select("*").eq("user_id", user['user_id']).execute()
    student = s_res.data[0]
    
    user_obj = ObjWrapper(user)
    student_obj = ObjWrapper(student)
    # Ensure profile is attached
    setattr(user_obj, 'student_profile', student_obj)
    if not getattr(user_obj, 'name', None): setattr(user_obj, 'name', student.get('name', 'Student'))

    return templates.TemplateResponse("student/student-resources.html", {
        "request": request,
        "user": user_obj,
        "student": student_obj,
        "new_updates_count": 0
    })

@router.post("/resources/fetch", name="student.fetch_resources_data")
async def fetch_resources_data(request: Request, user: dict = Depends(get_current_student)):
    supabase = get_supabase()
    s_res = supabase.table("student").select("*").eq("user_id", user['user_id']).execute()
    student = s_res.data[0]
    
    # 1. Get Subjects
    subjects = supabase.table("subject").select("*").match({
        "branch": student['branch'], "year": student['year'], 
        "semester": student['semester']
    }).execute().data
    
    subject_map = {str(s['id']): s['name'] for s in subjects}
    
    # 2. Get Resources
    # Optimize: filtering by Python for now due to text ID match
    all_res = supabase.table("resource").select("*").order("uploaded_at", desc=True).execute().data
    
    filtered_resources = []
    for r in all_res:
        if str(r.get('subject_class_id')) in subject_map:
            filtered_resources.append({
                'id': r['id'],
                'title': r['title'],
                'subject': subject_map[str(r['subject_class_id'])],
                'type': r['type'],
                'uploaded_by': r.get('uploaded_by_name', 'Faculty'),
                'date': r['uploaded_at'][:10] if r.get('uploaded_at') else '-',
                'file_name': r.get('file_name')
            })
            
    return {
        "resources": filtered_resources,
        "subjects": [{'id': s['id'], 'name': s['name']} for s in subjects]
    }

@router.get("/resources/download/{resource_id}", name="student.download_resource")
async def download_resource(resource_id: int, inline: bool = False, user: dict = Depends(get_current_student)):
    supabase = get_supabase()
    res = supabase.table("resource").select("*").eq("id", resource_id).single().execute()
    if not res.data: return "Not Found", 404
    record = res.data
    
    import os
    from starlette.responses import FileResponse
    path = os.path.join(os.getcwd(), 'static', 'uploads', record['file_name'])
    
    if not os.path.exists(path): return "File missing", 404
    
    disposition = "inline" if inline else "attachment"
    
    # Explicitly handle text/plain for debug or logs, and PDF for preview
    import mimetypes
    media_type, _ = mimetypes.guess_type(path)
    
    ext = record['file_name'].split('.')[-1].lower()
    if ext == 'pdf': media_type = 'application/pdf'
    elif ext in ['jpg', 'jpeg']: media_type = 'image/jpeg'
    elif ext == 'png': media_type = 'image/png'
    elif ext == 'txt': media_type = 'text/plain'
        
    if inline:
        return FileResponse(path, media_type=media_type, content_disposition_type='inline')
    else:
        return FileResponse(path, filename=record['file_name'], media_type=media_type, content_disposition_type='attachment')

@router.get("/assignments", name="student.assignments")
async def assignments(request: Request, user: dict = Depends(get_current_student)):
    supabase = get_supabase()
    s_res = supabase.table("student").select("*").eq("user_id", user['user_id']).execute()
    student = s_res.data[0]
    
    user_obj = ObjWrapper(user)
    student_obj = ObjWrapper(student)
    setattr(user_obj, 'student_profile', student_obj)
    if not getattr(user_obj, 'name', None): setattr(user_obj, 'name', student.get('name', 'Student'))

    return templates.TemplateResponse("student/student-assignments.html", {
        "request": request,
        "user": user_obj,
        "student": student_obj,
        "new_updates_count": 0
    })

@router.post("/assignments/fetch", name="student.fetch_assignments_data")
async def fetch_assignments_data(request: Request, user: dict = Depends(get_current_student)):
    supabase = get_supabase()
    s_res = supabase.table("student").select("*").eq("user_id", user['user_id']).execute()
    student = s_res.data[0]
    
    subjects = supabase.table("subject").select("*").match({
        "branch": student['branch'], "year": student['year'], 
        "semester": student['semester']
    }).execute().data
    subject_map = {str(s['id']): s['name'] for s in subjects}
    
    all_ass = supabase.table("assignment").select("*").execute().data
    
    processed_assignments = []
    today_str = datetime.now().strftime('%Y-%m-%d')
    today_date_obj = datetime.now().date()
    
    for ass in all_ass:
        if str(ass.get('subject_class_id')) in subject_map:
            status = "active"
            due_date = ass.get('due_date')
            if due_date and due_date < today_str:
                status = "overdue"
            else:
                try:
                    if due_date:
                        d_date = datetime.strptime(due_date, '%Y-%m-%d').date()
                        if (d_date - today_date_obj).days > 7:
                            status = "upcoming"
                except: pass
                
            processed_assignments.append({
                'id': ass['id'],
                'title': ass['title'],
                'subject': subject_map[str(ass['subject_class_id'])],
                'due_date': due_date or '-',
                'max_marks': ass.get('max_marks'),
                'uploaded_by': ass.get('created_by_name', 'Faculty'),
                'uploaded_on': ass['created_at'][:10] if ass.get('created_at') else '-',
                'status': status
            })
            
    # Sort
    processed_assignments.sort(key=lambda x: x['due_date'] if x['due_date'] != '-' else '9999-12-31')
    
    return {
        "assignments": processed_assignments,
        "subjects": [{'id': s['id'], 'name': s['name']} for s in subjects]
    }

@router.get("/fees", name="student.fees")
async def fees(request: Request, user: dict = Depends(get_current_student)):
    supabase = get_supabase()
    s_res = supabase.table("student").select("*").eq("user_id", user['user_id']).execute()
    student = s_res.data[0]
    
    user_obj = ObjWrapper(user)
    student_obj = ObjWrapper(student)
    setattr(user_obj, 'student_profile', student_obj)
    if not getattr(user_obj, 'name', None): setattr(user_obj, 'name', student.get('name', 'Student'))

    return templates.TemplateResponse("student/student-fees.html", {
        "request": request,
        "user": user_obj,
        "student": student_obj,
        "new_updates_count": 0
    })

@router.post("/fees/fetch", name="student.fetch_fees_data")
async def fetch_fees_data(request: Request, user: dict = Depends(get_current_student)):
    supabase = get_supabase()
    s_res = supabase.table("student").select("*").eq("user_id", user['user_id']).execute()
    student = s_res.data[0]
    
    fees_res = supabase.table("fee").select("*").eq("student_id", student['id']).order("semester", desc=True).execute()
    
    total_due = sum(f['due_amount'] for f in fees_res.data)
    total_paid = sum(f['paid_amount'] for f in fees_res.data)
    
    return {
        "fees": fees_res.data,
        "summary": {"total_due": total_due, "total_paid": total_paid}
    }

@router.get("/marks/semester", name="student.semester_marks_view")
async def semester_marks_view(request: Request, user: dict = Depends(get_current_student)):
    supabase = get_supabase()
    s_res = supabase.table("student").select("*").eq("user_id", user['user_id']).execute()
    student = s_res.data[0]
    
    user_obj = ObjWrapper(user)
    student_obj = ObjWrapper(student)
    setattr(user_obj, 'student_profile', student_obj)
    if not getattr(user_obj, 'name', None): setattr(user_obj, 'name', student.get('name', 'Student'))

    return templates.TemplateResponse("student/student-semester-marks.html", {
        "request": request,
        "user": user_obj,
        "student": student_obj,
        "new_updates_count": 0
    })

@router.get("/assignments/details", name="student.assignment_details")
async def assignment_details(request: Request, user: dict = Depends(get_current_student)):
    supabase = get_supabase()
    s_res = supabase.table("student").select("*").eq("user_id", user['user_id']).execute()
    student = s_res.data[0]
    
    user_obj = ObjWrapper(user)
    student_obj = ObjWrapper(student)
    setattr(user_obj, 'student_profile', student_obj)
    if not getattr(user_obj, 'name', None): setattr(user_obj, 'name', student.get('name', 'Student'))

    return templates.TemplateResponse("student/student-assignment-details.html", {
        "request": request,
        "user": user_obj,
        "student": student_obj,
        "new_updates_count": 0,
        "announcements": []
    })

class AssignmentDetailsRequest(BaseModel):
    assignment_id: int

@router.post("/assignments/details/fetch", name="student.fetch_assignment_details_data")
async def fetch_assignment_details_data(req: AssignmentDetailsRequest, user: dict = Depends(get_current_student)):
    supabase = get_supabase()
    ass_res = supabase.table("assignment").select("*").eq("id", req.assignment_id).single().execute()
    if not ass_res.data: return {"error": "Assignment not found"}, 404
    ass = ass_res.data
    
    subject_name = "Unknown"
    if ass.get('subject_class_id'):
        sub_res = supabase.table("subject").select("name").eq("id", int(ass['subject_class_id'])).single().execute()
        if sub_res.data: subject_name = sub_res.data['name']
        
    file_name = None
    if ass.get('resource_id'):
        r_res = supabase.table("resource").select("file_name").eq("id", ass['resource_id']).single().execute()
        if r_res.data: file_name = r_res.data['file_name']
        
    questions = []
    if ass.get('questions'):
        try:
            import json
            questions = json.loads(ass['questions'])
        except: questions = []
        
    return {
        "assignment": {
            "id": ass['id'],
            "title": ass['title'],
            "subject": subject_name,
            "description": ass.get('description'),
            "type": ass.get('type'),
            "due_date": ass.get('due_date'),
            "max_marks": ass.get('max_marks'),
            "uploaded_by": ass.get('created_by_name', 'Faculty'),
            "uploaded_on": ass['created_at'][:10] if ass.get('created_at') else '-',
            "file_name": file_name,
            "questions": questions
        }
    }
    
from fastapi import Form
from fastapi.responses import RedirectResponse

@router.post("/update-profile", name="student.update_profile")
async def update_profile(
    request: Request,
    phone: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    father_name: Optional[str] = Form(None),
    mother_name: Optional[str] = Form(None),
    parents_phone: Optional[str] = Form(None),
    user: dict = Depends(get_current_student)
):
    supabase = get_supabase()
    s_res = supabase.table("student").select("*").eq("user_id", user['user_id']).execute()
    student = s_res.data[0]
    
    update_data = {}
    if phone: update_data['phone'] = phone
    if email: update_data['email'] = email
    if address: update_data['address'] = address
    if father_name: update_data['father_name'] = father_name
    if mother_name: update_data['mother_name'] = mother_name
    if parents_phone: update_data['parents_phone'] = parents_phone
    
    if update_data:
        supabase.table("student").update(update_data).eq("id", student['id']).execute()
        
    if email:
        # Also update users table email
        supabase.table("users").update({"email": email}).eq("id", user['user_id']).execute()
        
    # Redirect back to profile with success query param
    return RedirectResponse(url="/student/profile?success=Profile updated successfully", status_code=303)
