ALTER TABLE organizations ADD COLUMN IF NOT EXISTS logo_url text;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS brand_color text;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS support_email text;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS stripe_connected_account_id text;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS stripe_payments_enabled boolean NOT NULL DEFAULT false;

ALTER TABLE invoices ADD COLUMN IF NOT EXISTS currency text NOT NULL DEFAULT 'usd';
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS discount_amount numeric(12,2) NOT NULL DEFAULT 0;
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS pdf_storage_path text;
