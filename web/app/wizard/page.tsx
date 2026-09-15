import type { Metadata } from "next";

import { Wizard } from "@/components/wizard/wizard";
import { requireUser } from "@/lib/auth";

export const metadata: Metadata = {
  title: "New valuation | AccountIQ",
  description: "Upload financial statements and order an indicative business valuation report.",
};

export default async function WizardPage() {
  const user = await requireUser();
  return <Wizard user={user} />;
}
