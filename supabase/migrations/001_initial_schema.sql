-- ── Extensions ────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ── updated_at trigger function ────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ── Tables ────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS users (
  id          uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email       text NOT NULL UNIQUE,
  full_name   text,
  avatar_url  text,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS organizations (
  id          uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  name        text NOT NULL,
  slug        text NOT NULL UNIQUE,
  owner_id    uuid NOT NULL REFERENCES users(id),
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS organization_members (
  org_id   uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id  uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role     text NOT NULL DEFAULT 'member',
  PRIMARY KEY (org_id, user_id)
);

CREATE TABLE IF NOT EXISTS clients (
  id          uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  name        text NOT NULL,
  email       text NOT NULL,
  phone       text,
  company     text,
  notes       text,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS projects (
  id           uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id       uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  client_id    uuid NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  name         text NOT NULL,
  description  text,
  status       text NOT NULL DEFAULT 'active',
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS invoices (
  id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id          uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  client_id       uuid NOT NULL REFERENCES clients(id),
  project_id      uuid REFERENCES projects(id),
  invoice_number  text NOT NULL,
  status          text NOT NULL DEFAULT 'draft',
  pay_token       uuid NOT NULL DEFAULT uuid_generate_v4() UNIQUE,
  due_date        date,
  issued_at       timestamptz,
  paid_at         timestamptz,
  subtotal        numeric(12,2) NOT NULL DEFAULT 0,
  tax_rate        numeric(5,4) NOT NULL DEFAULT 0,
  tax_amount      numeric(12,2) NOT NULL DEFAULT 0,
  total           numeric(12,2) NOT NULL DEFAULT 0,
  notes           text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, invoice_number)
);

CREATE TABLE IF NOT EXISTS invoice_line_items (
  id           uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  invoice_id   uuid NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
  description  text NOT NULL,
  quantity     numeric(10,2) NOT NULL DEFAULT 1,
  unit_price   numeric(12,2) NOT NULL,
  amount       numeric(12,2) NOT NULL,
  sort_order   int NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS payments (
  id                        uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  invoice_id                uuid NOT NULL REFERENCES invoices(id),
  org_id                    uuid NOT NULL REFERENCES organizations(id),
  amount                    numeric(12,2) NOT NULL,
  stripe_payment_intent_id  text UNIQUE,
  stripe_charge_id          text,
  status                    text NOT NULL DEFAULT 'pending',
  paid_at                   timestamptz,
  created_at                timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS disputes (
  id           uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  invoice_id   uuid NOT NULL REFERENCES invoices(id),
  org_id       uuid NOT NULL REFERENCES organizations(id),
  reason       text NOT NULL,
  status       text NOT NULL DEFAULT 'open',
  resolved_at  timestamptz,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS expenses (
  id           uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id       uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  project_id   uuid REFERENCES projects(id),
  description  text NOT NULL,
  amount       numeric(12,2) NOT NULL,
  category     text,
  receipt_url  text,
  incurred_at  date NOT NULL,
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS reminder_schedule (
  id          uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  invoice_id  uuid NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
  org_id      uuid NOT NULL REFERENCES organizations(id),
  send_at     timestamptz NOT NULL,
  sent_at     timestamptz,
  status      text NOT NULL DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS notification_log (
  id          uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id      uuid NOT NULL REFERENCES organizations(id),
  invoice_id  uuid REFERENCES invoices(id),
  type        text NOT NULL,
  payload     jsonb,
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- ── RLS ───────────────────────────────────────────────────────────────────────

ALTER TABLE users               ENABLE ROW LEVEL SECURITY;
ALTER TABLE organizations       ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE clients             ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects            ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices            ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoice_line_items  ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments            ENABLE ROW LEVEL SECURITY;
ALTER TABLE disputes            ENABLE ROW LEVEL SECURITY;
ALTER TABLE expenses            ENABLE ROW LEVEL SECURITY;
ALTER TABLE reminder_schedule   ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification_log    ENABLE ROW LEVEL SECURITY;

-- ── Policies ──────────────────────────────────────────────────────────────────

DROP POLICY IF EXISTS "users_self_access" ON users;
CREATE POLICY "users_self_access" ON users
  FOR ALL USING (id = auth.uid());

DROP POLICY IF EXISTS "org_members_access" ON organization_members;
CREATE POLICY "org_members_access" ON organization_members
  FOR ALL USING (user_id = auth.uid());

-- All remaining tables share the same org-membership pattern
DROP POLICY IF EXISTS "organizations_org_access" ON organizations;
CREATE POLICY "organizations_org_access" ON organizations
  FOR ALL USING (id IN (SELECT org_id FROM organization_members WHERE user_id = auth.uid()));

DROP POLICY IF EXISTS "clients_org_access" ON clients;
CREATE POLICY "clients_org_access" ON clients
  FOR ALL USING (org_id IN (SELECT org_id FROM organization_members WHERE user_id = auth.uid()));

DROP POLICY IF EXISTS "projects_org_access" ON projects;
CREATE POLICY "projects_org_access" ON projects
  FOR ALL USING (org_id IN (SELECT org_id FROM organization_members WHERE user_id = auth.uid()));

DROP POLICY IF EXISTS "invoices_org_access" ON invoices;
CREATE POLICY "invoices_org_access" ON invoices
  FOR ALL USING (org_id IN (SELECT org_id FROM organization_members WHERE user_id = auth.uid()));

DROP POLICY IF EXISTS "invoice_line_items_org_access" ON invoice_line_items;
CREATE POLICY "invoice_line_items_org_access" ON invoice_line_items
  FOR ALL USING (
    invoice_id IN (
      SELECT id FROM invoices
      WHERE org_id IN (SELECT org_id FROM organization_members WHERE user_id = auth.uid())
    )
  );

DROP POLICY IF EXISTS "payments_org_access" ON payments;
CREATE POLICY "payments_org_access" ON payments
  FOR ALL USING (org_id IN (SELECT org_id FROM organization_members WHERE user_id = auth.uid()));

DROP POLICY IF EXISTS "disputes_org_access" ON disputes;
CREATE POLICY "disputes_org_access" ON disputes
  FOR ALL USING (org_id IN (SELECT org_id FROM organization_members WHERE user_id = auth.uid()));

DROP POLICY IF EXISTS "expenses_org_access" ON expenses;
CREATE POLICY "expenses_org_access" ON expenses
  FOR ALL USING (org_id IN (SELECT org_id FROM organization_members WHERE user_id = auth.uid()));

DROP POLICY IF EXISTS "reminder_schedule_org_access" ON reminder_schedule;
CREATE POLICY "reminder_schedule_org_access" ON reminder_schedule
  FOR ALL USING (org_id IN (SELECT org_id FROM organization_members WHERE user_id = auth.uid()));

DROP POLICY IF EXISTS "notification_log_org_access" ON notification_log;
CREATE POLICY "notification_log_org_access" ON notification_log
  FOR ALL USING (org_id IN (SELECT org_id FROM organization_members WHERE user_id = auth.uid()));

-- ── Triggers ──────────────────────────────────────────────────────────────────

DROP TRIGGER IF EXISTS set_users_updated_at ON users;
CREATE TRIGGER set_users_updated_at
  BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS set_organizations_updated_at ON organizations;
CREATE TRIGGER set_organizations_updated_at
  BEFORE UPDATE ON organizations FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS set_clients_updated_at ON clients;
CREATE TRIGGER set_clients_updated_at
  BEFORE UPDATE ON clients FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS set_projects_updated_at ON projects;
CREATE TRIGGER set_projects_updated_at
  BEFORE UPDATE ON projects FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS set_invoices_updated_at ON invoices;
CREATE TRIGGER set_invoices_updated_at
  BEFORE UPDATE ON invoices FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS set_disputes_updated_at ON disputes;
CREATE TRIGGER set_disputes_updated_at
  BEFORE UPDATE ON disputes FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ── Indexes ───────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_invoices_org_id ON invoices(org_id);
CREATE INDEX IF NOT EXISTS idx_invoices_client_id ON invoices(client_id);
CREATE INDEX IF NOT EXISTS idx_invoices_pay_token ON invoices(pay_token);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);
CREATE INDEX IF NOT EXISTS idx_clients_org_id ON clients(org_id);
CREATE INDEX IF NOT EXISTS idx_projects_org_id ON projects(org_id);
CREATE INDEX IF NOT EXISTS idx_payments_invoice_id ON payments(invoice_id);
CREATE INDEX IF NOT EXISTS idx_payments_stripe_payment_intent_id ON payments(stripe_payment_intent_id);
CREATE INDEX IF NOT EXISTS idx_reminder_schedule_send_at ON reminder_schedule(send_at) WHERE status = 'pending';
