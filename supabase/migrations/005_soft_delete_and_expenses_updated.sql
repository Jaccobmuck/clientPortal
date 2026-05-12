ALTER TABLE clients  ADD COLUMN deleted_at timestamptz;
ALTER TABLE projects ADD COLUMN deleted_at timestamptz;
ALTER TABLE expenses ADD COLUMN deleted_at timestamptz;
ALTER TABLE expenses ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now();

CREATE TRIGGER set_expenses_updated_at
  BEFORE UPDATE ON expenses FOR EACH ROW EXECUTE FUNCTION set_updated_at();
