-- ── Members-feature DB prerequisites ──────────────────────────────────────────
-- Two changes ship together because both are required before the org members
-- router can land:
--   1. auth.users → public.users sync, so invite-by-email can find users.
--   2. organization_members.joined_at column, surfaced in MemberResponse.
--
-- Without the trigger, public.users is empty until a user happens to create
-- an org (the create_organization RPC bootstraps it as a side effect), so a
-- newly-registered user is invisible to invitations until they create their
-- own org. The backfill covers users who registered before the trigger.

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
  INSERT INTO public.users (id, email, full_name)
  VALUES (
    NEW.id,
    NEW.email,
    COALESCE(NEW.raw_user_meta_data->>'full_name', '')
  )
  ON CONFLICT (id) DO NOTHING;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ── joined_at column on organization_members ─────────────────────────────────
ALTER TABLE organization_members
  ADD COLUMN IF NOT EXISTS joined_at timestamptz NOT NULL DEFAULT now();

-- Backfill any auth.users rows that pre-date the trigger.
INSERT INTO public.users (id, email, full_name)
SELECT
  au.id,
  au.email,
  COALESCE(au.raw_user_meta_data->>'full_name', '')
FROM auth.users au
LEFT JOIN public.users pu ON pu.id = au.id
WHERE pu.id IS NULL AND au.email IS NOT NULL
ON CONFLICT (id) DO NOTHING;
