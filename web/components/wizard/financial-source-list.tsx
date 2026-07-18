import { financialStatementLabel } from "@/lib/presentation";
import type { WizardReadiness } from "@/types/domain";

type SourcePeriod = WizardReadiness["source_periods"][number];

type FinancialSourceListProps = {
  sources: SourcePeriod[];
  className?: string;
  filenameFirst?: boolean;
};

export function formatMoney(amountCents: number, currency: string) {
  return new Intl.NumberFormat("en-NZ", {
    style: "currency",
    currency: currency.toUpperCase(),
  }).format(amountCents / 100);
}

export function formatStatement(statement: string) {
  return financialStatementLabel(statement);
}

export function FinancialSourceList({ sources, className, filenameFirst = false }: FinancialSourceListProps) {
  return (
    <ul className={className}>
      {sources.map((source) => {
        const coverage = `${formatStatement(source.statement)} · ${source.period}`;
        return (
          <li key={`${source.document_id}-${source.statement}-${source.period}`}>
            {filenameFirst ? <><span>{coverage}</span><strong>{source.filename}</strong></> : <><strong>{coverage}</strong><span>{source.filename}</span></>}
          </li>
        );
      })}
    </ul>
  );
}
