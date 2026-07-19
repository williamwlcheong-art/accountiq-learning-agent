import { financialStatementLabel } from "@/lib/presentation";
import type { WizardReadiness } from "@/types/domain";

type SourcePeriod = WizardReadiness["source_periods"][number];

type FinancialSourceListProps = {
  sources: SourcePeriod[];
  className?: string;
  filenameFirst?: boolean;
};

export function FinancialSourceList({ sources, className, filenameFirst = false }: FinancialSourceListProps) {
  return (
    <ul className={className}>
      {sources.map((source) => {
        const coverage = `${financialStatementLabel(source.statement)} · ${source.period}`;
        return (
          <li key={`${source.document_id}-${source.statement}-${source.period}`}>
            {filenameFirst ? <><span>{coverage}</span><strong>{source.filename}</strong></> : <><strong>{coverage}</strong><span>{source.filename}</span></>}
          </li>
        );
      })}
    </ul>
  );
}
