type PlotSelectorProps = {
  date: string;
  onDateChange: (date: string) => void;
};

export const PlotSelector = ({ date, onDateChange }: PlotSelectorProps) => {
  return (
    <section className="rounded-2xl border border-kowr-border bg-kowr-white p-4 shadow-[0_8px_30px_rgba(31,91,70,0.05)]">
      <div className="grid gap-3 md:grid-cols-[minmax(200px,1fr)_200px_170px_auto]">
        <label className="grid gap-1.5 text-xs font-semibold text-kowr-gray">
          Działka
          <input
            type="text"
            placeholder="Miejscowość lub numer działki"
            className="h-11 rounded-xl border border-kowr-border bg-kowr-background px-3.5 text-sm font-normal text-kowr-text outline-none focus:border-kowr-light-green"
          />
        </label>
        <label className="grid gap-1.5 text-xs font-semibold text-kowr-gray">
          Uprawa
          <select
            name="uprawa"
            defaultValue=""
            className="h-11 rounded-xl border border-kowr-border bg-kowr-background px-3.5 text-sm font-normal text-kowr-text outline-none focus:border-kowr-light-green"
          >
            <option value="" disabled>Wybierz uprawę</option>
            <option value="pszenica-ozima">Pszenica ozima</option>
            <option value="pszenica-jara">Pszenica jara</option>
            <option value="rzepak">Rzepak</option>
            <option value="kukurydza">Kukurydza</option>
            <option value="ziemniaki">Ziemniaki</option>
            <option value="burak-cukrowy">Burak cukrowy</option>
          </select>
        </label>
        <label className="grid gap-1.5 text-xs font-semibold text-kowr-gray">
          Data analizy
          <input
            type="date"
            value={date}
            min="2016-11-21"
            max="2026-11-21"
            onChange={(event) => onDateChange(event.target.value)}
            className="h-11 rounded-xl border border-kowr-border bg-kowr-background px-3.5 text-sm font-normal text-kowr-text outline-none focus:border-kowr-light-green"
          />
        </label>
        <div className="flex items-end">
          <button className="h-11 w-full rounded-xl bg-kowr-forest px-5 text-sm font-semibold text-kowr-white transition-colors hover:bg-kowr-green md:w-auto">
            Analizuj działkę
          </button>
        </div>
      </div>
    </section>
  );
};
