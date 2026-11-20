-- treeWISE Sprint 5: apply manually to a dedicated, private PostgreSQL database.
-- Use an app role with SELECT/INSERT/UPDATE and a separate migration role.
BEGIN;
CREATE TABLE IF NOT EXISTS treewise_staff (
  id uuid PRIMARY KEY,
  username text NOT NULL UNIQUE,
  display_name text NOT NULL,
  password_hash text NOT NULL,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (length(username) BETWEEN 3 AND 80)
);
CREATE TABLE IF NOT EXISTS treewise_sessions (
  token_hash text PRIMARY KEY,
  staff_id uuid NOT NULL REFERENCES treewise_staff(id) ON DELETE CASCADE,
  expires_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS treewise_sessions_expiry_idx ON treewise_sessions(expires_at);
CREATE TABLE IF NOT EXISTS treewise_inquiries (
  id uuid PRIMARY KEY,
  created_at timestamptz NOT NULL DEFAULT now(),
  name text NOT NULL,
  email text NOT NULL DEFAULT '',
  phone text NOT NULL DEFAULT '',
  location text NOT NULL DEFAULT '',
  description text NOT NULL,
  urgency text NOT NULL DEFAULT 'routine' CHECK (urgency IN ('routine','soon','urgent')),
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','reviewing','contacted','resolved','closed')),
  consent_at timestamptz NOT NULL,
  CHECK (email <> '' OR phone <> '')
);
CREATE INDEX IF NOT EXISTS treewise_inquiries_recent_idx ON treewise_inquiries(created_at DESC);
CREATE TABLE IF NOT EXISTS treewise_inquiry_events (
  id bigserial PRIMARY KEY,
  inquiry_id uuid NOT NULL REFERENCES treewise_inquiries(id) ON DELETE CASCADE,
  staff_id uuid NOT NULL REFERENCES treewise_staff(id),
  status text NOT NULL CHECK (status IN ('pending','reviewing','contacted','resolved','closed')),
  note text NOT NULL DEFAULT '',
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS treewise_inquiry_events_ref_idx ON treewise_inquiry_events(inquiry_id, created_at DESC);
COMMIT;
