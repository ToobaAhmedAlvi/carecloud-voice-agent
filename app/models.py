"""
CareCloud Patient Registration — Database Models
SQLite via SQLAlchemy for simplicity & portability.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Date, DateTime, Enum, Text, create_engine
)
from sqlalchemy.orm import declarative_base, sessionmaker
import enum
import os

Base = declarative_base()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./carecloud.db")
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class SexEnum(str, enum.Enum):
    male = "Male"
    female = "Female"
    other = "Other"
    decline = "Decline to Answer"


class Patient(Base):
    __tablename__ = "patients"

    # Auto-generated fields
    patient_id    = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))
    deleted_at    = Column(DateTime, nullable=True)   # soft-delete

    # Required fields
    first_name      = Column(String(50), nullable=False)
    last_name       = Column(String(50), nullable=False)
    date_of_birth   = Column(Date, nullable=False)
    sex             = Column(Enum(SexEnum), nullable=False)
    phone_number    = Column(String(20), nullable=False)
    address_line_1  = Column(String(200), nullable=False)
    city            = Column(String(100), nullable=False)
    state           = Column(String(2), nullable=False)
    zip_code        = Column(String(10), nullable=False)

    # Optional fields
    email                   = Column(String(200), nullable=True)
    address_line_2          = Column(String(200), nullable=True)
    insurance_provider      = Column(String(200), nullable=True)
    insurance_member_id     = Column(String(100), nullable=True)
    preferred_language      = Column(String(50), nullable=True, default="English")
    emergency_contact_name  = Column(String(100), nullable=True)
    emergency_contact_phone = Column(String(20), nullable=True)

    def to_dict(self):
        return {
            "patient_id":               self.patient_id,
            "first_name":               self.first_name,
            "last_name":                self.last_name,
            "date_of_birth":            self.date_of_birth.strftime("%m/%d/%Y") if self.date_of_birth else None,
            "sex":                      self.sex.value if self.sex else None,
            "phone_number":             self.phone_number,
            "email":                    self.email,
            "address_line_1":           self.address_line_1,
            "address_line_2":           self.address_line_2,
            "city":                     self.city,
            "state":                    self.state,
            "zip_code":                 self.zip_code,
            "insurance_provider":       self.insurance_provider,
            "insurance_member_id":      self.insurance_member_id,
            "preferred_language":       self.preferred_language or "English",
            "emergency_contact_name":   self.emergency_contact_name,
            "emergency_contact_phone":  self.emergency_contact_phone,
            "created_at":               self.created_at.isoformat() if self.created_at else None,
            "updated_at":               self.updated_at.isoformat() if self.updated_at else None,
            "deleted_at":               self.deleted_at.isoformat() if self.deleted_at else None,
        }


def init_db():
    """Create all tables and seed demo patients."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Patient).count() == 0:
            seed = [
                Patient(
                    patient_id="11111111-1111-1111-1111-111111111111",
                    first_name="Jane",
                    last_name="Doe",
                    date_of_birth=datetime(1990, 5, 15).date(),
                    sex=SexEnum.female,
                    phone_number="5550001234",
                    email="jane.doe@example.com",
                    address_line_1="123 Main Street",
                    city="New York",
                    state="NY",
                    zip_code="10001",
                    preferred_language="English",
                ),
                Patient(
                    patient_id="22222222-2222-2222-2222-222222222222",
                    first_name="Carlos",
                    last_name="Rivera",
                    date_of_birth=datetime(1978, 11, 3).date(),
                    sex=SexEnum.male,
                    phone_number="5550009876",
                    address_line_1="456 Oak Avenue",
                    address_line_2="Apt 2B",
                    city="Los Angeles",
                    state="CA",
                    zip_code="90001",
                    insurance_provider="Blue Cross Blue Shield",
                    insurance_member_id="BCBS-2024-7890",
                    preferred_language="Spanish",
                ),
            ]
            db.add_all(seed)
            db.commit()
            print("[DB] Seeded 2 demo patients.")
    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
