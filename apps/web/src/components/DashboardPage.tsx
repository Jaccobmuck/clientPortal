import { AppShell } from "@/components/AppShell";
import { CategoryCards } from "@/components/CategoryCards";
import { InvoiceStatusMock } from "@/components/InvoiceStatusMock";
import { QuickActions } from "@/components/QuickActions";
import { RecentInvoices } from "@/components/RecentInvoices";
import { RevenueChartMock } from "@/components/RevenueChartMock";
import { StatCard } from "@/components/StatCard";
import { summaryStats } from "@/lib/mockData";

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

      <section className="stats-grid" aria-label="Invoice summary">
        {summaryStats.map((stat) => (
          <StatCard
            badge={stat.badge}
            key={stat.title}
            title={stat.title}
            trend={stat.trend}
            value={stat.value}
            tone={stat.tone}
          />
        ))}
      </section>

      <div className="dashboard-grid">
        <div className="dashboard-main">
          <InvoiceStatusMock />
          <RecentInvoices />
          <CategoryCards />
        </div>

        <aside className="dashboard-side" aria-label="Dashboard supporting widgets">
          <RevenueChartMock />
          <QuickActions />
        </aside>
      </div>
    </AppShell>
  );
}
