import type { ReactNode } from "react";

type CardProps = {
  title?: ReactNode;
  aside?: ReactNode;
  className?: string;
  bodyClassName?: string;
  children: ReactNode;
};

export const Card = ({ title, aside, className = "", bodyClassName = "", children }: CardProps) => (
  <section className={`flex flex-col rounded-lg border border-kowr-border bg-kowr-white ${className}`}>
    {(title || aside) && (
      <header className="flex items-baseline justify-between gap-3 px-5 pt-4">
        {title && <h2 className="text-[15px] font-semibold text-kowr-text">{title}</h2>}
        {aside && <div className="text-xs text-kowr-gray">{aside}</div>}
      </header>
    )}
    <div className={`flex-1 px-5 pb-5 ${title || aside ? "pt-3" : "pt-5"} ${bodyClassName}`}>{children}</div>
  </section>
);

export const Stat = ({ value, label, className = "" }: { value: ReactNode; label: ReactNode; className?: string }) => (
  <div className={className}>
    <div className="text-xl font-semibold text-kowr-text tabular-nums">{value}</div>
    <div className="mt-0.5 text-xs text-kowr-gray">{label}</div>
  </div>
);
