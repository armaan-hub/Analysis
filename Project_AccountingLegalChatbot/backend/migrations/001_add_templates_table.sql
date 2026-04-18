-- Migration: Add templates table
-- Note: SQLAlchemy auto-creates this via Base.metadata.create_all
-- This SQL is provided as a reference and for manual migration if needed

CREATE TABLE IF NOT EXISTS templates (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    name TEXT NOT NULL,
    config_json TEXT NOT NULL,
    embedding JSON,
    status TEXT DEFAULT 'draft',
    verification_report TEXT,
    page_count INTEGER,
    source_pdf_name TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_global BOOLEAN DEFAULT 0,
    confidence_score REAL DEFAULT 0.0,
    UNIQUE(user_id, name)
);

CREATE INDEX IF NOT EXISTS idx_templates_user_id ON templates(user_id);
CREATE INDEX IF NOT EXISTS idx_templates_status ON templates(status);
