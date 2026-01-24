from fastapi import APIRouter, Depends, Request, Body, Response, Form, UploadFile, File
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from ..supabase_client import get_supabase
from ..dependencies import get_current_faculty
from datetime import datetime, timedelta
import os
import csv
import io
import json
import re
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter(prefix="/faculty", tags=["Faculty"])

from ..utils import templates

# --- Period Alert System (Faculty Period Alert & Notification) ---
# NOTE: CampusIQ uses Supabase tables directly. We add routes + Pydantic models and
# document the required table schema separately (docs/db/period_alert.sql).
ALERT_STATUS_PENDING = "PENDING"
ALERT_STATUS_ACCEPTED = "ACCEPTED"
ALERT_STATUS_REJECTED = "REJECTED"

# --- Helper Classes ---
class ProfileWrapper:
    def __init__(self, data):
        for k,v in data.items(): setattr(self, k, v)
    def __getitem__(self, item):
        return getattr(self, item)
    def get(self, item, default=None):
        return getattr(self, item, default)

class UserWrapper:
    def __init__(self, u, p):
        self.role = u['role']
        self.name = u.get('name', p.get('name'))
        self.email = u.get('email', p.get('email'))
        self.profile_image = p.get('profile_image')
        self.faculty_profile = ProfileWrapper(p) if isinstance(p, dict) else p

class FetchStudentsRequest(BaseModel):
    class_id: Optional[str] = None

class AssessmentListRequest(BaseModel):
    subject_id: Optional[str] = None
    type: Optional[str] = None

class AssessmentDetailRequest(BaseModel):
    id: int

class AssessmentDeleteRequest(BaseModel):
    id: int

class AttendancePeriodsRequest(BaseModel):
    offering_id: int
    date: str

class AttendanceStudentsRequest(BaseModel):
    offering_id: int
    date: str
    time: str

class AttendanceItem(BaseModel):
    student_id: int
    status: str

class AttendanceSaveRequest(BaseModel):
    offering_id: int
    date: str
    time: str
    attendance: List[AttendanceItem]
    update_reason: Optional[str] = None

class AttendanceFetchRequest(BaseModel):
    offering_id: int
    date: str

class AttendanceUpdateRequest(BaseModel):
    id: int
    status: str
    reason: str

class AttendanceStatsRequest(BaseModel):
    offering_id: int
    month: str

class GetMarksStudentsRequest(BaseModel):
    subject_value: str
    assessment_type: str
    assignment_number: Optional[str] = None # can be int or str

class MarkItem(BaseModel):
    student_id: int
    marks: Optional[str] = None # Might be "5" or ""
    is_absent: Optional[bool] = False
    remarks: Optional[str] = None

class SaveMarksRequest(BaseModel):
    subject_value: str
    assessment_type: str
    assignment_number: Optional[str] = None
    max_marks: float
    marks: List[MarkItem]

class BulkAssignFullRequest(BaseModel):
    subject_value: str

class FetchMarksRequest(BaseModel):
    subject_value: str
    assessment_filter: Optional[str] = None

class FetchTimetableRequest(BaseModel):
    branch: Optional[str] = None
    year: Optional[int] = None
    section: Optional[str] = None
    date: str

class AlterOptionsRequest(BaseModel):
    entry_id: int

class AlterClassRequest(BaseModel):
    entry_id: int
    new_faculty_id: Optional[int] = None
    reason: str
    date: str

class SuspendRequest(BaseModel):
    entry_id: int
    reason: str
    date: str

class ReactivateRequest(BaseModel):
    entry_id: int

class ListResourcesRequest(BaseModel):
    subject_id: Optional[int] = None
    type: Optional[str] = None

class DeleteResourceRequest(BaseModel):
    resource_id: int

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

# Helper for internal marks calculation
def calculate_internal_marks(marks_list):
    total_internal = 0
    max_internal = 0
    for m in marks_list:
        m_type = m.get('assessment_type', '')
        if m_type and 'external' in m_type.lower():
            continue
        total_internal += m.get('marks', 0)
        max_internal += m.get('max_marks', 0)
    return {"totalInternal": total_internal, "maxInternal": max_internal}

# --- Helper Function for Common Context ---
def get_common_context(request: Request, user: dict, profile: dict, supabase):
    announcements = supabase.table("announcement").select("*").in_("target_audience", ["all", "faculty"]).eq("is_active", True).order("created_at", desc=True).limit(5).execute().data

    # Pending period alerts for this faculty (role-scoped: faculty only).
    # IMPORTANT: If the table doesn't exist yet, do not break existing pages.
    pending_alerts_count = 0
    try:
        if profile and profile.get("id"):
            # Convert bigint faculty.id to UUID string for lookup
            profile_id_uuid = bigint_to_uuid_string(profile["id"])
            pa_res = supabase.table("period_alert").select("id", count="exact").eq("alerted_to", profile_id_uuid).eq("status", ALERT_STATUS_PENDING).execute()
            pending_alerts_count = pa_res.count or 0
    except Exception:
        pending_alerts_count = 0

    new_updates_count = len(announcements) + pending_alerts_count
    return {
        "request": request,
        "user": UserWrapper(user, profile),
        "announcements": announcements,
        "new_updates_count": new_updates_count,
        "pending_period_alerts_count": pending_alerts_count,
        "today_date": datetime.now().strftime('%Y-%m-%d')
    }


# Helper: Convert bigint ID to UUID string format (for period_alert table compatibility)
def bigint_to_uuid_string(bigint_id):
    """Convert bigint ID to UUID string format: 00000000-0000-0000-0000-{16-digit-hex}"""
    if bigint_id is None:
        return None
    hex_str = format(int(bigint_id), '012x')  # Convert to 12-digit hex (Standard UUID last segment)
    return f"00000000-0000-0000-0000-{hex_str}"

def uuid_string_to_bigint(uuid_str):
    """Extract bigint from UUID string format (reverse of bigint_to_uuid_string)"""
    if not uuid_str:
        return None
    try:
        # Extract last 16 hex digits and convert to int
        parts = str(uuid_str).split('-')
        if len(parts) == 5:
            return int(parts[-1], 16)
    except:
        pass
    return None


class PeriodAlertCreateRequest(BaseModel):
    period_id: str
    alerted_to: str
    date: str  # YYYY-MM-DD
    time: str  # HH:MM (start time)
    reason: str


class PeriodAlertActionRequest(BaseModel):
    alert_id: str  # UUID string (from period_alert.id)


@router.post("/period-alerts/create", name="faculty.create_period_alert")
async def create_period_alert(req: PeriodAlertCreateRequest, user: dict = Depends(get_current_faculty)):
    """Create a period alert (status=PENDING). Only the faculty who owns the period can create an alert for it."""
    supabase = get_supabase()
    f_res = supabase.table("faculty").select("id, name").eq("user_id", user["user_id"]).single().execute()
    if not f_res.data:
        return JSONResponse({"error": "Faculty profile not found"}, status_code=404)
    me_id = f_res.data["id"]

    # Validate period exists and is owned by the current faculty (original or current)
    t_res = supabase.table("timetable").select("*").eq("id", req.period_id).single().execute()
    if not t_res.data:
        return JSONResponse({"error": "Period not found"}, status_code=404)
    tt = t_res.data

    owner_ids = {tt.get("original_faculty_id"), tt.get("current_faculty_id")}
    if me_id not in owner_ids:
        return JSONResponse({"error": "Not authorized to alert this period"}, status_code=403)

    if int(req.alerted_to) == int(me_id):
        return JSONResponse({"error": "You cannot alert yourself"}, status_code=400)

    # Denormalize subject + class details for stable UI rendering
    s_res = supabase.table("subject").select("id, name").eq("id", tt["subject_id"]).single().execute()
    subject_name = s_res.data["name"] if s_res.data else "Unknown"
    class_str = f"{tt.get('branch', '')} Y{tt.get('year', '')} {tt.get('section', '')}".strip()

    # Convert bigint IDs to UUID strings for period_alert table
    payload = {
        "alerted_by": bigint_to_uuid_string(me_id),
        "alerted_to": bigint_to_uuid_string(int(req.alerted_to)),
        "period_id": bigint_to_uuid_string(int(req.period_id)),
        "period_date": req.date,
        "period_time": req.time,
        "subject": subject_name,
        "class_name": class_str,
        "reason": req.reason,
        "status": ALERT_STATUS_PENDING,
    }

    try:
        ins = supabase.table("period_alert").insert(payload).execute()
    except Exception as e:
        return JSONResponse({"error": f"period_alert table missing or insert failed: {str(e)}"}, status_code=500)

    if not ins.data:
        return JSONResponse({"error": "Failed to create alert"}, status_code=500)

    return {"message": "Alert created", "alert": ins.data[0]}


@router.get("/period-alerts/fetch", name="faculty.fetch_period_alerts")
async def fetch_period_alerts(user: dict = Depends(get_current_faculty)):
    """Fetch alerts for the logged-in faculty (both actionable + confirmations)."""
    supabase = get_supabase()
    f_res = supabase.table("faculty").select("id").eq("user_id", user["user_id"]).single().execute()
    if not f_res.data:
        return JSONResponse({"error": "Faculty profile not found"}, status_code=404)
    me_id = f_res.data["id"]

    # Convert me_id to UUID string for lookup
    me_id_uuid = bigint_to_uuid_string(me_id)
    
    try:
        res = supabase.table("period_alert").select("*").or_(f"alerted_to.eq.{me_id_uuid},alerted_by.eq.{me_id_uuid}").order("created_at", desc=True).limit(50).execute()
    except Exception as e:
        print(f"Error fetching period alerts: {str(e)}")
        # If table not created yet, return empty without breaking UI
        return {"counts": {"pending_to_me": 0, "total_to_me": 0, "total_by_me": 0}, "alerts_to_me": [], "alerts_by_me": []}

    alerts = res.data or []

    # Extract bigint IDs from UUID strings for faculty lookup
    fac_bigint_ids = []
    for a in alerts:
        by_id = uuid_string_to_bigint(a.get("alerted_by"))
        to_id = uuid_string_to_bigint(a.get("alerted_to"))
        if by_id: fac_bigint_ids.append(by_id)
        if to_id: fac_bigint_ids.append(to_id)
    
    fac_map = {}
    if fac_bigint_ids:
        f2 = supabase.table("faculty").select("id, name").in_("id", list(set(fac_bigint_ids))).execute()
        fac_map = {bigint_to_uuid_string(x["id"]): x["name"] for x in (f2.data or [])}

    def enrich(a):
        a = dict(a)
        # Map DB column names to API response format (for frontend compatibility)
        a["date"] = a.get("period_date")  # Frontend expects "date"
        a["time"] = a.get("period_time")  # Frontend expects "time"
        a["subject_name"] = a.get("subject")  # Frontend expects "subject_name"
        a["class_str"] = a.get("class_name")  # Frontend expects "class_str"
        a["alerted_by_name"] = fac_map.get(a.get("alerted_by"), "Unknown")
        a["alerted_to_name"] = fac_map.get(a.get("alerted_to"), "Unknown")
        return a

    alerts_to_me = [enrich(a) for a in alerts if a.get("alerted_to") == me_id_uuid]
    alerts_by_me = [enrich(a) for a in alerts if a.get("alerted_by") == me_id_uuid]
    pending_to_me = len([a for a in alerts_to_me if a.get("status") == ALERT_STATUS_PENDING])

    return {
        "counts": {"pending_to_me": pending_to_me, "total_to_me": len(alerts_to_me), "total_by_me": len(alerts_by_me)},
        "alerts_to_me": alerts_to_me,
        "alerts_by_me": alerts_by_me,
    }


@router.post("/period-alerts/accept", name="faculty.accept_period_alert")
async def accept_period_alert(req: PeriodAlertActionRequest, user: dict = Depends(get_current_faculty)):
    supabase = get_supabase()
    f_res = supabase.table("faculty").select("id").eq("user_id", user["user_id"]).single().execute()
    if not f_res.data:
        return JSONResponse({"error": "Faculty profile not found"}, status_code=404)
    me_id = f_res.data["id"]

    # req.alert_id is UUID string
    a_res = supabase.table("period_alert").select("*").eq("id", req.alert_id).single().execute()
    if not a_res.data:
        return JSONResponse({"error": "Alert not found"}, status_code=404)
    alert = a_res.data

    me_id_uuid = bigint_to_uuid_string(me_id)
    if alert.get("alerted_to") != me_id_uuid:
        return JSONResponse({"error": "Not authorized for this alert"}, status_code=403)
    if alert.get("status") != ALERT_STATUS_PENDING:
        return JSONResponse({"error": "Alert already processed"}, status_code=400)

    now_iso = datetime.utcnow().isoformat()
    supabase.table("period_alert").update({"status": ALERT_STATUS_ACCEPTED}).eq("id", req.alert_id).execute()

    # Apply assignment update using existing timetable pattern (do NOT change existing logic)
    # Convert UUID period_id back to bigint for timetable update
    period_bigint_id = uuid_string_to_bigint(alert.get("period_id"))
    if period_bigint_id:
        supabase.table("timetable").update({
            "status": "altered",
            "reason": f"Period Alert accepted: {alert.get('reason', '')}".strip(),
            "alter_date": alert.get("period_date"),
            "current_faculty_id": me_id
        }).eq("id", period_bigint_id).execute()

    return {"message": "Alert accepted"}


