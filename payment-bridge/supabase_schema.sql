-- Supabase Database Schema for Autonomous Printing Kiosk
-- Run this in the Supabase SQL Editor (Dashboard -> SQL Editor -> New Query)

-- 1. Kiosks Master Table
CREATE TABLE IF NOT EXISTS kiosks (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT DEFAULT 'OFFLINE' CHECK (status IN ('ONLINE', 'OFFLINE', 'OUT_OF_PAPER', 'JAMMED', 'MAINTENANCE')),
    printer_model TEXT,
    ip_address TEXT,
    toner_level INT DEFAULT 100,
    paper_status TEXT DEFAULT 'OK',
    last_heartbeat TIMESTAMPTZ,
    price_per_page_single NUMERIC(5, 2) DEFAULT 2.00,
    price_per_page_double NUMERIC(5, 2) DEFAULT 3.00,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Print Jobs Table
CREATE TABLE IF NOT EXISTS print_jobs (
    id TEXT PRIMARY KEY,
    kiosk_id TEXT REFERENCES kiosks(id) ON DELETE CASCADE,
    file_name TEXT,
    file_url TEXT,
    page_count INT NOT NULL,
    copies INT DEFAULT 1,
    is_duplex BOOLEAN DEFAULT FALSE,
    base_amount NUMERIC(6, 2) NOT NULL,
    reserved_paise_offset INT NOT NULL DEFAULT 0, -- 1 to 99 paise for collision-free matching
    final_amount NUMERIC(6, 2) NOT NULL,          -- base_amount + (reserved_paise_offset / 100)
    utr_number TEXT UNIQUE,                       -- 12-digit UPI reference number
    payment_status TEXT DEFAULT 'PENDING' CHECK (payment_status IN ('PENDING', 'PAID', 'EXPIRED', 'UNDERPAID', 'OVERPAID', 'REFUND_DUE')),
    print_status TEXT DEFAULT 'QUEUED' CHECK (print_status IN ('QUEUED', 'PROCESSING', 'COMPLETED', 'FAILED')),
    pages_actually_printed INT DEFAULT 0,
    reprint_voucher TEXT UNIQUE,                  -- 6-character recovery token if print fails
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

-- 3. Incoming Payments Table (Captured by Phone Bridge)
CREATE TABLE IF NOT EXISTS incoming_payments (
    id BIGSERIAL PRIMARY KEY,
    utr_number TEXT UNIQUE,                       -- Unique 12-digit UTR prevents double-spending
    amount NUMERIC(6, 2) NOT NULL,
    sender_info TEXT,                             -- UPI ID / Name / Mobile if present in SMS
    raw_message TEXT NOT NULL,                    -- Full original SMS for debugging & audit
    matched_job_id TEXT REFERENCES print_jobs(id),
    is_consumed BOOLEAN DEFAULT FALSE,            -- True once matched to a print job
    received_at TIMESTAMPTZ DEFAULT NOW()
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
ALTER TABLE kiosks ENABLE ROW LEVEL SECURITY;
ALTER TABLE print_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE incoming_payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE kiosk_events ENABLE ROW LEVEL SECURITY;

-- Allow read access for public/anon users on kiosks and print_jobs (for the web app)
CREATE POLICY "Public read kiosks" ON kiosks FOR SELECT USING (true);
CREATE POLICY "Public read print_jobs" ON print_jobs FOR SELECT USING (true);

-- Insert a default demo kiosk
INSERT INTO kiosks (id, name, status, price_per_page_single, price_per_page_double)
VALUES ('KIOSK_01', 'Main Entrance Laser Kiosk', 'ONLINE', 2.00, 3.00)
ON CONFLICT (id) DO NOTHING;
