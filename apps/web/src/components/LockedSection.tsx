export function LockedSection({ items }: { items: string[] }) {
  return (
    <section className="card locked-wrap">
      <div className="locked">
        <div className="eyebrow">Full report</div>
        <h2>Detailed analysis</h2>
        {items.map((item) => (
          <p key={item}>{item}: included in the unlocked report with source mapping.</p>
        ))}
      </div>
    </section>
  );
}
