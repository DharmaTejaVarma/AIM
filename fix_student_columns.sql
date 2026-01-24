-- MINIMAL FIX for Student Import Error
-- Run this in Supabase SQL Editor

ALTER TABLE public.student ADD COLUMN IF NOT EXISTS batch TEXT;
ALTER TABLE public.student ADD COLUMN IF NOT EXISTS phone TEXT;
ALTER TABLE public.student ADD COLUMN IF NOT EXISTS address TEXT;
ALTER TABLE public.student ADD COLUMN IF NOT EXISTS father_name TEXT;
ALTER TABLE public.student ADD COLUMN IF NOT EXISTS mother_name TEXT;
ALTER TABLE public.student ADD COLUMN IF NOT EXISTS parents_phone TEXT;
ALTER TABLE public.student ADD COLUMN IF NOT EXISTS date_of_birth DATE;
ALTER TABLE public.student ADD COLUMN IF NOT EXISTS admission_date DATE;

-- Reload Schema Cache
NOTIFY pgrst, 'reload schema';
