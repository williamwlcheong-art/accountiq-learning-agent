import { NextResponse } from "next/server";
import { createSupabaseAdminClient } from "@/lib/supabase-admin";
import { createStripeClient } from "@/lib/stripe";

export async function POST(request: Request) {
  const stripe = createStripeClient();
  const webhookSecret = process.env.STRIPE_WEBHOOK_SECRET;

  if (!stripe || !webhookSecret) {
    return NextResponse.json({ error: "Stripe webhook is not configured" }, { status: 503 });
  }

  const signature = request.headers.get("stripe-signature");
  if (!signature) {
    return NextResponse.json({ error: "Missing Stripe signature" }, { status: 400 });
  }

  let event;
  try {
    event = stripe.webhooks.constructEvent(await request.text(), signature, webhookSecret);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Invalid Stripe webhook" },
      { status: 400 },
    );
  }

  if (event.type === "checkout.session.completed") {
    const session = event.data.object;
    const reportId = session.metadata?.report_id;
    const supabase = createSupabaseAdminClient();

    if (supabase && reportId) {
      await supabase
        .from("payments")
        .update({
          amount_total: session.amount_total,
          currency: session.currency,
          status: "paid",
          stripe_customer_id: typeof session.customer === "string" ? session.customer : null,
          stripe_payment_intent_id:
            typeof session.payment_intent === "string" ? session.payment_intent : null,
        })
        .eq("stripe_checkout_session_id", session.id);

      await supabase.from("reports").update({ is_unlocked: true }).eq("id", reportId);
    }
  }

  return NextResponse.json({ received: true });
}
