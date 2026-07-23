import os
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/tmr_db")

engine = create_engine(DATABASE_URL)

def get_db_connection():
    return engine.connect()
