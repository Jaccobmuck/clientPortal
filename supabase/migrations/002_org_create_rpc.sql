-- ── Atomic org creation RPC ───────────────────────────────────────────────────
-- Creates an organization and the owner's membership row in a single
-- transaction. An organization without its owner-membership row must never
-- persist, so both inserts share one atomic unit.
--
-- Also bootstraps the public.users row (FK target for organizations.owner_id)
-- on first use. This is an integrity fail-safe, not a profile-management
-- feature: profile editing belongs to a later phase.

CREATE OR REPLACE FUNCTION create_organization(
  p_user_id    uuid,
  p_user_email text,
  p_name       text,
  p_slug       text
) RETURNS organizations
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_org organizations;
BEGIN
  INSERT INTO users (id, email)
  VALUES (p_user_id, p_user_email)
  ON CONFLICT (id) DO NOTHING;

  BEGIN
    INSERT INTO organizations (name, slug, owner_id)
    VALUES (p_name, p_slug, p_user_id)
    RETURNING * INTO v_org;
  EXCEPTION WHEN unique_violation THEN
    RAISE EXCEPTION 'slug_taken' USING ERRCODE = '23505';
  END;

  INSERT INTO organization_members (org_id, user_id, role)
  VALUES (v_org.id, p_user_id, 'owner');

  RETURN v_org;
END;
$$;

REVOKE ALL ON FUNCTION create_organization(uuid, text, text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION create_organization(uuid, text, text, text)
  TO authenticated, service_role;
