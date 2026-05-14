-- ── Org role CHECK constraint ─────────────────────────────────────────────────
-- Pin organization_members.role to the three roles the application understands.
-- The Python OrgRole enum is the in-process source of truth; this constraint
-- guarantees the database can never disagree with it.

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'org_role_check'
      AND conrelid = to_regclass('public.organization_members')
  ) THEN
    ALTER TABLE organization_members
      ADD CONSTRAINT org_role_check
      CHECK (role IN ('owner', 'admin', 'member'));
  END IF;
END;
$$;