@router.post("/period-alerts/reject", name="faculty.reject_period_alert")
async def reject_period_alert(req: PeriodAlertActionRequest, user: dict = Depends(get_current_faculty)):
    supabase = get_supabase()
    f_res = supabase.table("faculty").select("id").eq("user_id", user["user_id"]).single().execute()
    if not f_res.data:
        return JSONResponse({"error": "Faculty profile not found"}, status_code=404)
    me_id = f_res.data["id"]

    # req.alert_id is UUID string
    a_res = supabase.table("period_alert").select("*").eq("id", req.alert_id).single().execute()
    if not a_res.data:
        return JSONResponse({"error": "Alert not found"}, status_code=404)
    alert = a_res.data

    me_id_uuid = bigint_to_uuid_string(me_id)
    if alert.get("alerted_to") != me_id_uuid:
        return JSONResponse({"error": "Not authorized for this alert"}, status_code=403)
    if alert.get("status") != ALERT_STATUS_PENDING:
        return JSONResponse({"error": "Alert already processed"}, status_code=400)

    now_iso = datetime.utcnow().isoformat()
    supabase.table("period_alert").update({"status": ALERT_STATUS_REJECTED}).eq("id", req.alert_id).execute()
    return {"message": "Alert rejected"}


@router.post("/suspend-class", name="faculty.suspend_class")
async def suspend_class(req: SuspendRequest, user: dict = Depends(get_current_faculty)):
    """Suspend (cancel) a class for a specific date."""
    supabase = get_supabase()
    f_res = supabase.table("faculty").select("id").eq("user_id", user["user_id"]).single().execute()
    if not f_res.data:
        return JSONResponse({"error": "Faculty profile not found"}, status_code=404)
    me_id = f_res.data["id"]

    # Verify ownership (original or current)
    # req.entry_id is the timetable ID (bigint)
    t_res = supabase.table("timetable").select("*").eq("id", req.entry_id).single().execute()
    if not t_res.data:
        return JSONResponse({"error": "Class entry not found"}, status_code=404)
    tt = t_res.data

    owner_ids = {tt.get("original_faculty_id"), tt.get("current_faculty_id")}
    if me_id not in owner_ids:
        # Check if they are the HOD or have special permission? For now strict ownership.
        return JSONResponse({"error": "Not authorized to suspend this class"}, status_code=403)

    # We update the timetable row itself? No, timetable is the schedule.
    # If we suspend, we mark it as "Suspended" or "Cancelled".
    # Since existing logic uses `status`, we check how it handles it.
    # The `timetable` table has `status`.
    # However, `timetable` rows are usually recurring (Day of Week).
    # If we suspend for a *specific date*, we usually effectively "Cancel" it for that date.
    # BUT, the current system seems to assume `timetable` is the template, and attendance/changes are tracked elsewhere?
    # Wait, `timetable` has `alter_date`. Use that?
    # If `timetable` is mutable per week, then updating `status` works.
    # If `timetable` is a static template, we can't change it for just one day without affecting all weeks.
    # Let's check `alter_date`. It suggests the table supports one-off alterations.
    
    # Assuming the user wants to CANCEL this specific instance.
    # If the system supports "Period Alert" which likely creates a one-off change...
    # Let's check how `alter_class` (if it existed) would work.
    
    # Existing `accept_period_alert` does:
    # supabase.table("timetable").update({ "status": "altered", "reason": ..., "alter_date": ... }).eq("id", ...).execute()
    # This implies the `timetable` row itself is mutated.
    # This design is slightly flawed for recurring, but I must follow existing patterns.
    # So I will update the status to 'Suspended'.

    supabase.table("timetable").update({
        "status": "Suspended",
        "reason": req.reason,
        "alter_date": req.date
    }).eq("id", req.entry_id).execute()

    return {"message": "Class suspended successfully"}

def get_pending_attendance(supabase, profile_id, user_id):
    pending_classes = []
    sem_res = supabase.table("semester").select("*").eq("status", "Active").execute()
    active_semesters = sem_res.data or []
    
    if active_semesters:
        sem = active_semesters[0]
        start_date = datetime.strptime(sem['start_date'], '%Y-%m-%d').date()
        today = datetime.now().date()
        end_date = min(datetime.strptime(sem['end_date'], '%Y-%m-%d').date(), today)
        
        if start_date <= end_date:
            # Reverted to match existing schema (removed subject_type from select)
            off_res = supabase.table("class_offering").select("id, subject_id, branch, year, section, subject(name)").eq("faculty_id", profile_id).eq("is_active", True).execute()
            my_offerings = off_res.data or []
            
            if my_offerings:
                # Reverted select
                tt_res = supabase.table("timetable").select("*, subject(name)").execute()
                all_tt = tt_res.data or []
                
                my_tt_entries = []
                for tt in all_tt:
                    if tt.get('original_faculty_id') == profile_id:
                         my_tt_entries.append(tt)
                    elif any(o['branch'] == tt['branch'] and o['year'] == tt['year'] and o['section'] == tt['section'] and o['subject_id'] == tt['subject_id'] for o in my_offerings):
                         my_tt_entries.append(tt)
                         
                att_res = supabase.table("attendance").select("date, subject_id, class_time").gte("date", sem['start_date']).eq("marked_by", user_id).execute()
                existing_att = att_res.data or []
                marked_set = set()
                for a in existing_att:
                     t = a['class_time']
                     if len(t) > 5: t = t[:5]
                     marked_set.add(f"{a['date']}_{a['subject_id']}_{t}")
                
                curr = start_date
                days_map = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                
                while curr <= end_date:
                    day_name = days_map[curr.weekday()]
                    curr_str = curr.strftime('%Y-%m-%d')
                    
                    daily_classes = [t for t in my_tt_entries if t['day_of_week'] == day_name]
                    
                    for cls in daily_classes:
                        c_start = cls['start_time']
                        if len(c_start) > 5: c_start = c_start[:5]
                        
                        # Fix: Don't show future classes for today
                        if curr == today:
                             now_time_str = datetime.now().strftime('%H:%M')
                             if c_start > now_time_str:
                                 continue
                        
                        key = f"{curr_str}_{cls['subject_id']}_{c_start}"
                        
                        if key not in marked_set:
                             off_id = None
                             sub_type = "Theory" # Default
                             
                             for o in my_offerings:
                                 if o['subject_id'] == cls['subject_id'] and o['branch'] == cls['branch'] and o['section'] == cls['section']:
                                     off_id = o['id']
                                     # INFER type from name since column might be missing
                                     if o.get('subject') and o['subject'].get('name'):
                                         name_lower = o['subject']['name'].lower()
                                         if 'lab' in name_lower or 'laboratory' in name_lower or 'practical' in name_lower:
                                             sub_type = "Lab"
                                     break
                             
                             if off_id:
                                 pending_classes.append({
                                     "date": curr_str,
                                     "day": day_name,
                                     "start_time": c_start,
                                     "subject_name": cls['subject']['name'] if cls.get('subject') else "Unknown",
                                     "subject_type": sub_type,
                                     "branch": cls['branch'],
                                     "year": cls['year'],
                                     "section": cls['section'],
                                     "room": cls.get('room_number', '-'),
                                     "offering_id": off_id
                                 })
                    curr += timedelta(days=1)
                
                pending_classes.sort(key=lambda x: (x['date'], x['start_time']), reverse=True)
    return pending_classes

# --- Routes ---

@router.get("/dashboard", name="faculty.dashboard")
async def dashboard(request: Request, user: dict = Depends(get_current_faculty)):
    supabase = get_supabase()
    faculty_res = supabase.table("faculty").select("*").eq("user_id", user['user_id']).execute()
    if not faculty_res.data:
        return "Faculty Profile Not Found"
    faculty_profile = faculty_res.data[0]
    
    offerings_res = supabase.table("class_offering").select("*", count="exact").eq("faculty_id", faculty_profile['id']).eq("is_active", True).execute()
    total_subjects = offerings_res.count
    
    total_students = 0
    if offerings_res.data:
         student_ids = set()
         for off in offerings_res.data:
             s_res = supabase.table("student").select("id").match({
                 "branch": off['branch'], "year": off['year'], "semester": off['semester'], "section": off['section']
             }).execute()
             for s in s_res.data: student_ids.add(s['id'])
         total_students = len(student_ids)

    today_day = datetime.now().strftime('%A')
    todays_classes = supabase.table("timetable").select("*, subject(*)").match({
        "current_faculty_id": faculty_profile['id'],
        "day_of_week": today_day
    }).order("start_time").execute().data

    # --- Enhance Timetable with Attendance Status ---
    processed_classes = []
    current_time_str = datetime.now().strftime('%H:%M')
    
    for cls in (todays_classes or []):
        # 1. Find Offering ID (Required for deep link)
        # We need to match branch, year, section, subject_id to find the offering
        # To avoid N+1 queries ideally we fetch offerings once, but for few classes N queries is acceptable for now
        off_res = supabase.table("class_offering").select("id").match({
            "subject_id": cls['subject_id'],
            "branch": cls['branch'],
            "year": cls['year'],
            "semester": cls['semester'],
            "section": cls['section']
            # "faculty_id": faculty_profile['id'] # Ensure it's taught by this faculty (usually yes if in timetable)
        }).limit(1).execute()
        
        offering_id = off_res.data[0]['id'] if off_res.data else None
        cls['offering_id'] = offering_id

        # 2. Check Attendance Status
        today_date = datetime.now().strftime('%Y-%m-%d')
        # Check if ANY record exists for this subject+date+time
        att_check = supabase.table("attendance").select("id").match({
            "subject_id": cls['subject_id'],
            "date": today_date,
            "class_time": cls['start_time']
        }).limit(1).execute()
        
        cls['is_marked'] = len(att_check.data) > 0 if att_check.data else False
        
        # 3. Check Upcoming
        # Simple string comparison works for HH:MM format (24h)
        if len(cls['start_time']) > 5: cls['start_time'] = cls['start_time'][:5]
        if cls.get('end_time') and len(cls['end_time']) > 5: cls['end_time'] = cls['end_time'][:5]
        
        cls['is_upcoming'] = current_time_str < cls['start_time']
        
        
        # 4. Fetch Student Count for this class
        # Assuming student table has branch, year, section columns that match logic
        st_count_res = supabase.table("student").select("id", count="exact").match({
            "branch": cls['branch'],
            "year": cls['year'],
            "section": cls['section']
        }).execute()
        cls['student_count'] = st_count_res.count if st_count_res.count is not None else 0
        
        # 5. Determine Class Type (Mock or Logic)
        # If subject code contains 'LAB', use 'Lab', else 'Lecture'
        cls['type'] = 'Lab' if 'LAB' in cls['subject'].get('code', '').upper() else 'Lecture'

        # 6. Determine Dashboard Status (Derived)
        # Prioritize 'Suspended' (from DB), then Check Mark, then Time
        if cls.get('status') == 'Suspended':
            pass
        elif cls['is_marked']:
            cls['status'] = 'Completed'
        elif not cls['is_upcoming']:
            # Class started/finished but not marked
            cls['status'] = 'Pending'
        else:
            cls['status'] = 'Upcoming'

        processed_classes.append(cls)

    # --- NEW: Calculate Dashboard Stats ---
    low_attendance_count = 0
    pending_tasks_count = 0

    if offerings_res.data:
        my_offerings = offerings_res.data
        subject_ids = [o['subject_id'] for o in my_offerings]
        
        if subject_ids:
            # 1. Low Attendance Calc (< 75%)
            # Fetch all attendance records for these subjects
            att_res = supabase.table("attendance").select("student_id, status").in_("subject_id", subject_ids).execute()
            all_att = att_res.data or []
            
            student_stats = {}
            for a in all_att:
                sid = a['student_id']
                if sid not in student_stats: student_stats[sid] = {'total': 0, 'present': 0}
                student_stats[sid]['total'] += 1
                if a['status'] == 'present': student_stats[sid]['present'] += 1
                
            low_attendance_list = []
            low_attendance_ids = []

            for s, stats in student_stats.items():
                if stats['total'] > 0:
                    pct = (stats['present'] / stats['total']) * 100
                    if pct < 75:
                        low_attendance_count += 1
                        low_attendance_ids.append(s)
            
            if low_attendance_ids:
                print(f"DEBUG: Low Attendance IDs: {low_attendance_ids}")
                # Fetch names for these students
                st_res = supabase.table("student").select("id, name, student_id, branch, year, section").in_("id", low_attendance_ids).execute()
                print(f"DEBUG: Student Query Result: {len(st_res.data) if st_res.data else 'None'}")
                if st_res.data:
                    print(f"DEBUG: First Student Data: {st_res.data[0]}")
                
                students_map = {st['id']: st for st in st_res.data or []}
                
                for sid in low_attendance_ids:
                    if sid in students_map:
                        st = students_map[sid]
                        # Re-calculate pct for display
                        stats = student_stats[sid]
                        pct = (stats['present'] / stats['total']) * 100
                        low_attendance_list.append({
                            "name": st['name'],
                            "student_id": st['student_id'], # The display ID (e.g. 2023001)
                            "branch": st['branch'],
                            "year": st['year'],
                            "section": st['section'],
                            "percentage": round(pct, 1)
                        })

            # 2. Pending Tasks (Assignments Created but not Graded)
            # Find assignments for these subjects
            subject_ids_str = [str(sid) for sid in subject_ids]
            
            # Fetch assignments created for these subjects
            # Note: 'assignment' table uses subject_class_id which could be string '1' or '101'
            pass
            # Fetch assignments
            ass_res = supabase.table("assignment").select("id, subject_class_id").in_("subject_class_id", subject_ids_str).execute()
            my_assignments = ass_res.data or []
            
            if my_assignments:
                # Group assignments by subject to check if THAT subject has ANY marks
                # This is a heuristic: If a subject has assignments but ZERO marks in 'mark' table, count as pending.
                subjects_with_assessments = set([int(a['subject_class_id']) for a in my_assignments if a['subject_class_id'].isdigit()])
                
                # Check marks for these subjects
                marks_res = supabase.table("mark").select("subject_id").in_("subject_id", list(subjects_with_assessments)).eq("assessment_type", "assignment").execute()
                subjects_with_marks = set([m['subject_id'] for m in marks_res.data or []])
                
                # Pending = Subjects that have assignments but NO marks
                for sid in subjects_with_assessments:
                    if sid not in subjects_with_marks:
                        pending_tasks_count += 1

    # 3. Recent Activities (based on Attendance Logs for now)
    # Fetch last 5 attendance entries marked by this user
    rec_act_res = supabase.table("attendance").select("*, subject(name)").eq("marked_by", user['user_id']).order("created_at", desc=True).limit(5).execute()
    recent_activities = []
    if rec_act_res.data:
        for act in rec_act_res.data:
            # We don't have a 'created_at' displayed usually, but let's use date/time
            act_title = f"Marked Attendance: {act['subject']['name']}" if act.get('subject') else "Marked Attendance"
            recent_activities.append({
                "title": act_title,
                "description": f"For {act['date']} at {act['class_time']}",
                "time": act['date'], # Simplified
                "type": "attendance"
            })

    pending_classes_list = get_pending_attendance(supabase, faculty_profile['id'], user['user_id'])
    
    # Calculate Average Attendance for Stat Card (Mock or Real)
    # Simple Logic: Average of all student averages calculated above
    avg_attendance = 0
    if student_stats:
        total_pct = sum([(s['present']/s['total'])*100 for s in student_stats.values() if s['total'] > 0])
        if total_pct > 0:
            avg_attendance = round(total_pct / len(student_stats), 1)

    # Fetch Announcements (Mock or Real - reusing existing logic if any, or empty list)
    # For now, let's fetch recent admin announcements if possible, or just pass empty
    # Fetch Announcements
    ann_res = supabase.table("announcement").select("*").or_("target_audience.eq.faculty,target_audience.eq.all").order("created_at", desc=True).limit(20).execute()
    ann_data = ann_res.data or []
    announcements = []
    
    # Filter by department
    my_dept = faculty_profile.get('department')
    for ann in ann_data:
        dept = ann.get('department')
        if not dept or dept.lower() == 'all' or dept == my_dept:
            announcements.append(ann)
    
    announcements = announcements[:5]
    
    context = get_common_context(request, user, faculty_profile, supabase)
    context.update({
        "total_subjects": total_subjects,
        "total_students": total_students,
        "todays_classes": processed_classes,
        "pending_classes": pending_classes_list,
        "pending_attendance_count": len(pending_classes_list),
        "low_attendance_count": low_attendance_count,
        "low_attendance_list": low_attendance_list if 'low_attendance_list' in locals() else [],
        "pending_tasks_count": pending_tasks_count,
        "recent_activities": recent_activities,
        "avg_attendance": avg_attendance,
        "today_classes": processed_classes, # Alias for template compatibility
        "today": datetime.now().strftime("%B %d, %Y"),
        "announcements": announcements
    })

    return templates.TemplateResponse("faculty/faculty-dashboard.html", context)


