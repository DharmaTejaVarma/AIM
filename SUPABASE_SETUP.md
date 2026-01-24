# Supabase Setup Guide for Campus Management System

## Prerequisites
- Supabase account (sign up at https://supabase.com)
- Python 3.8 or higher
- Git (optional)

## Step 1: Create Supabase Project

1. Go to https://supabase.com and sign in
2. Click "New Project"
3. Fill in project details:
   - **Name**: Campus Management System
   - **Database Password**: Choose a strong password (save this!)
   - **Region**: Choose closest to your location
4. Wait for project to be created (~2 minutes)

## Step 2: Get Database Connection String

1. In your Supabase dashboard, go to **Project Settings** (gear icon)
2. Navigate to **Database** section
3. Scroll down to **Connection String**
4. Select **URI** tab
5. Copy the connection string (looks like):
   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
   ```
6. Replace `[YOUR-PASSWORD]` with your actual database password

## Step 3: Get API Keys (Optional)

1. In Supabase dashboard, go to **Project Settings** > **API**
2. Copy the following:
   - **Project URL**: `https://[PROJECT-REF].supabase.co`
   - **anon/public key**: For client-side operations
   - **service_role key**: For admin operations (keep secret!)

## Step 4: Configure Your Application

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Create Environment File:**
   ```bash
   # Copy the example file
   copy .env.example .env
   ```

3. **Edit `.env` file** with your Supabase credentials:
   ```env
   # Flask Configuration
   SECRET_KEY=your-random-secret-key-here
   FLASK_ENV=development
   DEBUG=True

   # Supabase Database
   SUPABASE_DB_URI=postgresql://postgres:YOUR_PASSWORD@db.YOUR_PROJECT_REF.supabase.co:5432/postgres

   # Supabase API (Optional)
   SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
   SUPABASE_ANON_KEY=your-anon-key
   SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
   ```

## Step 5: Initialize Database

1. **Run the application** (this will create tables):
   ```bash
   python app.py
   ```

2. **Verify tables were created:**
   - Go to Supabase Dashboard > **Table Editor**
   - You should see tables: users, students, faculty, departments, etc.

## Step 6: (Optional) Seed Sample Data

If you want to populate the database with sample data:

```bash
python seed_database.py
```

## Troubleshooting

### Connection Error: "could not connect to server"
- Check your database password is correct
- Verify your IP is allowed (Supabase allows all IPs by default)
- Check your internet connection

### SSL Error
Add `?sslmode=require` to your connection string:
```
postgresql://postgres:password@db.ref.supabase.co:5432/postgres?sslmode=require
```

### "relation does not exist" Error
- Run `python app.py` to create tables
- Check that `db.create_all()` is being called

## Security Best Practices

1. **Never commit `.env` file** to Git
2. **Use strong passwords** for database
3. **Keep service_role key secret** (never expose in client-side code)
4. **Enable Row Level Security (RLS)** in Supabase for production
5. **Use environment variables** for all sensitive data

## Supabase Features You Can Use

### 1. Real-time Subscriptions
Listen to database changes in real-time

### 2. Storage
Store files (student documents, resources, etc.)

### 3. Authentication
Use Supabase Auth instead of Flask-Login (optional)

### 4. Edge Functions
Run serverless functions

### 5. Database Backups
Automatic daily backups (paid plans)

## Migration from SQLite to Supabase

Your existing SQLite data can be migrated:

1. **Export SQLite data:**
   ```bash
   python export_sqlite_data.py
   ```

2. **Import to Supabase:**
   ```bash
   python import_to_supabase.py
   ```

## Monitoring

- **Database Usage**: Supabase Dashboard > Database > Usage
- **API Requests**: Supabase Dashboard > API > Logs
- **Performance**: Supabase Dashboard > Database > Query Performance

## Support

- Supabase Docs: https://supabase.com/docs
- Supabase Discord: https://discord.supabase.com
- GitHub Issues: https://github.com/supabase/supabase/issues

## Next Steps

1. ✅ Set up Supabase project
2. ✅ Configure environment variables
3. ✅ Run application and create tables
4. 🔲 Seed sample data (optional)
5. 🔲 Configure Row Level Security (production)
6. 🔲 Set up backups (production)
7. 🔲 Deploy application
