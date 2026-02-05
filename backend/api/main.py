from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text, func
import numpy as np
from backend.db.database import get_db, IS_STANDALONE, engine, SessionLocal
from backend.models.models import Base, IngestionJob, Professor, Paper, Author
from backend.core.nlp_core import nlp_engine
from backend.workers.tasks import ingest_university_faculty
from pydantic import BaseModel
from typing import List, Optional
import os
import json
from openpyxl import Workbook
from io import BytesIO

# Initialize database on startup (especially for SQLite)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="SRME API")

# Serve static files from frontend/static
# This assumes the directory exists at the same level as backend
frontend_path = os.path.join(os.getcwd(), "frontend", "static")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

    @app.get("/")
    async def read_index():
        return FileResponse(os.path.join(frontend_path, "index.html"))

    @app.get("/style.css")
    async def get_css():
        return FileResponse(os.path.join(frontend_path, "style.css"))

    @app.get("/app.js")
    async def get_js():
        return FileResponse(os.path.join(frontend_path, "app.js"))

class MatchRequest(BaseModel):
    profile_text: str
    limit: int = 50  # Get more papers initially to group
    min_score: float = 0.4

class IngestRequest(BaseModel):
    university: str
    dept_url: str

@app.post("/match")
def get_matches(request: MatchRequest, db: Session = Depends(get_db)):
    # 1. Embed user profile
    vector = nlp_engine.encode(request.profile_text)
    
    if IS_STANDALONE:
        # 2a. Standalone (SQLite) matching logic
        # We need to manually compute similarity since SQLite has no pgvector
        query = text("""
            SELECT 
                p.id as paper_id, p.title, p.year, p.paper_url,
                prof.name as prof_name, prof.university, prof.email, e.embedding
            FROM paper_embeddings e
            JOIN papers p ON e.paper_id = p.id
            JOIN paper_authors pa ON p.id = pa.paper_id
            JOIN authors a ON pa.author_id = a.id
            JOIN professors prof ON a.professor_id = prof.id
        """)
        rows = db.execute(query).fetchall()
        
        matches_flat = []
        vec_a = np.array(vector)
        for row in rows:
            # Parse vector from JSON string
            vec_b = np.array(json.loads(row.embedding))
            # Cosine similarity
            similarity = np.dot(vec_a, vec_b) / (np.linalg.norm(vec_a) * np.linalg.norm(vec_b))
            
            if similarity >= request.min_score:
                matches_flat.append({
                    "prof_id": row.prof_name + row.university, # Simple key
                    "prof_name": row.prof_name,
                    "university": row.university,
                    "email": row.email,
                    "title": row.title,
                    "year": row.year,
                    "score": float(similarity),
                    "url": row.paper_url
                })
        
        # Sort and Group (mimicking the Postgres query)
        matches_flat.sort(key=lambda x: x['score'], reverse=True)
        
        grouped = {}
        for m in matches_flat[:request.limit]:
            key = m['prof_id']
            if key not in grouped:
                grouped[key] = {
                    "professor": m['prof_name'],
                    "university": m['university'],
                    "email": m['email'],
                    "max_score": m['score'],
                    "papers": []
                }
            if len(grouped[key]['papers']) < 3:
                grouped[key]['papers'].append({
                    "title": m['title'],
                    "year": m['year'],
                    "score": m['score'],
                    "url": m['url']
                })
        
        return list(grouped.values())
    else:
        # 2b. Production (Postgres + pgvector) matching logic
        query = text("""
            WITH ranked_papers AS (
                SELECT 
                    p.id as paper_id, 
                    p.title, 
                    p.year, 
                    p.citations,
                    p.paper_url,
                    prof.id as prof_id,
                    prof.name as prof_name,
                    prof.university,
                    (1 - (e.embedding <=> :vec)) as similarity
                FROM paper_embeddings e
                JOIN papers p ON e.paper_id = p.id
                JOIN paper_authors pa ON p.id = pa.paper_id
                JOIN authors a ON pa.author_id = a.id
                JOIN professors prof ON a.professor_id = prof.id
                WHERE (1 - (e.embedding <=> :vec)) >= :min_score
                ORDER BY similarity DESC
                LIMIT :limit
            )
            SELECT 
                prof_id, 
                prof_name, 
                university,
                MAX(similarity) as max_score,
                JSON_AGG(JSON_BUILD_OBJECT(
                    'title', title, 
                    'year', year, 
                    'score', similarity,
                    'url', paper_url
                )) as top_papers
            FROM ranked_papers
            GROUP BY prof_id, prof_name, university
            ORDER BY max_score DESC
        """)
        
        results = db.execute(query, {
            "vec": str(vector), 
            "limit": request.limit,
            "min_score": request.min_score
        }).fetchall()
        
        matches = []
        for row in results:
            matches.append({
                "professor": row.prof_name,
                "university": row.university,
                "max_score": round(float(row.max_score), 4),
                "papers": row.top_papers[:3]
            })
            
        return matches

@app.post("/ingest")
def start_ingest(request: IngestRequest, db: Session = Depends(get_db)):
    import uuid
    job_id = str(uuid.uuid4())
    
    # Create Job Record
    job = IngestionJob(
        id=job_id,
        university=request.university,
        status="queued"
    )
    db.add(job)
    db.commit()

    ingest_university_faculty.delay(request.university, request.dept_url, job_id=job_id)
    return {"task_id": job_id, "status": "Queued"}

@app.get("/job/{job_id}")
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "id": job.id,
        "university": job.university,
        "status": job.status,
        "total_faculty": job.total_faculty,
        "processed_faculty": job.processed_faculty,
        "progress": (job.processed_faculty / job.total_faculty) if job.total_faculty > 0 else 0
    }

@app.get("/export/professors.xlsx")
def export_professors(db: Session = Depends(get_db)):
    # Query professors with unique paper count
    # Note: paper_authors link table is used to join Professor -> Author -> Paper
    results = (
        db.query(
            Professor.name,
            Professor.email,
            Professor.profile_url,
            Professor.university,
            Professor.department,
            func.count(func.distinct(Paper.id)).label("paper_count")
        )
        .outerjoin(Author, Author.professor_id == Professor.id)
        .outerjoin(Author.papers) # Uses relationship to Paper
        .group_by(Professor.id)
        .all()
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "SRME Professors"

    # Header
    ws.append([
        "Name",
        "Email",
        "Profile URL",
        "University",
        "Department",
        "Papers Indexed"
    ])

    for row in results:
        ws.append(list(row))

    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)

    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=professors.xlsx"
        }
    )

@app.get("/health")
def health():
    return {"status": "ok"}
