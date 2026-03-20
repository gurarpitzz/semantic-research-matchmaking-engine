-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Professors Table (Academic Profiles)
CREATE TABLE IF NOT EXISTS professors (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    university TEXT NOT NULL,
    department TEXT,
    email TEXT,
    profile_url TEXT UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Authors Table (Semantic Scholar Metadata Mapping)
CREATE TABLE IF NOT EXISTS authors (
    id SERIAL PRIMARY KEY,
    professor_id INTEGER REFERENCES professors(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    semantic_scholar_id TEXT UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Papers Table
CREATE TABLE IF NOT EXISTS papers (
    id SERIAL PRIMARY KEY,
    semantic_scholar_id TEXT UNIQUE,
    title TEXT NOT NULL,
    abstract TEXT,
    year INTEGER,
    citations INTEGER DEFAULT 0,
    paper_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_paper_title_year UNIQUE(title, year)
);

-- Paper-Author Mapping (Many-to-Many)
CREATE TABLE IF NOT EXISTS paper_authors (
    paper_id INTEGER REFERENCES papers(id) ON DELETE CASCADE,
    author_id INTEGER REFERENCES authors(id) ON DELETE CASCADE,
    PRIMARY KEY (paper_id, author_id)
);

-- Embeddings Table (pgvector)
CREATE TABLE IF NOT EXISTS paper_embeddings (
    id SERIAL PRIMARY KEY,
    paper_id INTEGER REFERENCES papers(id) ON DELETE CASCADE UNIQUE,
    embedding vector(768),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast vector similarity search
CREATE INDEX ON paper_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
