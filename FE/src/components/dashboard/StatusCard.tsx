export const StatusCard = () => {
  return (
    <section className="grid min-h-52 overflow-hidden rounded-2xl border border-kowr-border bg-kowr-white md:grid-cols-[1fr_220px_260px]">
      <div className="flex flex-col justify-center p-6 md:p-8">
        <p className="mb-3 text-xs font-bold uppercase tracking-widest text-kowr-gray">Stan działki</p>
        <div className="flex items-center gap-3">
          <div className="flex center size-12 shrink-0 rounded-full bg-kowr-beige text-kowr-forest">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
              <path d="M12 2.8S5.5 10 5.5 15a6.5 6.5 0 0 0 13 0C18.5 10 12 2.8 12 2.8Z" />
            </svg>
          </div>
          <div>
            <h2 className="text-2xl font-bold tracking-tight text-kowr-text">Umiarkowany niedobór wody</h2>
            <p className="mt-1 text-sm text-kowr-gray">Miejsce na krótkie uzasadnienie analizy</p>
          </div>
        </div>
      </div>
      <div className="flex center flex-col border-t border-kowr-border bg-kowr-background px-6 py-5 md:border-l md:border-t-0">
        <span className="text-xs text-kowr-gray">Percentyl wobec tej pory roku</span>
        <strong className="mt-1 text-4xl font-bold text-kowr-olive">24.</strong>
        <span className="mt-1 text-xs text-kowr-gray">z danych 10-letnich</span>
      </div>
      <div className="flex flex-col justify-center border-t border-kowr-border px-6 py-5 md:border-l md:border-t-0">
        <span className="text-xs text-kowr-gray">Przedział niepewności</span>
        <strong className="mt-1 text-xl font-bold text-kowr-text">18–30% wilgotności</strong>
        <span className="mt-2 text-[11px] leading-4 text-kowr-gray">Szacowany zakres modelu dla wybranego dnia</span>
      </div>
    </section>
  );
};
