import { quickActions } from "@/lib/mockData";

export function QuickActions() {
  return (
    <section className="quick-card card" aria-labelledby="actions-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Shortcuts</p>
          <h2 id="actions-title">Quick actions</h2>
        </div>
      </div>

      <div className="quick-actions">
        {quickActions.map((action) => (
          <button className="quick-action" type="button" key={action}>
            <span>{action.slice(0, 2)}</span>
            {action}
          </button>
        ))}
      </div>
    </section>
  );
}
