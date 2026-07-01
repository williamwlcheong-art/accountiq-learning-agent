import { Wizard } from "@/components/wizard/wizard";
import { requireUser } from "@/lib/auth";

export default async function WizardPage() {
  const user = await requireUser();
  return <Wizard user={user} />;
}
