import Stripe from "stripe";
import { createSupabaseAdminClient } from "@/lib/supabase-admin";

export function createStripeClient() {
  const secretKey = process.env.STRIPE_SECRET_KEY;
  if (!secretKey) {
    return null;
  }

  return new Stripe(secretKey);
}

export async function createReportCheckout(reportId: string) {
  const stripe = createStripeClient();
  const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";
  const priceId = process.env.STRIPE_REPORT_PRICE_ID;

  if (!stripe || !priceId) {
    return `/preview/${reportId}?checkout=demo`;
  }

  const session = await stripe.checkout.sessions.create({
    cancel_url: `${siteUrl}/preview/${reportId}?checkout=cancelled`,
    line_items: [{ price: priceId, quantity: 1 }],
    metadata: {
      report_id: reportId,
    },
    mode: "payment",
    success_url: `${siteUrl}/preview/${reportId}?paid=1&session_id={CHECKOUT_SESSION_ID}`,
  });

  const supabase = createSupabaseAdminClient();
  if (supabase) {
    await supabase.from("payments").insert({
      report_id: reportId,
      status: "pending",
      stripe_checkout_session_id: session.id,
    });
  }

  return session.url ?? `/preview/${reportId}?checkout=created`;
}
