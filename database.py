import os
from typing import Generator
from dotenv import load_dotenv
from sqlalchemy import Column, String, UniqueConstraint, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session


# Load environment variables from the local .env file.
load_dotenv()

DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "assessment_db")

# Database URL
DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


# Connection pool to MySQL:

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True, # Tests connections before checkout to detect stale/dropped connections.
    pool_recycle=3600, # Refreshes idle connections every hour to avoid MySQL timeout drops.
)

# Distinct database transaction sessions for incoming requests
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class used by SQLAlchemy ORM models
Base = declarative_base()


class Assessment(Base):
    """
    Represents the 'assessment' table in the MySQL database.
    Maps Python object attributes directly to table columns.
    """
    __tablename__ = "assessment"

    # UUID v4 string stored as a fixed-length 36-character primary key
    userID = Column(String(36), primary_key=True)

    # Identifiers 
    id1 = Column(String(255), nullable=False)
    id2 = Column(String(255), nullable=False)

    # Ensure uniqueness across the (id1, id2) pair.
    __table_args__ = (
        UniqueConstraint("id1", "id2", name="uq_id1_id2"),
    )


def get_db() -> Generator[Session, None, None]:
    #Ensures the session is cleanly closed once the HTTP response is completed

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()