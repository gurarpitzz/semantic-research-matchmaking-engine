from celery import Celery
import os
import json
import time
import random
import functools
from datetime import datetime
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from backend.db.database import SessionLocal, IS_STANDALONE, db_lock
from backend.models.models import Professor, Author, Paper, PaperEmbedding, paper_authors, IngestionJob
from backend.core.scraper import scraper
from backend.core.semantic_scholar import ss_client
from backend.core.nlp_core import nlp_engine
from dotenv import load_dotenv

load_dotenv()

# Celery Setup with fallback
REDIS_URL = os.getenv("REDIS_URL")
if REDIS_URL:
    celery_app = Celery("srme_tasks", broker=REDIS_URL)
else:
    # Threaded fallback for standalone (no Redis)
    from concurrent.futures import ThreadPoolExecutor
    import uuid
    
    class MockTask:
        def __init__(self):
            self.id = str(uuid.uuid4())
            
    class DummyApp:
        def __init__(self, max_workers=5):
            self.executor = ThreadPoolExecutor(max_workers=max_workers)
            
        def task(self, func):
            def delay(*args, **kwargs):
                # Submit to the persistent executor to limit concurrency
                self.executor.submit(func, *args, **kwargs)
                return MockTask()
            func.delay = delay
            return func
    
    # Increase to 5 concurrent tasks. SQLite with WAL + db_lock can handle this.
    celery_app = DummyApp(max_workers=5)

# --- Helpers ---

