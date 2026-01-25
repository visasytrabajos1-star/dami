from sqlmodel import SQLModel, create_engine, Session
import os
from dotenv import load_dotenv

load_dotenv()

# Render provides DATABASE_URL, Supabase provides it too.
# Render provides DATABASE_URL. Supabase uses SUPABASE_DATABASE_URL for transaction pooler usually.
# If SUPABASE_DATABASE_URL is set, use it. Otherwise fall back to DATABASE_URL.
raw_url = os.getenv("SUPABASE_DATABASE_URL", os.getenv("DATABASE_URL"))
DATABASE_URL = raw_url.strip() if raw_url else None

if DATABASE_URL:
    # Debug print to verify correct URL usage (masking password)
    try:
        from sqlalchemy.engine.url import make_url
        u = make_url(DATABASE_URL)
        print(f"INFO: Connecting to Host: {u.host}, Port: {u.port}, User: {u.username}, DB: {u.database}")
    except Exception as e:
        print(f"WARNING: Could not parse DATABASE_URL for debug: {e}")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase_client = None

if SUPABASE_URL and SUPABASE_KEY:
    try:
        from supabase import create_client, Client
        supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    except ImportError:
        print("WARNING: Supabase client library not installed or failed to import.")
    except Exception as e:
         print(f"WARNING: Failed to init Supabase client: {e}")

if not DATABASE_URL:
    # Fallback/Dev config - ensure you have a .env file or set this env var
    print("WARNING: DATABASE_URL not set. Database operations will fail.")
    DATABASE_URL = "sqlite:///./test.db" # Fallback for local testing if env missing

# check_same_thread=False is needed only for SQLite
connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}

# Verify if we need sslmode=require for postgres (usually needed for hosted DBs)
if "postgresql" in DATABASE_URL and "sslmode" not in DATABASE_URL:
     if "?" in DATABASE_URL:
         DATABASE_URL += "&sslmode=require"
     else:
         DATABASE_URL += "?sslmode=require"

engine = create_engine(DATABASE_URL, connect_args=connect_args)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
