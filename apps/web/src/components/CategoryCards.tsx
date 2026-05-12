import { categories } from "@/lib/mockData";

export function CategoryCards() {
  return (
    <section className="category-section" aria-labelledby="categories-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Revenue mix</p>
          <h2 id="categories-title">Categories</h2>
        </div>
      </div>

      <div className="category-grid">
        {categories.map((category) => (
          <article className={`category-card category-card--${category.tone}`} key={category.title}>
            <span>{category.title}</span>
            <strong>{category.value}</strong>
            <p>{category.detail}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
