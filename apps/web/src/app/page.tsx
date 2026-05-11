import { LandingHero } from "@/components/LandingHero";

export default function HomePage() {
  return (
    <>
      <LandingHero />
      <section className="feature-grid">
        {[
          ["Lead capture first", "Let prospects upload a statement and see value before asking them to pay."],
          ["Python extraction retained", "The working PDF and Excel engine stays in Python while the product shell moves to Next.js."],
          ["Paid unlock ready", "Locked sections create the path to Stripe checkout once the funnel is proven."],
        ].map(([title, copy]) => (
          <div className="card" key={title}>
            <h3>{title}</h3>
            <p>{copy}</p>
          </div>
        ))}
      </section>
    </>
  );
}
