-- P6 lifecycle columns for invoices
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS sent_at    timestamptz;
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS voided_at  timestamptz;
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS locked     boolean NOT NULL DEFAULT false;

-- Job outbox for async queue stubs (consumed by P7 workers)
CREATE TABLE IF NOT EXISTS job_outbox (
  id         uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id     uuid NOT NULL REFERENCES organizations(id),
  queue_name text NOT NULL,
  payload    jsonb NOT NULL,
  status     text NOT NULL DEFAULT 'pending',
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE job_outbox ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "job_outbox_org_access" ON job_outbox;
CREATE POLICY "job_outbox_org_access" ON job_outbox
  FOR ALL USING (
    org_id IN (SELECT org_id FROM organization_members WHERE user_id = auth.uid())
  );

CREATE INDEX IF NOT EXISTS idx_job_outbox_pending
  ON job_outbox(queue_name, status)
  WHERE status = 'pending';
