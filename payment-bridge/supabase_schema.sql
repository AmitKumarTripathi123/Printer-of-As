-- Supabase Database Schema for Printer of A's Kiosk
-- Run this in your Supabase SQL Editor:
-- Dashboard -> SQL Editor -> New Query -> Paste & Run

-- 1. Jobs Table (Matches app.py with UPI payment extensions)
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    stored TEXT,
    pages INTEGER DEFAULT 1,
    copies INTEGER DEFAULT 1,
    color TEXT DEFAULT 'bw',
    duplex INTEGER DEFAULT 0,
    amount NUMERIC(6, 2) NOT NULL,
    reserved_paise_offset INT DEFAULT 0,          -- 1 to 99 paise for collision-free payment
    utr_number TEXT UNIQUE,                       -- 12-digit UPI reference number
    status TEXT DEFAULT 'pending_payment' CHECK (status IN ('pending_payment', 'queued', 'printing', 'done', 'failed', 'refund_due')),
    created TEXT,
    expires_at TIMESTAMPTZ,
    notes TEXT DEFAULT '',
    reprint_voucher TEXT UNIQUE                   -- 6-character recovery token if print fails
);

-- 2. Incoming Payments Table (Captured by Phone Bridge)
CREATE TABLE IF NOT EXISTS incoming_payments (
    id BIGSERIAL PRIMARY KEY,
    utr_number TEXT UNIQUE,                       -- Unique 12-digit UTR prevents double-spending
    amount NUMERIC(6, 2) NOT NULL,
    sender_info TEXT,                             -- UPI ID / Name / Mobile if present in SMS
    raw_message TEXT NOT NULL,                    -- Full original SMS for debugging & audit
    matched_job_id TEXT REFERENCES jobs(id),
    is_consumed BOOLEAN DEFAULT FALSE,            -- True once matched to a print job
    received_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Kiosks Master Table
CREATE TABLE IF NOT EXISTS kiosks (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT DEFAULT 'ONLINE' CHECK (status IN ('ONLINE', 'OFFLINE', 'OUT_OF_PAPER', 'JAMMED', 'MAINTENANCE')),
    printer_model TEXT,
    ip_address TEXT,
    toner_level INT DEFAULT 100,
    paper_status TEXT DEFAULT 'OK',
    last_heartbeat TIMESTAMPTZ DEFAULT NOW(),
    price_per_page_single NUMERIC(5, 2) DEFAULT 2.00,
    price_per_page_double NUMERIC(5, 2) DEFAULT 3.00,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Kiosk Telemetry & Audit Log
CREATE TABLE IF NOT EXISTS kiosk_events (
    id BIGSERIAL PRIMARY KEY,
    kiosk_id TEXT REFERENCES kiosks(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,                     -- HEARTBEAT, PAPER_EMPTY, JAM, ERROR, RECOVERY
    details JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable Row Level Security (RLS)
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE incoming_payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE kiosks ENABLE ROW LEVEL SECURITY;
ALTER TABLE kiosk_events ENABLE ROW LEVEL SECURITY;

-- Allow public read & insert for jobs
CREATE POLICY "Public read jobs" ON jobs FOR SELECT USING (true);
CREATE POLICY "Public insert jobs" ON jobs FOR INSERT WITH CHECK (true);
CREATE POLICY "Public update jobs" ON jobs FOR UPDATE USING (true);
CREATE POLICY "Public read kiosks" ON kiosks FOR SELECT USING (true);

-- Insert Default Kiosk
INSERT INTO kiosks (id, name, status, price_per_page_single, price_per_page_double)
VALUES ('KIOSK_01', 'Main Entrance Laser Kiosk', 'ONLINE', 2.00, 3.00)
ON CONFLICT (id) DO NOTHING;
