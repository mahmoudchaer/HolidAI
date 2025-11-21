-- Create users table
CREATE TABLE IF NOT EXISTS users (
    email TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP
);

-- Create index on email for faster lookups (though it's already primary key)
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Create chats table
CREATE TABLE IF NOT EXISTS chats (
    email TEXT NOT NULL,
    session_id TEXT NOT NULL,
    title TEXT NOT NULL,
    messages JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (email, session_id)
);

-- Create indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_chats_email ON chats(email);
CREATE INDEX IF NOT EXISTS idx_chats_session_id ON chats(session_id);
CREATE INDEX IF NOT EXISTS idx_chats_updated_at ON chats(updated_at DESC);

