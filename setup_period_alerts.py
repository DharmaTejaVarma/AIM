
def print_setup_sql():
    sql = """
-- Create period_alert table
CREATE TABLE IF NOT EXISTS public.period_alert (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    alerted_by UUID NOT NULL, -- references faculty(id) but stored as UUID for now or convert
    alerted_to UUID NOT NULL, -- references faculty(id)
    period_id UUID NOT NULL,  -- references timetable(id)
    period_date DATE NOT NULL,
    period_time TEXT NOT NULL,
    subject TEXT,
    class_name TEXT,
    reason TEXT,
    status TEXT DEFAULT 'PENDING',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Enable RLS
ALTER TABLE public.period_alert ENABLE ROW LEVEL SECURITY;

-- Policy (Open for now, refine later)
CREATE POLICY "Enable all access for authenticated users" ON "public"."period_alert"
AS PERMISSIVE FOR ALL
TO authenticated
USING (true)
WITH CHECK (true);
    """
    print("Run this SQL in your Supabase SQL Editor:")
    print(sql)

if __name__ == "__main__":
    print_setup_sql()
