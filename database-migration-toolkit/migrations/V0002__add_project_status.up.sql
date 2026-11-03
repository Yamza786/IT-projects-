ALTER TABLE projects ADD COLUMN status TEXT NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'paused', 'archived'));
