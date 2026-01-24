from ..supabase_client import get_supabase

class PromotionService:
    def __init__(self):
        self.supabase = get_supabase()

    def promote_students(self, current_year: int, current_semester: int, target_course_id: str):
        """
        Promotes all ACTIVE students from (Year X, Sem Y) to their next logical stage.
        Logic:
           - Sem 1 -> Sem 2 (Same Year)
           - Sem 2 -> Sem 3 (Next Year)
           - Sem 8 -> Passed Out
        """
        
        # 1. Fetch Eligible Students
        # Mapping SQL columns: current_year, current_semester
        # We assume database schema has these columns. If not, we might need to rely on 'class_offering' logic
        # But 'student' table was requested to have these.
        
        try:
            # We filter by course_id logically if we had it in DB, but for now we assume all B.Tech
            res = self.supabase.table("student")\
                .select("id, current_year, current_semester")\
                .eq("current_year", current_year)\
                .eq("current_semester", current_semester)\
                .eq("status", "active")\
                .execute()
                
            students = res.data
            if not students:
                return {"count": 0, "message": "No eligible students found"}

            updates = []
            next_sem = current_semester + 1
            
            # 2. Determine Next State
            if current_semester == 8:
                # Graduation
                for s in students:
                    updates.append({
                        "id": s['id'],
                        "status": "passed_out", 
                        "current_semester": 8 # Cap at 8
                    })
            elif current_semester % 2 == 0:
                # Even Semester -> Next Year (2->3, 4->5, 6->7)
                next_year = current_year + 1
                for s in students:
                    updates.append({
                        "id": s['id'],
                        "current_year": next_year,
                        "current_semester": next_sem
                    })
            else:
                # Odd Semester -> Same Year (1->2, 3->4, 5->6, 7->8)
                for s in students:
                    updates.append({
                        "id": s['id'],
                        "current_semester": next_sem
                    })
            
            # 3. Batch Update (Simulated via loop as Supabase bulk update is tricky without upsert)
            count = 0
            for u in updates:
                self.supabase.table("student").update(u).eq("id", u['id']).execute()
                count += 1
                
            return {"count": count, "message": f"Promoted {count} students"}

        except Exception as e:
            print(f"Promotion Error: {e}")
            raise e
