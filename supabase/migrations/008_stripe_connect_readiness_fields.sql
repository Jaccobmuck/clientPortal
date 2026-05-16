ALTER TABLE organizations
  ADD COLUMN IF NOT EXISTS stripe_connect_onboarding_complete boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS stripe_connect_charges_enabled boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS stripe_connect_payouts_enabled boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS stripe_connect_details_submitted boolean NOT NULL DEFAULT false;
