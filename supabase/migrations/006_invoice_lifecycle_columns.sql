-- P6 lifecycle columns for invoices
ALTER TABLE invoices ADD COLUMN sent_at    timestamptz;
ALTER TABLE invoices ADD COLUMN voided_at  timestamptz;
ALTER TABLE invoices ADD COLUMN locked     boolean NOT NULL DEFAULT false;

-- Job outbox for async queue stubs (consumed by P7 workers)
CREATE TABLE job_outbox (
  id         uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id     uuid NOT NULL REFERENCES organizations(id),
  queue_name text NOT NULL,
  payload    jsonb NOT NULL,
  status     text NOT NULL DEFAULT 'pending',
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE job_outbox ENABLE ROW LEVEL SECURITY;

CREATE POLICY "job_outbox_org_access" ON job_outbox
  FOR ALL USING (
    org_id IN (SELECT org_id FROM organization_members WHERE user_id = auth.uid())
  );

CREATE INDEX idx_job_outbox_pending
  ON job_outbox(queue_name, status)
  WHERE status = 'pending';
