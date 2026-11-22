import type { PrzyczynaAI } from "@Hooks/useOcenaWilgoci";
import { Card } from "./Card";

type Props = { causes?: PrzyczynaAI[]; className?: string };

export const CausesCard = ({ causes = [], className = "" }: Props) => (
  <Card title="Co wpływa na wilgotność" className={className}>
    {causes.length ? (
      <ul className="divide-y divide-kowr-border">
        {causes.map((cause, i) => (
          <li key={i} className="py-3 first:pt-0 last:pb-0">
            <div className="text-sm font-medium text-kowr-text">{cause.title}</div>
            <div className="mt-0.5 text-sm text-kowr-text/80">{cause.value}</div>
            <div className="mt-1 text-xs text-kowr-gray">{cause.detail}</div>
          </li>
        ))}
      </ul>
    ) : (
      <p className="text-sm text-kowr-gray">Pojawi się po analizie.</p>
    )}
  </Card>
);
