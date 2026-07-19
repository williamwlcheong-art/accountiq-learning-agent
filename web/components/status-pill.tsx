import { reportStatusLabel, reportStatusTone } from "@/lib/presentation";

type StatusPillProps = {
  status: string;
};

export function StatusPill({ status }: StatusPillProps) {
  return (
    <span className={`status-pill status-${reportStatusTone(status)}`}>
      {reportStatusLabel(status)}
    </span>
  );
}