def retry_with_backoff(retries=4, base=0.5, jitter=0.2, allowed_exceptions=(Exception,)):
    def deco(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            attempt = 0
            while True:
                try:
                    return f(*args, **kwargs)
                except allowed_exceptions as e:
                    attempt += 1
                    if attempt > retries:
                        raise
                    sleep = base * (2 ** (attempt - 1)) + random.uniform(0, jitter)
                    time.sleep(sleep)
        return wrapped
    return deco

def _update_job_progress(db, job_id):
    """
    Atomically increment processed_faculty in the DB.
    Works across multiple worker processes/containers.
    """
    try:
        # Use SQL-level increment to avoid read-modify-write races
        stmt = (
            update(IngestionJob)
            .where(IngestionJob.id == job_id)
            .values(processed_faculty=IngestionJob.processed_faculty + 1)
            .execution_options(synchronize_session="fetch")
        )
        # Lock for SQLite concurrency safety if running in standalone mode
        if IS_STANDALONE:
            with db_lock:
                db.execute(stmt)
                db.commit()
        else:
            db.execute(stmt)
            db.commit()

        # Reload fresh job state for logs / UI
        job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        if job:
            if job.processed_faculty >= (job.total_faculty or 0):
                job.status = "completed"
                db.commit()
            print(f"📊 Job {job_id} Progress: {job.processed_faculty}/{job.total_faculty}")
    except SQLAlchemyError as exc:
        print(f"⚠️ Progress update failed (db error): {exc}")
        db.rollback()

def get_or_create_professor(db, name, university, profile_url, email=None):
    prof = db.query(Professor).filter(Professor.profile_url == profile_url).first()
    if prof:
        # update sparse fields
        updated = False
        if not prof.email and email:
            prof.email = email
            updated = True
        if updated:
            db.commit()
            db.refresh(prof)
        return prof

    # Try create (assumes unique constraint on profile_url)
    try:
        prof = Professor(
            name=name,
            university=university,
            profile_url=profile_url,
            email=email
        )
        db.add(prof)
        db.commit()
        db.refresh(prof)
        return prof
    except IntegrityError:
        db.rollback()
        # Race: created by another worker — fetch it
        return db.query(Professor).filter(Professor.profile_url == profile_url).first()

@retry_with_backoff(retries=5, base=0.6)
def _ss_search_author(name, affiliation, limit=50):
    return ss_client.get_author_papers(name, affiliation, limit=limit)

# --- Tasks ---

@celery_app.task
def ingest_university_faculty(university_name, dept_url, job_id=None):
    db = SessionLocal()
    try:
        print(f"🚀 Job {job_id}: Starting ingestion for {university_name}")
        # Update Job Status to processing
        if job_id:
            job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
            if job:
                job.status = "processing"
                db.commit()
                print(f"✅ Job {job_id}: Status set to processing")

        faculty = scraper.get_faculty_list(dept_url)
        print(f"🔍 Job {job_id}: Found {len(faculty)} faculty members")
        
        if job_id:
            job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
            if job:
                job.total_faculty = len(faculty)
                if len(faculty) == 0:
                    job.status = "failed" # Or mark as warning, but 'failed' unlocks the UI flow best
                    db.commit()
                    return f"Job {job_id}: No faculty found, URL may be incorrect or scraper blocked."
                
                job.status = "processing"
                db.commit()

        for f in faculty:
            try:
                # Deep Scrape Email if missing (already has timeout in extract_email_from_url)
                email = f.get('email')
                if not email:
                    # Optional: deep scrape lazily or here. For now keeping here to ensure high quality data.
                    # Considering moving this to a separate task if it slows loop too much.
                    # print(f"📧 Job {job_id}: Deep scraping email for {f['name']}...")
                    # email = scraper.extract_email_from_url(f['url'])
                    pass 
                
                # 1. Fetch/Create Professor safely
                prof = get_or_create_professor(db, f['name'], university_name, f['url'], email)
                
                fetch_papers_for_professor.delay(prof.id, job_id)
                time.sleep(0.1) # Slight pacing to avoid queue explosion
                
            except Exception as loop_e:
                print(f"⚠️ Job {job_id}: Skipping {f.get('name')} due to error: {loop_e}")
                # Increment progress anyway so the job can reach 'completed'
                if job_id:
                    _update_job_progress(db, job_id)
                continue
            
        return f"Successfully queued {len(faculty)} faculty from {university_name}"
    except Exception as e:
        print(f"❌ Job {job_id} Error: {e}")
        if job_id:
            job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
            if job:
                job.status = "failed"
                db.commit()
        raise e
    finally:
        db.close()

@celery_app.task
def fetch_papers_for_professor(prof_id, job_id=None):
    db = SessionLocal()
    try:
        prof = db.query(Professor).filter(Professor.id == prof_id).first()
        if not prof:
            if job_id:
                _update_job_progress(db, job_id)
            return

        # Search for author using ss_client with backoff
        try:
            author_result = _ss_search_author(prof.name, prof.university, limit=100)
        except Exception as e:
            print(f"❌ SS client failure for {prof.name}: {e}")
            if job_id:
                _update_job_progress(db, job_id)
            return

        # Expect author_result to contain (author_id, papers_list) OR just papers_list
        # Try to extract papers_list robustly:
        papers_data = None
        author_id = None
        if isinstance(author_result, dict) and 'author_id' in author_result:
            author_id = author_result['author_id']
            papers_data = author_result.get('papers', [])
        elif isinstance(author_result, list):
            papers_data = author_result
        else:
            papers_data = []

        if not papers_data:
            if job_id:
                _update_job_progress(db, job_id)
            return

        # Create Author record if needed
        author = db.query(Author).filter(Author.professor_id == prof.id).first()
        if not author:
            author = Author(name=prof.name, professor_id=prof.id, semantic_scholar_id=author_id)
            db.add(author)
            db.commit()
            db.refresh(author)
        else:
            # update SS id if discovered
            if not author.semantic_scholar_id and author_id:
                author.semantic_scholar_id = author_id
                db.commit()

        # filter & select papers (top30 by citations + recent 5 years)
        current_year = datetime.now().year
        papers_data.sort(key=lambda x: x.get('citationCount', 0) or 0, reverse=True)
        top_30 = papers_data[:30]
        recent_5 = [p for p in papers_data if p.get('year') and p['year'] >= (current_year - 5)]
        
        seen_ss = set()
        papers_to_ingest = []
        for p in (top_30 + recent_5):
            pid = p.get('paperId')
            if not pid:
                # fallback: use title+year composite key if absolutely necessary, or just skip
                key = f"{p.get('title','')}_{p.get('year','')}"
            else:
                key = pid
            if key in seen_ss:
                continue
            seen_ss.add(key)
            papers_to_ingest.append(p)

        # Now upsert papers in DB
        # We commit individually to handle race conditions (IntegrityError) gracefully per paper.
        # Batching is removed in favor of correctness.
        created = 0
        for p in papers_to_ingest:
            ss_id = p.get('paperId')
            title = p.get('title','').strip()
            year = p.get('year')
            
            existing_paper = None
            if ss_id:
                existing_paper = db.query(Paper).filter(Paper.semantic_scholar_id == ss_id).first()
            if not existing_paper:
                existing_paper = db.query(Paper).filter(Paper.title == title, Paper.year == year).first()
            
            if not existing_paper:
                try:
                    paper_obj = Paper(
                        semantic_scholar_id=ss_id,
                        title=title,
                        abstract=p.get('abstract'),
                        year=year,
                        citations=p.get('citationCount', 0) or 0,
                        paper_url=p.get('url')
                    )
                    db.add(paper_obj)
                    db.commit()
                    created += 1
                except IntegrityError:
                    db.rollback()
                    # Race condition: someone else inserted it. That's fine.
                    pass
        
        # Now ensure mapping author <-> paper exists
        for p in papers_to_ingest:
            # resolve current paper id (again safe)
            ss_id = p.get('paperId')
            title = p.get('title','').strip()
            year = p.get('year')
            paper = None
            if ss_id:
                paper = db.query(Paper).filter(Paper.semantic_scholar_id == ss_id).first()
            if not paper:
                paper = db.query(Paper).filter(Paper.title == title, Paper.year == year).first()
            if not paper:
                continue
            
            # Insert mapping if not exists
            exists = db.execute(
                paper_authors.select().where(
                    (paper_authors.c.paper_id == paper.id) &
                    (paper_authors.c.author_id == author.id)
                )
            ).first()
            if not exists:
                db.execute(paper_authors.insert().values(paper_id=paper.id, author_id=author.id))
        db.commit()

        # Kick off embeddings
        for p in papers_to_ingest:
            paper = None
            ss_id = p.get('paperId')
            title = p.get('title','').strip()
            year = p.get('year')
            if ss_id:
                paper = db.query(Paper).filter(Paper.semantic_scholar_id == ss_id).first()
            if not paper:
                paper = db.query(Paper).filter(Paper.title == title, Paper.year == year).first()
            if paper:
                generate_paper_embedding.delay(paper.id)

        if job_id:
            _update_job_progress(db, job_id)

        return f"Ingested {len(papers_to_ingest)} papers for {prof.name}"
    except Exception as e:
        print(f"❌ Worker Error for {prof_id}: {e}")
        if job_id:
            _update_job_progress(db, job_id)
        raise
    finally:
        db.close()

@celery_app.task
def generate_paper_embedding(paper_id):
    db = SessionLocal()
    try:
        paper = db.query(Paper).filter(Paper.id == paper_id).first()
        if not paper or not (paper.title or paper.abstract):
            return

        # Idempotent: skip if embedding exists
        existing_emb = db.query(PaperEmbedding).filter(PaperEmbedding.paper_id == paper_id).first()
        if existing_emb:
            return

        text = f"{paper.title}. {paper.abstract or ''}"
        vector = nlp_engine.encode(text)  # assume numpy array or list
        
        # convert to plain list of python floats for standardizing storage
        try:
            vector_list = [float(x) for x in vector.tolist()] if hasattr(vector, 'tolist') else [float(x) for x in vector]
        except Exception:
            vector_list = [float(x) for x in vector]

        # If IS_STANDALONE, we mock the Vector type with Text/JSON
        # If Postgres, pgvector handles List[float] automatically
        db_vector = json.dumps(vector_list) if IS_STANDALONE else vector_list

        embedding = PaperEmbedding(
            paper_id=paper.id,
            embedding=db_vector
        )
        db.add(embedding)
        db.commit()
    finally:
        db.close()
