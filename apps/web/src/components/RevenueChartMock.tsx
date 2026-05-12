import { revenueData } from "@/lib/mockData";

export function RevenueChartMock() {
  return (
    <section className="revenue-card card" aria-labelledby="revenue-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Cashflow</p>
          <h2 id="revenue-title">Revenue overview</h2>
        </div>
        <span className="section-pill">Last 6 months</span>
      </div>

      <div className="revenue-total">
        <span>Total collected</span>
        <strong>$60.4k</strong>
      </div>

      <div className="revenue-bars" aria-label="Monthly revenue bar chart">
        {revenueData.map((item) => (
          <div className="revenue-bars__item" key={item.label}>
            <span className="revenue-bars__value">{item.value}</span>
            <span className="revenue-bars__track">
              <span className="revenue-bars__bar" style={{ height: `${item.height}%` }} />
            </span>
            <span className="revenue-bars__label">{item.label}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
