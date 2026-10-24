from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from .database import Base


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), default="candidate", nullable=False)  # candidate | admin
    is_active = Column(Boolean, default=True)
    target_role = Column(String(120), default="")
    experience = Column(String(60), default="")
    industry = Column(String(120), default="")
    language = Column(String(40), default="English")
    created_at = Column(DateTime, default=utcnow)
    last_login = Column(DateTime, nullable=True)
    reset_token = Column(String(120), nullable=True)
    reset_expires = Column(DateTime, nullable=True)


class Dataset(Base):
    __tablename__ = "datasets"
    id = Column(Integer, primary_key=True)
    filename = Column(String(255))
    status = Column(String(20), default="pending")  # pending|processing|completed|failed
    total_rows = Column(Integer, default=0)
    processed = Column(Integer, default=0)
    imported = Column(Integer, default=0)
    duplicates = Column(Integer, default=0)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    finished_at = Column(DateTime, nullable=True)


class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True)
    question = Column(Text, nullable=False)
    norm = Column(String(1000), unique=True, index=True)  # hash of text + role + experience + difficulty + category (detects duplicate records)
    category = Column(String(120), index=True, default="")
    role = Column(String(120), index=True, default="")
    experience = Column(String(60), index=True, default="")
    difficulty = Column(String(30), index=True, default="")
    source_type = Column(String(60), index=True, default="")
    ideal_answer = Column(Text, default="")
    vec_idx = Column(Integer, default=-1)  # position of this question's vector in the FAISS index
    dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=utcnow)
    keywords = relationship("Keyword", cascade="all, delete-orphan", lazy="selectin")


class Keyword(Base):
    __tablename__ = "keywords"
    id = Column(Integer, primary_key=True)
    question_id = Column(Integer, ForeignKey("questions.id"), index=True)
    keyword = Column(String(120))


class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), unique=True)


class JobRole(Base):
    __tablename__ = "job_roles"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), unique=True)


class Interview(Base):
    __tablename__ = "interviews"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    started_at = Column(DateTime, default=utcnow, index=True)
    finished_at = Column(DateTime, nullable=True)
    duration = Column(Integer, default=0)  # seconds
    role = Column(String(120))
    experience = Column(String(60))
    difficulty = Column(String(30))
    categories = Column(JSON, default=list)
    num_questions = Column(Integer, default=5)
    finished = Column(Boolean, default=False)
    items = relationship("InterviewQuestion", cascade="all, delete-orphan", order_by="InterviewQuestion.id")


class InterviewQuestion(Base):
    __tablename__ = "interview_questions"
    id = Column(Integer, primary_key=True)
    interview_id = Column(Integer, ForeignKey("interviews.id"), index=True)
    question_id = Column(Integer, nullable=True)
    question_text = Column(Text, default="")  # snapshot, so history survives question edits/deletes
    user_answer = Column(Text, nullable=True)
    is_skipped = Column(Boolean, default=False)
    viewed_ideal_answer = Column(Boolean, default=False)