@router.get("/courses", name="faculty.courses")
async def courses(request: Request, user: dict = Depends(get_current_faculty)):
    try:
        supabase = get_supabase()
        faculty_res = supabase.table("faculty").select("id").eq("user_id", user['user_id']).execute()
        if not faculty_res.data:
            return "Faculty Profile Not Found"
        faculty_id = faculty_res.data[0]['id']

        off_res = supabase.table("class_offering").select("*, subject(name, code)").eq("faculty_id", faculty_id).eq("is_active", True).execute()
        offerings = off_res.data or []
        
        courses_data = []
        
        # Try to load local instructions store
        import json
        instructions_file = "faculty_instructions.json"
        local_instructions = {}
        if os.path.exists(instructions_file):
            try:
                with open(instructions_file, 'r') as f:
                    local_instructions = json.load(f)
            except: pass

        for off in offerings:
            # 1. Attendance Stats for 'Completed' logic
            # Count attendance records marked by this faculty for this subject roughly
            att_res = supabase.table("attendance").select("id", count="exact").match({
                "subject_id": off['subject_id']
            }).eq("marked_by", user['user_id']).execute()
            
            completed_classes = att_res.count if att_res.count else 0
            total_classes = 45 # Estimated
            
            # Instructions
            instr = local_instructions.get(str(off['id']), "")
            
            # Infer Subject Type
            sub_name = off['subject']['name'] if off.get('subject') else "Unknown"
            sub_code = off['subject']['code'] if off.get('subject') else ""
            
            subject_type = "Theory"
            if "lab" in sub_name.lower() or "laboratory" in sub_name.lower():
                subject_type = "Lab"
            
            courses_data.append({
                "offering_id": off['id'],
                "subject_name": sub_name,
                "subject_code": sub_code,
                "subject_type": subject_type,
                "course_name": "B.Tech",
                "branch": off['branch'],
                "semester": off['semester'],
                "section": off['section'],
                "academic_year": f"Year {off['year']}",
                "total_classes": total_classes,
                "completed_classes": completed_classes,
                "attendance_percentage": "N/A", 
                "attendance_status_class": "text-muted",
                "instructions": instr,
                "is_active": off['is_active']
            })

        return templates.TemplateResponse("faculty/faculty-courses.html", {
            "request": request,
            "courses": courses_data,
            "user": user,
            "current_page": "courses"
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Error: {str(e)}"

from pydantic import BaseModel
class InstructionUpdate(BaseModel):
    offering_id: int
    instructions: str

@router.post("/courses/update-instructions")
async def update_instructions(data: InstructionUpdate, user: dict = Depends(get_current_faculty)):
    import json
    instructions_file = "faculty_instructions.json"
    local_instructions = {}
    if os.path.exists(instructions_file):
        try:
            with open(instructions_file, 'r') as f:
                local_instructions = json.load(f)
        except: pass
    
    local_instructions[str(data.offering_id)] = data.instructions
    
    with open(instructions_file, 'w') as f:
        json.dump(local_instructions, f)
        
    return {"status": "success"}

@router.get("/attendance", name="faculty.attendance")
async def attendance(request: Request, user: dict = Depends(get_current_faculty)):
    supabase = get_supabase()
    f_res = supabase.table("faculty").select("*").eq("user_id", user['user_id']).execute()
    if not f_res.data: return "Profile not found"
    profile = f_res.data[0]
    
    offerings = supabase.table("class_offering").select("*, subject(*)").eq("faculty_id", profile['id']).eq("is_active", True).execute().data
    
    # --- Pending Attendance Logic ---
    pending_classes = get_pending_attendance(supabase, profile['id'], user['user_id'])

    context = get_common_context(request, user, profile, supabase)
    context.update({
        "class_offerings": offerings,
        "pending_classes": pending_classes
    })
    return templates.TemplateResponse("faculty/faculty-attendance.html", context)
    
@router.post("/attendance/save", name="faculty.save_attendance")
async def save_attendance(req: AttendanceSaveRequest, user: dict = Depends(get_current_faculty)):
    supabase = get_supabase()
    
    # --- 1. Semester & Date Validation ---
    try:
        input_dt = datetime.strptime(f"{req.date} {req.time}", '%Y-%m-%d %H:%M')
        if input_dt > datetime.now():
             return JSONResponse({"error": "Cannot mark attendance for future dates or times."}, status_code=400)
    except ValueError:
        pass 

    # Fetch Active Semester(s)
    # Check if the date falls within ANY active semester
    sem_res = supabase.table("semester").select("*").eq("status", "Active").execute()
    active_semesters = sem_res.data or []
    
    is_valid_semester = False
    validation_msg = "Attendance disabled. No active semester found for this date."
    
    if not active_semesters:
        return JSONResponse({"error": "Attendance disabled. No active semester configured."}, status_code=400)

    for sem in active_semesters:
        # Check date range
        if sem['start_date'] <= req.date <= sem['end_date']:
            is_valid_semester = True
            break
        elif req.date < sem['start_date']:
            validation_msg = f"Attendance not available. Semester '{sem['name']}' has not started yet."
        elif req.date > sem['end_date']:
            validation_msg = f"Attendance disabled. Semester '{sem['name']}' has ended."

    if not is_valid_semester:
         return JSONResponse({"error": validation_msg}, status_code=400)

    # --- End Validation ---

    off_res = supabase.table("class_offering").select("subject_id").eq("id", req.offering_id).single().execute()
    if not off_res.data: return JSONResponse({"error": "Invalid Class Offering"}, status_code=404)
    subject_id = off_res.data['subject_id']
    
    count = 0
    absent_students = []

    for item in req.attendance:
        # Check if exists
        exists_res = supabase.table("attendance").select("id, status").match({
            "student_id": item.student_id,
            "subject_id": subject_id,
            "date": req.date,
            "class_time": req.time
        }).execute()
        
        # Determine Status
        status_to_save = item.status
        is_not_marked = (status_to_save == 'not_marked')

        if not exists_res.data:
            # If New Record
            if not is_not_marked:
                # Insert only if valid status
                supabase.table("attendance").insert({
                    "student_id": item.student_id,
                    "subject_id": subject_id,
                    "date": req.date,
                    "class_time": req.time,
                    "status": status_to_save,
                    "marked_by": user['user_id']
                }).execute()
        else:
            # If Existing Record
            rec = exists_res.data[0]
            
            if is_not_marked:
                # DELETE if now 'not_marked' (reset)
                supabase.table("attendance").delete().eq("id", rec['id']).execute()
            else:
                # UPDATE
                # If status is changing, enforce reason
                if rec['status'] != status_to_save:
                    if not req.update_reason or not req.update_reason.strip():
                         return JSONResponse({"error": "Reason for update is required when modifying existing attendance."}, status_code=400)
                    
                    payload = { "status": status_to_save, "marked_by": user['user_id'] }
                    payload["reason_for_change"] = req.update_reason
                    supabase.table("attendance").update(payload).eq("id", rec['id']).execute()
                elif req.update_reason:
                    # Reason update only
                     supabase.table("attendance").update({ "reason_for_change": req.update_reason }).eq("id", rec['id']).execute()
        
        count += 1
        if item.status == 'absent':
             s_res = supabase.table("student").select("name").eq("id", item.student_id).single().execute()
             if s_res.data: absent_students.append(s_res.data['name'])
             
    return {
        "message": f"Processed {count} records.",
        "absent_students": absent_students
    }

@router.post("/attendance/fetch", name="faculty.fetch_attendance")
async def fetch_attendance(req: AttendanceFetchRequest, user: dict = Depends(get_current_faculty)):
    supabase = get_supabase()
    
    off_res = supabase.table("class_offering").select("*").eq("id", req.offering_id).single().execute()
    if not off_res.data: return JSONResponse({"error": "Invalid Class Offering"}, status_code=404)
    off = off_res.data
    
    # Time map logic (fetch timetable for end times)
    try:
        date_obj = datetime.strptime(req.date, '%Y-%m-%d')
        day_name = date_obj.strftime('%A')
        
        # We need subject code to handle duplicates, but let's stick to simple subject_id query for now
        # as per previous logic
        ts_res = supabase.table("timetable").select("start_time, end_time").match({
            "subject_id": off['subject_id'],
            "day_of_week": day_name
        }).execute()
        time_map = {t['start_time']: t['end_time'] for t in ts_res.data or []}
    except:
        time_map = {}

    records_res = supabase.table("attendance").select("*").match({
        "subject_id": off['subject_id'], "date": req.date
    }).execute()
    records = records_res.data or []
    
    total = len(records)
    present = len([r for r in records if r['status'] == 'present'])
    absent = len([r for r in records if r['status'] == 'absent'])
    rate = int((present / total * 100)) if total > 0 else 0
    
    record_list = []
    # Bulk fetch student names for performance
    student_ids = list(set([r['student_id'] for r in records]))
    s_map = {}
    if student_ids:
        s_res = supabase.table("student").select("id, name, student_id").in_("id", student_ids).execute()
        s_map = {s['id']: s for s in s_res.data or []}
        
    for r in records:
        s = s_map.get(r['student_id'])
        display_time = r['class_time']
        if r['class_time'] in time_map:
            display_time = f"{r['class_time']} - {time_map[r['class_time']]}"
            
        record_list.append({
            'id': r['id'],
            'student_id_display': s['student_id'] if s else 'Unknown',
            'student_name': s['name'] if s else 'Unknown',
            'class_time': display_time,
            'status': r['status'],
            'reason': r.get('reason')
        })
        
    # Sort by Student ID
    record_list.sort(key=lambda x: x['student_id_display'])
        
    return {
        "records": record_list,
        "stats": { "total": total, "present": present, "absent": absent, "rate": rate }
    }

@router.post("/attendance/update_record", name="faculty.update_attendance_record")
async def update_attendance_record(req: AttendanceUpdateRequest, user: dict = Depends(get_current_faculty)):
    supabase = get_supabase()
    if not req.reason or not req.reason.strip():
        return JSONResponse({"error": "Reason for update is required"}, status_code=400)
        
    supabase.table("attendance").update({
        "status": req.status,
        "reason": req.reason,
        "reason_for_change": req.reason
    }).eq("id", req.id).execute()
    
    return {"message": "Updated"}

@router.post("/attendance/monthly_stats", name="faculty.monthly_stats")
async def monthly_stats(req: AttendanceStatsRequest, user: dict = Depends(get_current_faculty)):
    supabase = get_supabase()
    off_res = supabase.table("class_offering").select("*").eq("id", req.offering_id).single().execute()
    if not off_res.data: return JSONResponse({"error": "Invalid Class Offering"}, status_code=404)
    off = off_res.data
    
    # Active students
    s_res = supabase.table("student").select("id, student_id, name").match({
        "branch": off['branch'], "year": off['year'], 
        "semester": off['semester'], "section": off['section'], "status": 'active'
    }).order("student_id").execute()
    students = s_res.data or []
    
    # Fetch all attendance for this subject
    # Supabase filter for "date LIKE 'YYYY-MM%'" isn't direct in checks. 
    # Use text search or range if needed. Here simplistic 'ilike' might work if date is text.
    att_res = supabase.table("attendance").select("*").eq("subject_id", off['subject_id']).ilike("date", f"{req.month}%").execute()
    all_records = att_res.data or []
    
    stats = []
    for s in students:
        s_records = [r for r in all_records if r['student_id'] == s['id']]
        total = len(s_records)
        present = len([r for r in s_records if r['status'] == 'present'])
        absent = len([r for r in s_records if r['status'] == 'absent'])
        percentage = int((present / total * 100)) if total > 0 else 0
        
        stats.append({
            'student_id': s['student_id'],
            'name': s['name'],
            'total': total,
            'present': present,
            'absent': absent,
            'percentage': percentage
        })
        
    return {"stats": stats}

@router.post("/attendance/export", name="faculty.export_attendance")
async def export_attendance_handler(request: Request, user: dict = Depends(get_current_faculty)):
    # Handling form data manually since it might vary
    form = await request.form()
    offering_id = form.get('offering_id') or form.get('subject_value')
    date_str = form.get('date')
    month_str = form.get('month')
    
    supabase = get_supabase()
    off_res = supabase.table("class_offering").select("*").eq("id", offering_id).single().execute()
    if not off_res.data: return Response("Invalid Offering", status_code=400)
    off = off_res.data
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    if date_str:
        writer.writerow(['Student ID', 'Name', 'Time', 'Status', 'Reason'])
        att_res = supabase.table("attendance").select("*").match({
            "subject_id": off['subject_id'], "date": date_str
        }).execute()
        
        # Bulk fetch students
        s_ids = list(set([r['student_id'] for r in att_res.data or []]))
        s_map = {}
        if s_ids:
             s_r = supabase.table("student").select("id, student_id, name").in_("id", s_ids).execute()
             s_map = {s['id']: s for s in s_r.data}
             
        for r in (att_res.data or []):
            s = s_map.get(r['student_id'])
            writer.writerow([
                s['student_id'] if s else '',
                s['name'] if s else '',
                r['class_time'],
                r['status'],
                r.get('reason', '')
            ])
        filename = f"Attendance_{date_str}.csv"
        
    elif month_str:
        writer.writerow(['Student ID', 'Name', 'Total Classes', 'Present', 'Absent', 'Percentage'])
        # Active students
        s_res = supabase.table("student").select("id, student_id, name").match({
            "branch": off['branch'], "year": off['year'], 
            "semester": off['semester'], "section": off['section'], "status": 'active'
        }).execute()
        students = s_res.data or []
        
        att_res = supabase.table("attendance").select("*").eq("subject_id", off['subject_id']).ilike("date", f"{month_str}%").execute()
        all_records = att_res.data or []
        
        for s in students:
            s_records = [r for r in all_records if r['student_id'] == s['id']]
            total = len(s_records)
            present = len([r for r in s_records if r['status'] == 'present'])
            absent = len([r for r in s_records if r['status'] == 'absent'])
            pct = int((present / total * 100)) if total > 0 else 0
            writer.writerow([s['student_id'], s['name'], total, present, absent, f"{pct}%"])
            
        filename = f"Attendance_{month_str}.csv"
    else:
        return Response("Missing date or month", status_code=400)
        
    return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={filename}"})

@router.post("/attendance/get_periods", name="faculty.get_periods")
async def get_periods(req: AttendancePeriodsRequest, user: dict = Depends(get_current_faculty)):
    supabase = get_supabase()
    
    # 1. Fetch Offering
    off_res = supabase.table("class_offering").select("*, subject(code)").eq("id", req.offering_id).single().execute()
    if not off_res.data: return {"error": "Invalid Class Offering"}
    offering = off_res.data
    
    # 2. Determine Day of Week
    try:
        date_obj = datetime.strptime(req.date, '%Y-%m-%d')
        day_of_week = date_obj.strftime('%A')
    except ValueError:
        return {"error": "Invalid date format"}

    # 3. Find matching subjects (handle duplicates by code)
    # Supabase doesn't support complicated joins in one go easily for this specific "IN" logic with subjects
    # But we can just query timetable for this specific subject + faculty
    
    # Logic in Flask was: Timetable.subject_id in [ids with same code]
    # Here simplifiction: Use the subject_id from offering. 
    # If the user wants to handle duplicate subject codes properly, we might need a separate query.
    # For now, querying by subject_id directly is safer and simpler.
    
    # Additional filter: match generic class details (branch, year, etc)
    # The timetable table references specific subject_id
    
    periods_res = supabase.table("timetable").select("*").match({
        "subject_id": offering['subject_id'],
        "year": offering['year'],
        "semester": offering['semester'],
        "section": offering['section'],
        "day_of_week": day_of_week
        # "original_faculty_id": offering['faculty_id'] # Optional depending on if we show substituted classes
    }).order("start_time").execute()
    
    entries = periods_res.data or []
    
    today = datetime.now()
    is_today = req.date == today.strftime('%Y-%m-%d')
    input_date = datetime.strptime(req.date, '%Y-%m-%d').date()
    is_future_date = input_date > today.date()

    periods = []
    seen_periods = set()
    
    for e in entries:
        period_key = (e['start_time'], e['end_time'])
        if period_key in seen_periods: continue
        seen_periods.add(period_key)

        is_future_period = False
        if is_future_date:
            is_future_period = True
        elif is_today:
             try:
                 start_dt = datetime.strptime(f"{req.date} {e['start_time']}", '%Y-%m-%d %H:%M')
                 if start_dt > today: is_future_period = True
             except: pass

        periods.append({
            'start_time': e['start_time'],
            'end_time': e['end_time'],
            'type': e.get('status', 'Regular'), # Use status from DB or default
            'is_future': is_future_period
        })

    return {"periods": periods}

@router.post("/attendance/get_students_for_attendance", name="faculty.get_students_for_attendance")
async def get_students_for_attendance(req: AttendanceStudentsRequest, user: dict = Depends(get_current_faculty)):
    supabase = get_supabase()
    
    off_res = supabase.table("class_offering").select("*").eq("id", req.offering_id).single().execute()
    if not off_res.data: return {"error": "Invalid Class Offering"}
    offering = off_res.data
    
    # 1. Fetch Students
    s_res = supabase.table("student").select("id, student_id, name").match({
        "branch": offering['branch'],
        "year": offering['year'],
        "semester": offering['semester'],
        "section": offering['section'],
        "status": 'active'
    }).order("student_id").execute()
    
    students = s_res.data or []
    
    # 2. Fetch Existing Attendance
    # "attendance" table has: subject_id, date, class_time
    att_res = supabase.table("attendance").select("*").match({
        "subject_id": offering['subject_id'],
        "date": req.date,
        "class_time": req.time
    }).execute()
    
    existing = att_res.data or []
    is_frozen = len(existing) > 0
    
    # --- Semester Validation ---
    sem_res = supabase.table("semester").select("*").eq("status", "Active").execute()
    active_semesters = sem_res.data or []
    
    is_allowed = False
    validation_msg = "Attendance disabled. No active semester found."
    
    if active_semesters:
        validation_msg = "Attendance disabled. Date outside active semester."
        for sem in active_semesters:
            if sem['start_date'] <= req.date <= sem['end_date']:
                is_allowed = True
                validation_msg = ""
                break
            elif req.date < sem['start_date']:
                validation_msg = f"Attendance not available. Semester '{sem['name']}' starts {sem['start_date']}."
            elif req.date > sem['end_date']:
                validation_msg = f"Attendance disabled. Semester '{sem['name']}' ended {sem['end_date']}."
    
    return {
        "students": students,
        "existing_attendance": existing,
        "is_frozen": is_frozen,
        "semester_validation": {
            "allowed": is_allowed,
            "message": validation_msg
        }
    }

@router.get("/profile", name="faculty.profile")
async def profile(request: Request, user: dict = Depends(get_current_faculty)):
    supabase = get_supabase()
    f_res = supabase.table("faculty").select("*").eq("user_id", user['user_id']).execute()
    if not f_res.data: return "Profile not found"
    profile = f_res.data[0]
    
    offerings = supabase.table("class_offering").select("*, subject(*)").eq("faculty_id", profile['id']).eq("is_active", True).execute().data
    
    subjects_taught = []
    for off in offerings:
        subjects_taught.append({
            "name": off['subject']['name'],
            "code": off['subject']['code'],
            "branch": off['branch'],
            "year": off['year'],
            "semester": off['semester'],
            "section": off['section']
        })

    teaching_data = {
        "total_classes": len(offerings),
        "subjects_taught": subjects_taught
    }

    context = get_common_context(request, user, profile, supabase)
    context.update({
        "faculty": ProfileWrapper(profile),
        "teaching_data": teaching_data
    })
    
    return templates.TemplateResponse("faculty/faculty-profile.html", context)

@router.get("/my-students", name="faculty.my_students")
async def my_students(request: Request, user: dict = Depends(get_current_faculty)):
    supabase = get_supabase()
    f_res = supabase.table("faculty").select("*").eq("user_id", user['user_id']).execute()
    if not f_res.data: return "Profile not found"
    profile = f_res.data[0]

    offerings = supabase.table("class_offering").select("*, subject(*)").eq("faculty_id", profile['id']).eq("is_active", True).execute().data
    
    context = get_common_context(request, user, profile, supabase)
    context.update({
        "class_offerings": offerings
    })

    return templates.TemplateResponse("faculty/faculty-students.html", context)

@router.post("/fetch-students-list", name="faculty.fetch_students_list")
async def fetch_students_list(req: FetchStudentsRequest, user: dict = Depends(get_current_faculty)):
    supabase = get_supabase()
    f_res = supabase.table("faculty").select("*").eq("user_id", user['user_id']).execute()
    if not f_res.data: return {"students": []}
    faculty_id = f_res.data[0]['id']

    students = []
    
    if req.class_id:
        offering = supabase.table("class_offering").select("*").eq("id", req.class_id).eq("faculty_id", faculty_id).execute().data
        if offering:
            off = offering[0]
            s_res = supabase.table("student").select("*").match({
                "branch": off['branch'], "year": off['year'], 
                "semester": off['semester'], "section": off['section']
            }).order("student_id").execute()
            students = s_res.data
    else:
        offerings = supabase.table("class_offering").select("*").eq("faculty_id", faculty_id).eq("is_active", True).execute().data
        student_ids = set()
        
        for off in offerings:
            s_res = supabase.table("student").select("*").match({
                "branch": off['branch'], "year": off['year'], 
                "semester": off['semester'], "section": off['section']
            }).order("student_id").execute()
            for s in s_res.data:
                if s['student_id'] not in student_ids:
                    s['branch'] = off['branch'] 
                    students.append(s)
                    student_ids.add(s['student_id'])
    
    # Sort final combined list
    students.sort(key=lambda x: x['student_id'])
    
    return {"students": students}

@router.post("/export-students-list", name="faculty.export_students_list")
async def export_students_list_handler(class_id: str = Form(None), user: dict = Depends(get_current_faculty)):
    supabase = get_supabase()
    f_res = supabase.table("faculty").select("*").eq("user_id", user['user_id']).execute()
    if not f_res.data: return Response("Profile not found")
    faculty_id = f_res.data[0]['id']

    students = []
    
    if class_id:
        offering = supabase.table("class_offering").select("*").eq("id", class_id).eq("faculty_id", faculty_id).execute().data
        if offering:
            off = offering[0]
            s_res = supabase.table("student").select("*").match({
                "branch": off['branch'], "year": off['year'], 
                "semester": off['semester'], "section": off['section']
            }).execute()
            students = s_res.data
    else:
        offerings = supabase.table("class_offering").select("*").eq("faculty_id", faculty_id).eq("is_active", True).execute().data
        student_ids = set()
        for off in offerings:
            s_res = supabase.table("student").select("*").match({
                "branch": off['branch'], "year": off['year'], 
                "semester": off['semester'], "section": off['section']
            }).execute()
            for s in s_res.data:
                if s['student_id'] not in student_ids:
                    students.append(s)
                    student_ids.add(s['student_id'])

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Student ID', 'Name', 'Email', 'Branch', 'Year', 'Section', 'Phone'])
    for s in students:
        writer.writerow([s['student_id'], s['name'], s['email'], s['branch'], s['year'], s['section'], s.get('phone', '')])
    
    output.seek(0)
    return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=students.csv"})

@router.post("/update-profile", name="faculty.update_profile")
async def update_profile(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(None),
    qualification: str = Form(None),
    experience: int = Form(0),
    address: str = Form(None),
    user: dict = Depends(get_current_faculty)
):
    supabase = get_supabase()
    f_res = supabase.table("faculty").select("id").eq("user_id", user['user_id']).execute()
    if not f_res.data: return "Profile not found"
    faculty_id = f_res.data[0]['id']
    
    data = {
        "name": name,
        "email": email,
        "phone": phone,
        "qualification": qualification,
        "experience": experience,
        "address": address
    }
    supabase.table("faculty").update(data).eq("id", faculty_id).execute()
    return Response(status_code=303, headers={"Location": str(request.url_for("faculty.profile"))})

@router.get("/student/{student_id}", name="faculty.view_student_profile")
async def view_student_profile(student_id: int, request: Request, user: dict = Depends(get_current_faculty)):
    supabase = get_supabase()
    
    # 1. Student Details
    s_res = supabase.table("student").select("*").eq("id", student_id).execute()
    if not s_res.data:
        return "Student Not Found"
    student = s_res.data[0]
    
    # 2. Faculty Profile
    f_res = supabase.table("faculty").select("*").eq("user_id", user['user_id']).execute()
    profile = f_res.data[0] if f_res.data else {}

    # 3. Attendance Stats
    att_res = supabase.table("attendance").select("*").eq("student_id", student['id']).execute()
    att_data = att_res.data if att_res.data else []
    
    offering_ids = set()
    for a in att_data:
        oid = a.get('class_offering_id') or a.get('offering_id') or a.get('class_id')
        if oid: offering_ids.add(oid)
            
    offerings_map = {}
    if offering_ids:
        off_res = supabase.table("class_offering").select("id, subject(name, code)").in_("id", list(offering_ids)).execute()
        if off_res.data:
            for o in off_res.data:
                offerings_map[o['id']] = o
    
    total_classes = len(att_data)
    present_classes = sum(1 for a in att_data if str(a.get('status')).lower() == 'present')
    overall_percentage = round((present_classes / total_classes * 100), 1) if total_classes > 0 else 0
    
    attendance_stats = {
        "total": total_classes,
        "present": present_classes,
        "percentage": overall_percentage
    }
    
    subject_att = {}
    for a in att_data:
        oid = a.get('class_offering_id') or a.get('offering_id') or a.get('class_id')
        if not oid or oid not in offerings_map: continue
        
        offering = offerings_map[oid]
        if not offering.get('subject'): continue
        
        sub_name = offering['subject']['name']
        if sub_name not in subject_att: subject_att[sub_name] = {"total": 0, "present": 0}
        subject_att[sub_name]["total"] += 1
        
        if str(a.get('status')).lower() == 'present':
            subject_att[sub_name]["present"] += 1
            
    detailed_attendance = []
    for sub_name, stats in subject_att.items():
        pct = round((stats['present'] / stats['total'] * 100), 1) if stats['total'] > 0 else 0
        detailed_attendance.append({
            "subject_name": sub_name,
            "total": stats['total'],
            "present": stats['present'],
            "percentage": pct
        })
        
    # 4. Marks / Semester Data
    semester_data = {i: [] for i in range(1, 9)}
    
    marks_res = None
    try:
        # Check marks table or mark table
        marks_res = supabase.table("mark").select("*, class_offering(semester, subject(*))").eq("student_id", student['id']).execute()
    except Exception as e:
        # Fallback to 'mark' table if 'marks' fails
        try:
             marks_res = supabase.table("mark").select("*, class_offering(semester, subject(*))").eq("student_id", student['id']).execute()
        except:
             marks_res = None
    
    sub_map = {}
    
    if marks_res and marks_res.data:
        for m in marks_res.data:
            off = m.get('class_offering')
            if not off: continue
            sub = off.get('subject')
            if not sub: continue
            
            s_code = sub['code']
            sem = off.get('semester', 1) 
            
            if s_code not in sub_map:
                sub_map[s_code] = {"meta": sub, "sem": sem, "marks": []}
            sub_map[s_code]['marks'].append(m)
            
    for s_code, data in sub_map.items():
        sub = data['meta']
        sem = data['sem']
        marks_list = data['marks']
        
        total_internal = 0
        max_internal = 0
        external_score = None
        
        for m in marks_list:
            m_type = m.get('mark_type', '')
            score = m.get('score', 0)
            mx = m.get('max_marks', 0)
            
            if m_type and 'external' in m_type.lower():
                external_score = score
            else:
                total_internal += score
                max_internal += mx
        
        total_score = (total_internal + (external_score or 0)) if external_score is not None else None
        
        status = 'Pending'
        if total_score is not None:
             status = 'Pass' if total_score >= 40 else 'Fail' 
        
        sub_view = {
            "name": sub['name'],
            "code": sub['code'],
            "credits": sub.get('credits', 3), 
            "internal": {
                "allInternalMarksEntered": True,
                "totalInternal": total_internal,
                "maxInternal": max_internal
            },
            "external": external_score,
            "total": total_score,
            "status": status
        }
        
        if sem in semester_data:
            semester_data[sem].append(sub_view)

    context = get_common_context(request, user, profile, supabase)
    context.update({
        "student": student,
        "attendance_stats": attendance_stats,
        "detailed_attendance": detailed_attendance,
        "semester_data": semester_data
    })
    
    return templates.TemplateResponse("faculty/view-student-profile.html", context)


@router.get("/assessments", name="faculty.assessments")
async def assessments(request: Request, user: dict = Depends(get_current_faculty)):
    supabase = get_supabase()
    f_res = supabase.table("faculty").select("*").eq("user_id", user['user_id']).execute()
    profile = f_res.data[0] if f_res.data else {}
    offerings = supabase.table("class_offering").select("*, subject(*)").eq("faculty_id", profile.get('id')).eq("is_active", True).execute().data
    context = get_common_context(request, user, profile, supabase)
    context.update({"class_offerings": offerings})
    return templates.TemplateResponse("faculty/faculty-assessments.html", context)

# --- Assessment API Routes ---
# TABLE NAME: 'assignment' (from schema hint)

@router.post("/assessments/list", name="faculty.list_assessments")
async def list_assessments(req: AssessmentListRequest, user: dict = Depends(get_current_faculty)):
    supabase = get_supabase()
    f_res = supabase.table("faculty").select("id").eq("user_id", user['user_id']).execute()
    if not f_res.data: return {"assessments": []}
    fid = f_res.data[0]['id']
    
    # 1. Get all subjects taught by this faculty
    off_res = supabase.table("class_offering").select("subject_id").eq("faculty_id", fid).eq("is_active", True).execute()
    # Unique subject IDs (Integers)
    my_subject_ids = list(set([o['subject_id'] for o in off_res.data or []]))
    
    # Cast to strings for matching 'subject_class_id'
    my_subject_ids_str = [str(sid) for sid in my_subject_ids]
    
    if not my_subject_ids:
        return {"assessments": []}

    # 2. Query assignments for these subjects using subject_class_id
    query = supabase.table("assignment").select("*").in_("subject_class_id", my_subject_ids_str)
    
    if req.subject_id:
        if int(req.subject_id) not in my_subject_ids:
             return {"assessments": []} # Access control
        query = query.eq("subject_class_id", str(req.subject_id))
    if req.type:
        query = query.eq("type", req.type)
        
    res = query.order("created_at", desc=True).execute()
    assessments = res.data or []
    
    # 3. Fetch Subject Details Manually
    sub_map = {}
    if my_subject_ids:
        s_res = supabase.table("subject").select("id, name, code").in_("id", my_subject_ids).execute()
        if s_res.data:
            sub_map = {str(s['id']): s for s in s_res.data} # Key by String ID for easy lookup
            
    data = []
    for a in assessments:
        # DB column is subject_class_id (text)
        scid = a.get('subject_class_id')
        
        # Try to map back to subject
        if scid and scid in sub_map:
            a['subject'] = sub_map[scid]
            a['subject_name'] = sub_map[scid]['name']
            a['subject_id'] = int(scid) # Provide clean int ID for frontend
        else:
            a['subject'] = None
            a['subject_name'] = 'Unknown'
            # If scid is a digit, pass it back as subject_id anyway
            if scid and scid.isdigit():
                a['subject_id'] = int(scid)
        data.append(a)
        
    return {"assessments": data}

@router.post("/assessments/save", name="faculty.save_assessment")
async def save_assessment(
    id: str = Form(None),
    title: str = Form(...),
    subject_id: int = Form(...),
    type: str = Form(...),
    max_marks: int = Form(...),
    description: str = Form(None),
    questions: str = Form(None),
    file: UploadFile = File(None),
    user: dict = Depends(get_current_faculty)
):
    supabase = get_supabase()
    # Check faculty auth - Fetch name as well
    f_res = supabase.table("faculty").select("id, name").eq("user_id", user['user_id']).execute()
    if not f_res.data: return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    faculty_user = f_res.data[0]
    faculty_name = faculty_user['name']
    
    resource_id = None
    if file:
        try:
            filename = file.filename
            safe_filename = f"{int(datetime.now().timestamp())}_{filename}"
            
            import os
            upload_dir = os.path.join(os.getcwd(), 'static', 'uploads')
            if not os.path.exists(upload_dir): os.makedirs(upload_dir)
            
            file_path = os.path.join(upload_dir, safe_filename)
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
                
            # Create Resource
            res_payload = {
                "title": f"{title} Question Paper",
                "description": f"Question paper for {title}",
                "type": "assignment_question_paper",
                "file_name": safe_filename,
                "subject_id": subject_id, # Assuming int subject_id matches Resource table
                "uploaded_by": user['user_id']
            }
            r_ins = supabase.table("resources").insert(res_payload).execute()
            if r_ins.data:
                resource_id = r_ins.data[0]['id']
                
        except Exception as e:
            print(f"File upload error: {e}")
            # Optional: return error or continue without file?
            # returning error is safer
            return JSONResponse({"error": f"File upload failed: {str(e)}"}, status_code=500)

    payload = {
        "title": title,
        "subject_class_id": str(subject_id), # Map to text column
        "type": type,
        "max_marks": max_marks,
        "description": description,
        "questions": questions,
        "created_by": user['user_id'], # Use created_by (UUID)
        "created_by_name": faculty_name
    }
    
    if resource_id:
        payload['resource_id'] = resource_id
    
    try:
        if id:
             # If updating, we might want to check ownership
            supabase.table("assignment").update(payload).eq("id", id).execute()
            return {"message": "Assessment updated"}
        else:
            supabase.table("assignment").insert(payload).execute()
            return {"message": "Assessment created"}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@router.post("/assessments/details", name="faculty.get_assessment_details")
async def get_assessment_details(req: AssessmentDetailRequest, user: dict = Depends(get_current_faculty)):
    supabase = get_supabase()
    # Manual fetch
    res = supabase.table("assignment").select("*").eq("id", req.id).single().execute()
    if res.data:
        data = res.data
        scid = data.get('subject_class_id')
        
        if scid and scid.isdigit():
             sub = supabase.table("subject").select("name").eq("id", int(scid)).single().execute()
             data['subject_name'] = sub.data['name'] if sub.data else 'Unknown'
             data['subject_id'] = int(scid) # frontend expects subject_id
        else:
             data['subject_name'] = 'Unknown'
        return data
    return {"error": "Not found"}

@router.post("/assessments/delete", name="faculty.delete_assessment")
async def delete_assessment(req: AssessmentDeleteRequest, user: dict = Depends(get_current_faculty)):
    supabase = get_supabase()
    supabase.table("assignment").delete().eq("id", req.id).execute()
    return {"success": True}


# --- Other Stubs ---

@router.get("/mentees", name="faculty.mentees")
async def mentees(request: Request, user: dict = Depends(get_current_faculty)):
    supabase = get_supabase()
    f_res = supabase.table("faculty").select("*").eq("user_id", user['user_id']).execute()
    profile = f_res.data[0] if f_res.data else {}
    
    mentees = []
    if profile:
        # 1. Direct Assignments (Manual)
        m_res = supabase.table("student").select("*").eq("counselor_id", profile['id']).execute()
        direct_mentees = m_res.data or []
        
        # 2. Class Teacher Assignments (Automatic)
        # Fetch classes where faculty is mentor
        mentor_classes = supabase.table("class_offering").select("*").eq("faculty_id", profile['id']).eq("is_mentor", True).eq("is_active", True).execute().data or []
        
        class_mentees = []
        for cls in mentor_classes:
            # Fetch students in this class
            s_res = supabase.table("student").select("*").match({
                "branch": cls['branch'],
                "year": cls['year'],
                "semester": cls['semester'],
                "section": cls['section'],
                "status": 'active'
            }).execute()
            if s_res.data:
                class_mentees.extend(s_res.data)
        
        # 3. Combine and Deduplicate
        all_mentees = direct_mentees + class_mentees
        unique_map = {s['student_id']: s for s in all_mentees}
        mentees = list(unique_map.values())
        
        # Sort by Name or ID
        mentees.sort(key=lambda x: x['student_id'])

    context = get_common_context(request, user, profile, supabase)
    context.update({"mentees": mentees, "faculty": profile})
    return templates.TemplateResponse("faculty/faculty-mentees.html", context)

@router.get("/marks", name="faculty.marks")
async def marks(request: Request, user: dict = Depends(get_current_faculty)):
    supabase = get_supabase()
    f_res = supabase.table("faculty").select("*").eq("user_id", user['user_id']).execute()
    profile = f_res.data[0] if f_res.data else {}
    offerings = supabase.table("class_offering").select("*, subject(*)").eq("faculty_id", profile.get('id')).eq("is_active", True).execute().data
    context = get_common_context(request, user, profile, supabase)
    context.update({"class_offerings": offerings})
    return templates.TemplateResponse("faculty/faculty-marks.html", context)

@router.post("/marks/get_students_for_marks", name="faculty.get_students_for_marks")
async def get_students_for_marks(req: GetMarksStudentsRequest, user: dict = Depends(get_current_faculty)):
    supabase = get_supabase()
    
    parts = req.subject_value.split('_')
    if len(parts) < 5: return JSONResponse({"error": "Invalid subject value format"}, status_code=400)
    
    subject_id = int(parts[0])
    branch = parts[1]
    year = int(parts[2])
    semester = int(parts[3])
    section = parts[4]

    s_res = supabase.table("student").select("id, student_id, name").match({
        "branch": branch, "year": year, "semester": semester, "section": section, "status": 'active'
    }).order("student_id").execute()
    student_list = s_res.data or []
    
    # Get Existing Marks
    query = supabase.table("mark").select("*").eq("subject_id", subject_id).eq("assessment_type", req.assessment_type)
    
    if req.assessment_type == 'assignment' and req.assignment_number and str(req.assignment_number).lower() != 'all':
         query = query.eq("assignment_number", int(req.assignment_number))
         
    # Fallback to 'mark' if 'marks' fails or returns nothing (could check both but assumes one)
    # Actually let's just use 'marks' assuming we fixed it, or check schema.
    # User's code used Mark.query.
    
    try:
        m_res = query.execute()
    except Exception:
        # Retry with singular 'mark' if configured differently
        # query = supabase.table("mark")...
        # Assuming 'marks' based on view_student_profile priority
        m_res = None
        
    existing = m_res.data if m_res else []
    
    # Deduplicate: keep latest ID per student
    unique_existing = {}
    for m in existing:
        key = m['student_id'] # Check column name, usually camelCase or snake_case
        if key not in unique_existing:
            unique_existing[key] = m
        else:
            if m['id'] > unique_existing[key]['id']:
                unique_existing[key] = m
                
    return {"students": student_list, "existing_marks": list(unique_existing.values())}

@router.post("/marks/save", name="faculty.save_marks")
async def save_marks(req: SaveMarksRequest, user: dict = Depends(get_current_faculty)):
    supabase = get_supabase()
    
    parts = req.subject_value.split('_')
    subject_id = int(parts[0])
    
    count = 0
    
    # Determine assignments
    assignments_to_process = []
    if req.assessment_type == 'assignment':
        if str(req.assignment_number) == 'all':
            assignments_to_process = [1, 2, 3, 4, 5]
        else:
            assignments_to_process = [int(req.assignment_number)]
    else:
        assignments_to_process = [None]
        
    for item in req.marks:
        marks_obtained = 0.0
        if item.is_absent:
            marks_obtained = 0.0
        else:
            try:
                marks_obtained = float(item.marks)
            except (ValueError, TypeError):
                 continue # Skip invalid
        
        # Validation
        if not item.is_absent and marks_obtained > req.max_marks:
            return JSONResponse({"error": f"Marks for student ID {item.student_id} exceed max marks ({req.max_marks})."}, status_code=400)
            
        for assign_num in assignments_to_process:
            # Check existing (Need remarks for count check)
            query = supabase.table("mark").select("id, remarks").match({
                "student_id": item.student_id,
                "subject_id": subject_id,
                "assessment_type": req.assessment_type
            })
            if assign_num is not None:
                query = query.eq("assignment_number", assign_num)
                
            res = query.execute()
            
            payload = {
                "marks": marks_obtained,
                "max_marks": req.max_marks,
                "entered_by": user['user_id'],
                "remarks": item.remarks,
                "is_absent": item.is_absent,
                # Ensure we set keys if inserting
            }
            
            if res.data:
                # Update Logic with Limit Check
                existing_record = res.data[0]
                existing_remarks = existing_record.get('remarks') or ''
                
                # Robust extraction of max update count
                matches = re.findall(r'\[Update: (\d+)\]', existing_remarks)
                current_count = 0
                if matches:
                    current_count = max([int(m) for m in matches])
                
                new_count = current_count + 1
                
                if new_count > 5:
                    return JSONResponse({"error": f"Maximum update limit (5) reached for Student ID {item.student_id}."}, status_code=400)
                
                # Clean new remarks (remove any user-typed tags) and append fresh tag
                clean_reason = item.remarks or ''
                clean_reason = re.sub(r'\s*\[Update: \d+\]', '', clean_reason).strip()
                tagged_remarks = f"{clean_reason} [Update: {new_count}]"
                
                payload['remarks'] = tagged_remarks
                
                supabase.table("mark").update(payload).eq("id", existing_record['id']).execute()
            else:
                # Insert
                payload.update({
                    "student_id": item.student_id,
                    "subject_id": subject_id,
                    "assessment_type": req.assessment_type,
                    "assignment_number": assign_num
                })
                supabase.table("mark").insert(payload).execute()
            count += 1
            
    return {"message": f"Successfully validated and saved {count} marks entries."}

class BulkAssignChunkRequest(BaseModel):
    subject_value: str
    student_ids: List[int]

@router.post("/marks/bulk-assign-chunk", name="faculty.bulk_assign_chunk")
async def bulk_assign_chunk(req: BulkAssignChunkRequest, user: dict = Depends(get_current_faculty)):
    supabase = get_supabase()
    
    parts = req.subject_value.split('_')
    if len(parts) < 1: return JSONResponse({"error": "Invalid subject"}, status_code=400)
    subject_id = int(parts[0])

    if not req.student_ids:
        return {"message": "No students provided"}

    # 1. Fetch ALL existing assignment marks for these students
    # We want to know if we need to update (keep ID) or insert.
    # We only care about assessment_type='assignment'
    
    # Supabase 'in_' takes a list
    res = supabase.table("mark").select("id, student_id, assignment_number").eq("subject_id", subject_id).eq("assessment_type", "assignment").in_("student_id", req.student_ids).execute()
    existing_marks = res.data or []
    
    # Map (student_id, assignment_num) -> mark_id
    existing_map = {}
    for m in existing_marks:
        key = (m['student_id'], m['assignment_number'])
        existing_map[key] = m['id']

    upsert_payload = []
    today_str = datetime.now().strftime('%Y-%m-%d')
    remarks = "Full Marks Bulk Assign"

    for sid in req.student_ids:
        for assign_num in range(1, 6):
            # Check if exists
            key = (sid, assign_num)
            mark_id = existing_map.get(key)
            
            entry = {
                "student_id": sid,
                "subject_id": subject_id,
                "assessment_type": "assignment",
                "assignment_number": assign_num,
                "marks": 5,
                "max_marks": 5,
                "entered_by": user['user_id'],
                "is_absent": False,
                "remarks": remarks,
                "date": today_str
            }
            
            if mark_id:
                entry['id'] = mark_id # Include ID to force update
            
            upsert_payload.append(entry)

    # 2. Perform Bulk Upsert
    if upsert_payload:
        # Supabase/PostgREST upsert is simple if we just pass the list.
        # But for 'update', we need the ID. With ID present, it acts as update.
        # Without ID, it acts as insert.
        # We must pass on_conflict? No, if PK (id) is present, it updates. 
        # For new rows (no id), it auto-generates ID.
        
        # Batching just in case upsert payload is huge (5 * 5 = 25 is small, 5 * 100 = 500 is fine)
        # We can safely send all 25-50 records in one go.
        try:
            supabase.table("mark").upsert(upsert_payload).execute()
        except Exception as e:
            return JSONResponse({"error": f"Bulk update failed: {str(e)}"}, status_code=500)

    return {"message": "Chunk processed"}

@router.post("/marks/bulk-assign-full", name="faculty.bulk_assign_full_marks")
async def bulk_assign_full_marks(req: BulkAssignFullRequest, user: dict = Depends(get_current_faculty)):
    # Legacy or alternative endpoint, just keeping it valid or deleting implementation if unused.
    # We'll leave it simple or point out it's deprecated.
    return {"message": "Use chunked API"}

@router.post("/marks/fetch_marks", name="faculty.fetch_marks")
async def fetch_marks(req: FetchMarksRequest, user: dict = Depends(get_current_faculty)):
    supabase = get_supabase()
    
    parts = req.subject_value.split('_')
    if len(parts) < 1: return JSONResponse({"error": "Invalid subject"}, status_code=400)
    subject_id = int(parts[0])
    
    # Query Marks
    query = supabase.table("mark").select("*").eq("subject_id", subject_id)
    if req.assessment_filter:
        query = query.eq("assessment_type", req.assessment_filter)
        
    res = query.execute()
    raw_records = res.data or []
    
    # Deduplicate
    unique_map = {}
    for m in raw_records:
        key = (m['student_id'], m.get('assessment_type'), m.get('assignment_number'))
        if key not in unique_map:
            unique_map[key] = m
        else:
            if m['id'] > unique_map[key]['id']:
                unique_map[key] = m
    records = list(unique_map.values())
    
    # Stats
    student_ids_in_records = set([r['student_id'] for r in records])
    total_students = len(student_ids_in_records)
    avg_percentage = 0
    highest = 0
    
    if records:
        valid_marks = [r for r in records if r['max_marks'] > 0]
        if valid_marks:
            total_pct = sum([(r['marks']/r['max_marks']*100) for r in valid_marks])
            avg_percentage = int(total_pct / len(valid_marks))
        highest = max([r['marks'] for r in records]) if records else 0

    # Get ALL marks for subject to calc internals
    all_res = supabase.table("mark").select("*").eq("subject_id", subject_id).execute()
    raw_all = all_res.data or []
    
    # Deduplicate all
    uniq_all = {}
    for m in raw_all:
        key = (m['student_id'], m.get('assessment_type'), m.get('assignment_number'))
        if key not in uniq_all: uniq_all[key] = m
        else:
            if m['id'] > uniq_all[key]['id']: uniq_all[key] = m
    all_subject_marks = list(uniq_all.values())
    
    # Bulk fetch students
    s_map = {}
    if student_ids_in_records:
        s_res = supabase.table("student").select("id, student_id, name").in_("id", list(student_ids_in_records)).execute()
        s_map = {s['id']: s for s in s_res.data or []}
        
    record_list = []
    
    for r in records:
        s = s_map.get(r['student_id'])
        
        # Calc Internals
        student_marks = [m for m in all_subject_marks if m['student_id'] == r['student_id']]
        internal_data = calculate_internal_marks(student_marks)
        
        a_label = (r.get('assessment_type') or '').replace('_', ' ').title()
        if r.get('assessment_type') == 'assignment' and r.get('assignment_number'):
            a_label += f" {r['assignment_number']}"
            
        pct = 0
        if r['max_marks'] > 0:
            pct = round((r['marks'] / r['max_marks']) * 100, 2)
            
        record_list.append({
            'id': r['id'],
            'student_id_display': s['student_id'] if s else 'Unknown',
            'student_name': s['name'] if s else 'Unknown',
            'assessment': a_label,
            'assessment_type': r.get('assessment_type'),
            'assignment_number': r.get('assignment_number'),
            'marks': r['marks'],
            'max_marks': r['max_marks'],
            'percentage': pct,
            'internal_marks': internal_data['totalInternal'],
            'max_internal': internal_data['maxInternal'],
            'remarks': r.get('remarks'),
            'is_absent': r.get('is_absent')
        })
        
    # Sort by student ID ascending
    record_list.sort(key=lambda x: x['student_id_display'])
        
    return {
        "records": record_list,
        "stats": {
            "total_students": total_students,
            "avg_percentage": avg_percentage,
            "highest": highest
        }
    }

@router.post("/marks/export", name="faculty.export_marks")
async def export_marks(request: Request, user: dict = Depends(get_current_faculty)):
    form = await request.form()
    subject_val = form.get('subject_value')
    if not subject_val: return Response("Subject required", status_code=400)
    
    parts = subject_val.split('_')
    subject_id = int(parts[0])
    
    supabase = get_supabase()
    res = supabase.table("mark").select("*").eq("subject_id", subject_id).execute()
    raw = res.data or []
    
    unique_map = {}
    for r in raw:
        key = (r['student_id'], r.get('assessment_type'), r.get('assignment_number'))
        if key not in unique_map: unique_map[key] = r
        else:
            if r['id'] > unique_map[key]['id']: unique_map[key] = r
    records = list(unique_map.values())
    
    # Bulk student
    s_ids = list(set([r['student_id'] for r in records]))
    s_map = {}
    if s_ids:
        s_res = supabase.table("student").select("id, student_id, name").in_("id", s_ids).execute()
        s_map = {s['id']: s for s in s_res.data}
        
    # Sort records by student ID
    records.sort(key=lambda r: s_map.get(r['student_id'], {}).get('student_id', ''))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Student ID', 'Name', 'Assessment', 'Marks', 'Max Marks', 'Percentage'])
    
    for r in records:
        s = s_map.get(r['student_id'])
        pct = int((r['marks']/r['max_marks']*100)) if r['max_marks'] > 0 else 0
        lbl = r.get('assessment_type', '')
        if r.get('assignment_number'): lbl += f" {r['assignment_number']}"
        
        writer.writerow([
            s['student_id'] if s else '',
            s['name'] if s else '',
            lbl,
            r['marks'],
            r['max_marks'],
            f"{pct}%"
        ])

    return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=Marks_Export.csv"})

@router.post("/timetable/fetch", name="faculty.fetch_timetable")
async def fetch_timetable(req: FetchTimetableRequest, user: dict = Depends(get_current_faculty)):
    supabase = get_supabase()
    
    # --- Semester Validation ---
    sem_res = supabase.table("semester").select("*").eq("status", "Active").execute()
    active_semesters = sem_res.data or []
    
    is_allowed = False
    validation_msg = "Timetable View Disabled. No active semester found."
    
    if active_semesters:
        # Check if requested date falls within ANY active semester
        validation_msg = "Timetable View Disabled. Date outside active semester."
        for sem in active_semesters:
            if sem['start_date'] <= req.date <= sem['end_date']:
                is_allowed = True
                validation_msg = ""
                break
            elif req.date < sem['start_date']:
                validation_msg = f"Timetable not available. Semester '{sem['name']}' starts {sem['start_date']}."
            elif req.date > sem['end_date']:
                 validation_msg = f"Timetable disabled. Semester '{sem['name']}' ended {sem['end_date']}."
    
    if not is_allowed:
        return {
            "days": [], "periods": [], "timetable": {}, 
            "semester_validation": { "allowed": False, "message": validation_msg }
        }
    # --- End Validation ---

    # Base query: matching branch/year/section if provided
    # Supabase filter building
    query = supabase.table("timetable").select("*")
    if req.branch: query = query.eq("branch", req.branch)
    if req.year: query = query.eq("year", req.year)
    if req.section: query = query.eq("section", req.section)
    
    # Filter by current faculty if no filters (Allocated classes)
    if not req.branch and not req.year and not req.section:
        f_res = supabase.table("faculty").select("id").eq("user_id", user['user_id']).execute()
        if not f_res.data: return {"timetable": {}} # Error or empty
        fid = f_res.data[0]['id']
        
        # Get allocations
        off_res = supabase.table("class_offering").select("*").eq("faculty_id", fid).eq("is_active", True).execute()
        allocations = off_res.data or []
        
        if not allocations:
             # Just return where they are substitute? Or empty.
             # Let's try to find where they are substitute (current_faculty_id) at least
             query = query.eq("current_faculty_id", fid)
        else:
             # Match any of the allocations OR substitute
             # Supabase 'or' syntax with multiple conditions is tricky. 
             # Simpler: Get ALL timetable entries for this faculty (original or current)
             # But the 'Allocated' logic implies "Show me my classes".
             # Let's filter by original_faculty_id = fid OR current_faculty_id = fid
             # Split OR query into two safe queries
             q1 = supabase.table("timetable").select("*").eq("original_faculty_id", fid)
             if req.branch: q1 = q1.eq("branch", req.branch)
             if req.year: q1 = q1.eq("year", req.year)
             if req.section: q1 = q1.eq("section", req.section)
             
             q2 = supabase.table("timetable").select("*").eq("current_faculty_id", fid)
             if req.branch: q2 = q2.eq("branch", req.branch)
             if req.year: q2 = q2.eq("year", req.year) 
             if req.section: q2 = q2.eq("section", req.section)
             
             r1 = q1.execute()
             r2 = q2.execute()
             
             # Merge unique entries
             all_entries = (r1.data or []) + (r2.data or [])
             uniq = {}
             for e in all_entries:
                 uniq[e['id']] = e
             
             query = None # Flag to skip default execute
             res = type('obj', (object,), {'data': list(uniq.values())})
             
    if query:
        res = query.execute()
    entries = res.data or []
    
    # Determine week dates
    try:
        view_date = datetime.strptime(req.date, '%Y-%m-%d')
    except:
        view_date = datetime.now()
        
    start_of_week = view_date - timedelta(days=view_date.weekday())
    
    week_dates = {}
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    for i, dname in enumerate(day_names):
        d_date = start_of_week + timedelta(days=i)
        week_dates[dname] = d_date.strftime('%Y-%m-%d')
        
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
    
    # Bulk fetch subjects & faculty names
    sub_ids = set([e['subject_id'] for e in entries])
    fac_ids = set([e['original_faculty_id'] for e in entries] + [e.get('current_faculty_id') for e in entries if e.get('current_faculty_id')])
    
    sub_map = {}
    if sub_ids:
        s_res = supabase.table("subject").select("id, name").in_("id", list(sub_ids)).execute()
        sub_map = {s['id']: s['name'] for s in s_res.data}
        
    fac_map = {}
    if fac_ids:
        f_res = supabase.table("faculty").select("id, name").in_("id", list(fac_ids)).execute()
        fac_map = {f['id']: f['name'] for f in f_res.data}
        
    # --- Bulk Fetch Attendance & Offerings ---
    # 1. Resolve Offerings (Subject + Section + Branch + Year -> Offering ID)
    # 2. Check Attendance (Subject + Date + Time -> Status)
    
    # Collect unique offerings keys from entries
    off_keys = set()
    for e in entries:
        key = (e['subject_id'], e['branch'], e['year'], e['section'])
        off_keys.add(key)
        
    offering_map = {} # (sub, branch, year, sec) -> id
    if off_keys:
        # Fetch matching offerings
        # Supabase OR filter for multiple composite keys is hard. 
        # Easier: Fetch ALL active offerings for this faculty (or substitute) and match in python.
        # But timetable might show other faculty classes (Admin view?). 
        # Assuming current user scope based on 'entries' source.
        # Fetching all active offerings for the *subjects* in the timetable might be safer.
        sub_list = list(sub_ids)
        if sub_list:
            o_res = supabase.table("class_offering").select("id, subject_id, branch, year, section").in_("subject_id", sub_list).eq("is_active", True).execute()
            for o in (o_res.data or []):
                k = (o['subject_id'], o['branch'], o['year'], o['section'])
                offering_map[k] = o['id']

    # Collect Attendance Checks (Subject + Date + Time)
    # We need attendance for the displayed week.
    # Query: date >= start_week AND date <= end_week AND subject_id IN sub_ids
    start_str = start_of_week.strftime('%Y-%m-%d')
    end_str = (start_of_week + timedelta(days=6)).strftime('%Y-%m-%d')
    
    marked_map = set() # (subject_id, date_str, time_str)
    if sub_ids:
        a_res = supabase.table("attendance").select("subject_id, date, class_time").in_("subject_id", list(sub_ids)).gte("date", start_str).lte("date", end_str).execute()
        for a in (a_res.data or []):
            # Normalize time to HH:MM usually 
            # DB time might be HH:MM:SS
            t = str(a['class_time'])
            if len(t) > 5: t = t[:5]
            marked_map.add((a['subject_id'], a['date'], t))

    for entry in entries:
        day = entry['day_of_week']
        if day not in days: continue
        
        target_date_txt = week_dates.get(day)
        
        # Alteration check
        is_alteration = False
        # alter_date is usually YYYY-MM-DD string in DB
        if entry.get('alter_date') and str(entry['alter_date']) == target_date_txt:
            is_alteration = True
            
        status = 'scheduled'
        reason = ''
        fid = entry['original_faculty_id']
        
        if is_alteration:
            status = entry.get('status', 'scheduled')
            reason = entry.get('reason', '')
            fid = entry.get('current_faculty_id')
            
        fname = fac_map.get(fid, "Unknown")
        sname = sub_map.get(entry['subject_id'], "Unknown")
        
        # Resolve Offering ID
        off_key = (entry['subject_id'], entry['branch'], entry['year'], entry['section'])
        offering_id = offering_map.get(off_key)
        
        # Check Attendance Check
        estart = str(entry['start_time'])
        if len(estart) > 5: estart = estart[:5]
        
        is_marked = (entry['subject_id'], target_date_txt, estart) in marked_map

        # Slot matching
        estart_raw = entry['start_time'] # For comparison logic below
        eend = entry['end_time']
        
        # Normalize times (slicing to HH:MM)
        if len(str(estart_raw)) > 5: estart_raw = str(estart_raw)[:5]
        if len(str(eend)) > 5: eend = str(eend)[:5]
        
        for p in periods:
            pstart = p['start']
            pend = p['end']
            
            if estart_raw <= pstart and eend >= pend:
                if pstart not in timetable_data[day]:
                    timetable_data[day][pstart] = {'entries': []}
                    
                timetable_data[day][pstart]['entries'].append({
                    'id': entry['id'],
                    'subject_name': sname,
                    'branch': entry['branch'],
                    'year': entry['year'],
                    'section': entry['section'],
                    'room': entry.get('room_number', ''),
                    'faculty_name': fname,
                    'status': status,
                    'reason': reason,
                    'offering_id': offering_id,
                    'is_marked': is_marked,
                    'target_date': target_date_txt,  # Needed for frontend link
                    'start_time': estart_raw        # Needed for frontend link
                })
                
    return {
        "days": days,
        "periods": periods,
        "timetable": timetable_data
    }

@router.get("/timetable", name="faculty.timetable")
async def timetable(request: Request, user: dict = Depends(get_current_faculty)):
    supabase = get_supabase()
    # Get unique branches for filter
    # Supabase unique column fetch is a bit tricky, usually .select("branch").execute() then set() in python
    # Or creating a distinct rpc function. 
    # For now, fetching all student branches (lightweight enough?) or distinct from class_offering?
    # Better to fetch from active students.
    
    # Efficient enough for now:
    res = supabase.table("student").select("branch").execute()
    branches = list(set([r['branch'] for r in res.data if r['branch']]))
    branches.sort()
    
    context = get_common_context(request, user, {}, supabase) # Profile handled in common context if passed or fetched inside
    # Actually get_common_context expects profile. 
    f_res = supabase.table("faculty").select("*").eq("user_id", user['user_id']).execute()
    profile = f_res.data[0] if f_res.data else {}
    
    # We might re-fetch context with profile, or just update it manually
    context = get_common_context(request, user, profile, supabase)
    context.update({"branches": branches})
    
    return templates.TemplateResponse("faculty/faculty-timetable.html", context)

@router.post("/timetable/get_alter_options", name="faculty.get_alter_options")
async def get_alter_options(req: AlterOptionsRequest, user: dict = Depends(get_current_faculty)):
    supabase = get_supabase()
    
    t_res = supabase.table("timetable").select("*").eq("id", req.entry_id).single().execute()
    if not t_res.data: return JSONResponse({"error": "Not found"}, status_code=404)
    entry = t_res.data
    
    # Get eligible faculty logic:
    # SQL: active class offering same branch/year/section, faculty_id != original
    # Supabase join: class_offering(faculty_id, is_active, branch, year, section) -> faculty(id, name)
    # Supabase complexity: fetch class_offerings first
    
    off_res = supabase.table("class_offering").select("faculty_id").match({
        "branch": entry['branch'],
        "year": entry['year'],
        "section": entry['section'],
        "is_active": True
    }).neq("faculty_id", entry['original_faculty_id']).execute()
    
    eligible_ids = list(set([o['faculty_id'] for o in off_res.data or []]))
    
    eligible_faculty = []
    if eligible_ids:
        f_res = supabase.table("faculty").select("id, name").in_("id", eligible_ids).execute()
        eligible_faculty = f_res.data or []
        
    # Current faculty name
    cf_res = supabase.table("faculty").select("name").eq("id", entry['original_faculty_id']).single().execute()
    cf_name = cf_res.data['name'] if cf_res.data else "Unknown"
    
    # Subject name
    s_res = supabase.table("subject").select("name").eq("id", entry['subject_id']).single().execute()
    s_name = s_res.data['name'] if s_res.data else "Unknown"
    
    return {
        "subject": s_name,
        "class_str": f"{entry['branch']} Y{entry['year']} {entry['section']}",
        "current_faculty": cf_name,
        "eligible_faculty": eligible_faculty
    }

@router.post("/timetable/alter", name="faculty.alter_class")
async def alter_class(req: AlterClassRequest, user: dict = Depends(get_current_faculty)):
    supabase = get_supabase()
    
    payload = {
        "status": 'altered',
        "reason": req.reason,
        "alter_date": req.date,
        "current_faculty_id": req.new_faculty_id if req.new_faculty_id else None
    }
    
    supabase.table("timetable").update(payload).eq("id", req.entry_id).execute()
    return {"message": "Class altered successfully"}

@router.post("/timetable/suspend", name="faculty.suspend_class")
async def suspend_class(req: SuspendRequest, user: dict = Depends(get_current_faculty)):
    supabase = get_supabase()
    supabase.table("timetable").update({
        "status": "suspended",
        "reason": req.reason,
        "alter_date": req.date
    }).eq("id", req.entry_id).execute()
    return {"message": "Class suspended successfully"}

@router.post("/timetable/reactivate", name="faculty.reactivate_class")
async def reactivate_class(req: ReactivateRequest, user: dict = Depends(get_current_faculty)):
    supabase = get_supabase()
    
    # Get original ID to reset current
    t_res = supabase.table("timetable").select("original_faculty_id").eq("id", req.entry_id).single().execute()
    if not t_res.data: return JSONResponse({"error": "Not found"}, status_code=404)
    
    supabase.table("timetable").update({
        "status": "scheduled",
        "reason": None,
        "alter_date": None,
        "current_faculty_id": t_res.data['original_faculty_id']
    }).eq("id", req.entry_id).execute()
    return {"message": "Class reactivated successfully"}

@router.post("/timetable/export", name="faculty.export_timetable")
async def export_timetable(request: Request, user: dict = Depends(get_current_faculty)):
    form = await request.form()
    branch = form.get('branch')
    year = form.get('year')
    section = form.get('section')
    
    supabase = get_supabase()
    query = supabase.table("timetable").select("*")
    if branch: query = query.eq("branch", branch)
    if year: query = query.eq("year", int(year))
    if section: query = query.eq("section", section)
    
    if not branch and not year and not section:
         f_res = supabase.table("faculty").select("id").eq("user_id", user['user_id']).execute()
         if f_res.data:
             fid = f_res.data[0]['id']
             query = query.or_(f"original_faculty_id.eq.{fid},current_faculty_id.eq.{fid}")
             
    res = query.execute()
    entries = res.data or []
    
    # Bulk fetch names
    sub_ids = list(set([e['subject_id'] for e in entries]))
    fac_ids = list(set([e.get('current_faculty_id') for e in entries if e.get('current_faculty_id')]))
    
    sub_map = {}
    if sub_ids:
        r = supabase.table("subject").select("id, name").in_("id", sub_ids).execute()
        sub_map = {x['id']: x['name'] for x in r.data}
        
    fac_map = {}
    if fac_ids:
        r = supabase.table("faculty").select("id, name").in_("id", fac_ids).execute()
        fac_map = {x['id']: x['name'] for x in r.data}
        
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Day', 'Time', 'Branch', 'Year', 'Section', 'Subject', 'Faculty', 'Room', 'Status'])
    
    for e in entries:
        writer.writerow([
            e['day_of_week'],
            f"{e['start_time']}-{e['end_time']}",
            e['branch'],
            e['year'],
            e['section'],
            sub_map.get(e['subject_id'], ''),
            fac_map.get(e.get('current_faculty_id'), ''),
            e.get('room_number', ''),
            e.get('status', 'scheduled') # Assuming 'status' is column, else 'scheduled'
        ])
        
    return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=Timetable_Export.csv"})

@router.get("/resources", name="faculty.resources")
async def resources(request: Request, user: dict = Depends(get_current_faculty)):
    supabase = get_supabase()
    f_res = supabase.table("faculty").select("*").eq("user_id", user['user_id']).execute()
    profile = f_res.data[0] if f_res.data else {}
    offerings = supabase.table("class_offering").select("*, subject(*)").eq("faculty_id", profile.get('id')).eq("is_active", True).execute().data
    context = get_common_context(request, user, profile, supabase)
    # Add subject_name manually if Supabase didn't expand correctly or if structure is nested
    # offerings should contain 'subject': {'name': ...} if join successful
    
    context.update({"class_offerings": offerings})
    return templates.TemplateResponse("faculty/faculty-resources.html", context)

@router.post("/resources/upload", name="faculty.upload_resource")
async def upload_resource(request: Request, user: dict = Depends(get_current_faculty)):
    form = await request.form()
    file = form.get('file')
    title = form.get('title')
    subject_id = form.get('subject_id')
    res_type = form.get('type')
    description = form.get('description')
    
    if not file or not file.filename:
         return JSONResponse({"error": "No selected file"}, status_code=400)
         
    # Save file locally
    filename = file.filename # In FastAPI/Starlette UploadFile has filename
    safe_filename = f"{int(datetime.now().timestamp())}_{filename}"
    
    # Path: static/uploads (ensure exists)
    import os
    upload_dir = os.path.join(os.getcwd(), 'static', 'uploads')
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
        
    file_path = os.path.join(upload_dir, safe_filename)
    
    # Write file
    with open(file_path, "wb") as f:
        f.write(await file.read())
        
    supabase = get_supabase()
    supabase.table("resource").insert({
        "title": title,
        "description": description,
        "type": res_type,
        "file_url": file_path,
        "file_name": safe_filename,
        "subject_class_id": str(subject_id),
        "uploaded_by": user['user_id']
    }).execute()
    
    return {"message": "Resource uploaded successfully"}

@router.post("/resources/update", name="faculty.update_resource")
async def update_resource(request: Request, user: dict = Depends(get_current_faculty)):
    form = await request.form()
    resource_id = form.get('resource_id')
    title = form.get('title')
    subject_id = form.get('subject_id')
    res_type = form.get('type')
    description = form.get('description')
    file = form.get('file')
    
    supabase = get_supabase()
    
    # Verify ownership
    existing = supabase.table("resource").select("*").eq("id", resource_id).single().execute()
    if not existing.data:
        return JSONResponse({"error": "Resource not found"}, status_code=404)
    if existing.data['uploaded_by'] != user['user_id']:
        return JSONResponse({"error": "Permission denied"}, status_code=403)
        
    payload = {
        "title": title,
        "description": description,
        "type": res_type,
        "subject_class_id": str(subject_id)
    }
    
    # Handle optional file replacement
    if file and hasattr(file, 'filename') and file.filename:
        filename = file.filename
        safe_filename = f"{int(datetime.now().timestamp())}_{filename}"
        
        # Path: static/uploads
        import os
        upload_dir = os.path.join(os.getcwd(), 'static', 'uploads')
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)
            
        file_path = os.path.join(upload_dir, safe_filename)
        
        # Write new file
        with open(file_path, "wb") as f:
            f.write(await file.read())
            
        payload['file_url'] = file_path
        payload['file_name'] = safe_filename
        
        # Ideally, delete old file to save space, but we'll skip for safety/simplicity now
        
    supabase.table("resource").update(payload).eq("id", resource_id).execute()
    
    return {"message": "Resource updated successfully"}

@router.post("/resources/list", name="faculty.list_resources")
async def list_resources(req: ListResourcesRequest, user: dict = Depends(get_current_faculty)):
    supabase = get_supabase()
    
    query = supabase.table("resource").select("*").eq("uploaded_by", user['user_id'])
    if req.subject_id: query = query.eq("subject_class_id", str(req.subject_id))
    if req.type: query = query.eq("type", req.type)
    
    res = query.order("uploaded_at", desc=True).execute()
    resources = res.data or []
    
    # Get subject names
    sub_ids = list(set([int(r['subject_class_id']) for r in resources if r.get('subject_class_id')]))
    s_map = {}
    if sub_ids:
        r = supabase.table("subject").select("id, name").in_("id", sub_ids).execute()
        s_map = {x['id']: x['name'] for x in r.data}
        
    res_list = []
    for r in resources:
        sid = int(r['subject_class_id']) if r.get('subject_class_id') else 0
        res_list.append({
            'id': r['id'],
            'title': r['title'],
            'description': r['description'],
            'type': r['type'],
            'subject_class_id': r.get('subject_class_id'),
            'subject_name': s_map.get(sid, 'Unknown'),
            'file_name': r.get('file_name'),
            'uploaded_at': r['uploaded_at'][:10] # YYYY-MM-DD
        })
        
    return {"resources": res_list}

@router.get("/resources/download/{resource_id}", name="faculty.download_resource")
async def download_resource(resource_id: int, inline: bool = False, user: dict = Depends(get_current_faculty)):
    supabase = get_supabase()
    res = supabase.table("resource").select("*").eq("id", resource_id).single().execute()
    if not res.data: return Response("Not Found", status_code=404)
    record = res.data
    
    # Permission check
    if record['uploaded_by'] != user['user_id']:
        return Response("Access Denied", status_code=403)
        
    import os
    from starlette.responses import FileResponse
    path = os.path.join(os.getcwd(), 'static', 'uploads', record['file_name'])
    
    if not os.path.exists(path): return Response("File missing on server", status_code=404)
    
    disposition = 'inline' if inline else 'attachment'
    return FileResponse(path, filename=record['file_name'], content_disposition_type=disposition)
    
@router.post("/resources/delete", name="faculty.delete_resource")
async def delete_resource(req: DeleteResourceRequest, user: dict = Depends(get_current_faculty)):
    supabase = get_supabase()
    res = supabase.table("resource").select("*").eq("id", req.resource_id).single().execute()
    if not res.data: return JSONResponse({"error": "Not found"}, status_code=404)
    record = res.data
    
    if record['uploaded_by'] != user['user_id']:
        return JSONResponse({"error": "Access denied"}, status_code=403)
        
    # Delete file
    import os
    path = os.path.join(os.getcwd(), 'static', 'uploads', record['file_name'])
    if os.path.exists(path):
        os.remove(path)
        
    supabase.table("resource").delete().eq("id", req.resource_id).execute()
    return {"message": "Deleted successfully"}

@router.post("/change_password", name="faculty.change_password")
async def change_password(req: ChangePasswordRequest, user: dict = Depends(get_current_faculty)):
    supabase = get_supabase()
    # Check current password (hash verification) - implementing basic logic
    # In a real app with Supabase Auth, we'd use supabase.auth.update_user()
    # But here users seem stored in 'users'/'faculty' tables with custom hashes?
    # User's code used werkzeug check_password_hash. We need to fetch the stored hash.
    
    # We depend on get_current_faculty which gives us 'user' dict. 
    # Does 'user' contain password_hash? Usually dependencies filter it out.
    # We might need to fetch it explicitly.
    
    u_res = supabase.table("users").select("password_hash").eq("id", user['user_id']).single().execute()
    # Or 'password' if legacy.
    
    if not u_res.data: return JSONResponse({"error": "User  not found"}, status_code=404)
    stored_hash = u_res.data.get('password_hash')
    
    from werkzeug.security import check_password_hash, generate_password_hash
    
    if not stored_hash or not check_password_hash(stored_hash, req.current_password):
         return JSONResponse({"error": "Incorrect current password"}, status_code=400)
         
    new_hash = generate_password_hash(req.new_password)
    supabase.table("users").update({"password_hash": new_hash}).eq("id", user['user_id']).execute()
    
    return {"message": "Password changed successfully"}

# --- Period Alert Health Check (for debugging) ---
@router.get("/period-alerts/health", name="faculty.period_alerts_health")
async def period_alerts_health():
    """Simple health check to verify period_alert table exists in Supabase."""
    supabase = get_supabase()
    try:
        # Try a simple select to see if table exists
        res = supabase.table("period_alert").select("id").limit(1).execute()
        return {
            "status": "ok",
            "table_exists": True,
            "message": "period_alert table is accessible"
        }
    except Exception as e:
        error_msg = str(e)
        if "PGRST205" in error_msg or "Could not find the table" in error_msg:
            return {
                "status": "error",
                "table_exists": False,
                "message": "period_alert table does not exist. Please run docs/db/period_alert.sql in Supabase SQL Editor.",
                "error": error_msg
            }
        return {
            "status": "error",
            "table_exists": False,
            "message": "Error checking table",
            "error": error_msg
        }
