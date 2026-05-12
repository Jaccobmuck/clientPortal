type StatCardProps = {
  badge: string;
  title: string;
  trend: string;
  value: string;
  tone: string;
};

export function StatCard({ badge, title, trend, value, tone }: StatCardProps) {
  return (
    <article className={`stat-card card stat-card--${tone}`}>
      <div className="stat-card__top">
        <span className="stat-card__badge">{badge}</span>
        <button className="stat-card__menu" type="button" aria-label={`View ${title}`}>
          View
        </button>
      </div>
      <p>{title}</p>
      <strong>{value}</strong>
      <span>{trend}</span>
    </article>
  );
}
