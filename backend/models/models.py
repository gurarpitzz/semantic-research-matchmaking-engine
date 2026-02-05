from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime, Table, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import os
import json

# Conditional import for Vector
IS_STANDALONE = os.getenv("POSTGRES_HOST") is None or os.getenv("POSTGRES_HOST") == ""

if not IS_STANDALONE:
    from pgvector.sqlalchemy import Vector
else:
    # Polyfill or fallback for SQLite
    from sqlalchemy import Text as Vector

from backend.db.database import Base

# Many-to-Many Association Table
paper_authors = Table(
    "paper_authors",
    Base.metadata,
    Column("paper_id", Integer, ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True),
    Column("author_id", Integer, ForeignKey("authors.id", ondelete="CASCADE"), primary_key=True),
)

class Professor(Base):
    __tablename__ = "professors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    university = Column(String, nullable=False)
    department = Column(String)
    email = Column(String)
    profile_url = Column(String, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    authors = relationship("Author", back_populates="professor", cascade="all, delete-orphan")

class Author(Base):
    __tablename__ = "authors"

    id = Column(Integer, primary_key=True, index=True)
    professor_id = Column(Integer, ForeignKey("professors.id", ondelete="CASCADE"))
    name = Column(String, nullable=False)
    semantic_scholar_id = Column(String, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    professor = relationship("Professor", back_populates="authors")
    papers = relationship("Paper", secondary=paper_authors, back_populates="authors")

class Paper(Base):
    __tablename__ = "papers"

    id = Column(Integer, primary_key=True, index=True)
    semantic_scholar_id = Column(String, unique=True, index=True)
    title = Column(Text, nullable=False)
    abstract = Column(Text)
    year = Column(Integer)
    citations = Column(Integer, default=0)
    paper_url = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint('title', 'year', name='unique_paper_title_year'),)

    authors = relationship("Author", secondary=paper_authors, back_populates="papers")
    embedding = relationship("PaperEmbedding", back_populates="paper", uselist=False, cascade="all, delete-orphan")

class PaperEmbedding(Base):
    __tablename__ = "paper_embeddings"

    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(Integer, ForeignKey("papers.id", ondelete="CASCADE"), unique=True)
    embedding = Column(Vector(768))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    paper = relationship("Paper", back_populates="embedding")

class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id = Column(String, primary_key=True)
    university = Column(String)
    total_faculty = Column(Integer, default=0)
    processed_faculty = Column(Integer, default=0)
    status = Column(String, default="queued") # queued, processing, completed, failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
