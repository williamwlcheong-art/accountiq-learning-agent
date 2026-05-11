import Link from "next/link";
import { unlockReport } from "@/app/preview/[id]/actions";
import { LockedSection } from "@/components/LockedSection";
import { PreviewReport } from "@/components/PreviewReport";
import { getReportForPreview } from "@/lib/mock-report";

export default async function PreviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const report = await getReportForPreview(id);

  return (
    <div className="form-grid">
      <PreviewReport report={report} />
      <LockedSection items={report.lockedSections} />
      <div className="actions">
        <form action={unlockReport}>
          <input type="hidden" name="reportId" value={report.id} />
          <button className="button" type="submit">
            Unlock full analysis
          </button>
        </form>
        <Link href="/upload" className="button secondary">
          Upload another statement
        </Link>
      </div>
    </div>
  );
}
