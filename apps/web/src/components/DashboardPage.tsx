import { AppShell } from "@/components/AppShell";

export function DashboardPage() {
  return (
    <AppShell>
      <section className="dashboard-header">
        <div>
          <p className="eyebrow">May 2026</p>
          <h1>Dashboard</h1>
          <p>Here&apos;s what&apos;s happening with your invoices this month.</p>
        </div>
        <div className="dashboard-header__actions">
          <button className="ghost-button" type="button">
            May 2026
          </button>
          <button className="primary-button" type="button">
            Create invoice
          </button>
        </div>
      </section>

      <section className="dashboard-empty card" aria-label="Dashboard preview">
        <p className="eyebrow">Workspace shell</p>
        <h2>Invoice and payment widgets are ready to drop in.</h2>
        <p>
          The navigation, dashboard frame, and responsive app surface are in
          place for the mock data cards.
        </p>
      </section>
    </AppShell>
  );
}
