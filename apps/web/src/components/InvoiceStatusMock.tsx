import { invoiceStatus } from "@/lib/mockData";

export function InvoiceStatusMock() {
  return (
    <section className="status-card card" aria-labelledby="status-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Invoice flow</p>
          <h2 id="status-title">Invoice status</h2>
        </div>
        <span className="section-pill">182 total</span>
      </div>

      <div className="status-grid">
        {invoiceStatus.map((status) => (
          <article className={`status-step status-step--${status.tone}`} key={status.label}>
            <div>
              <span>{status.label}</span>
              <strong>{status.count}</strong>
            </div>
            <span className="status-step__track">
              <span
                className="status-step__bar"
                style={{ width: `${status.progress}%` }}
              />
            </span>
          </article>
        ))}
      </div>
    </section>
  );
}
