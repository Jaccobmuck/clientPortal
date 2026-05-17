ALTER TABLE users
  ADD COLUMN IF NOT EXISTS stripe_customer_id text,
  ADD COLUMN IF NOT EXISTS stripe_subscription_id text,
  ADD COLUMN IF NOT EXISTS billing_status text NOT NULL DEFAULT 'free',
  ADD COLUMN IF NOT EXISTS billing_price_id text,
  ADD COLUMN IF NOT EXISTS billing_current_period_end timestamptz;

ALTER TABLE organizations
  ADD COLUMN IF NOT EXISTS stripe_subscription_item_id text,
  ADD COLUMN IF NOT EXISTS is_free_org boolean NOT NULL DEFAULT false;

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_stripe_customer_id
  ON users(stripe_customer_id)
  WHERE stripe_customer_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_stripe_subscription_id
  ON users(stripe_subscription_id)
  WHERE stripe_subscription_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_organizations_owner_created_at
  ON organizations(owner_id, created_at);

WITH ranked_orgs AS (
  SELECT
    id,
    row_number() OVER (PARTITION BY owner_id ORDER BY created_at, id) = 1 AS is_first_org
  FROM organizations
)
UPDATE organizations
SET is_free_org = ranked_orgs.is_first_org
FROM ranked_orgs
WHERE organizations.id = ranked_orgs.id;
