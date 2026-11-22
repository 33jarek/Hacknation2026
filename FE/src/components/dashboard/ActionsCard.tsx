import type { RekomendacjaAI } from "@Hooks/useOcenaWilgoci";
import { Card } from "./Card";

type Props = { title: string; recommendations?: RekomendacjaAI[]; className?: string };

const kolorPriorytetu = (p: string) =>
  p === "Pilne" ? "text-red-700" : p === "Polecane" ? "text-kowr-forest" : "text-kowr-gray";

export const ActionsCard = ({ title, recommendations = [], className = "" }: Props) => (
  <Card title={title} className={className}>
    {recommendations.length ? (
      <ul className="divide-y divide-kowr-border">
        {recommendations.map((action, i) => (
          <li key={i} className="py-3 first:pt-0 last:pb-0">
            <div className="flex items-baseline justify-between gap-3">
              <span className="text-sm font-medium text-kowr-text">{action.title}</span>
              <span className={`shrink-0 text-xs ${kolorPriorytetu(action.priority)}`}>{action.priority}</span>
            </div>
            <p className="mt-1 text-xs leading-5 text-kowr-gray">{action.detail}</p>
            {action.evidence && (
              <p className="mt-1 text-[11px] leading-4 text-kowr-gray/80">Na podstawie: {action.evidence}</p>
            )}
          </li>
        ))}
      </ul>
    ) : (
      <p className="text-sm text-kowr-gray">Pojawią się po analizie.</p>
    )}
  </Card>
);
