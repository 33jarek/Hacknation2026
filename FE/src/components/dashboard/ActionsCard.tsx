const actions = [
  { title: "Sprawdź wilgotność gleby", detail: "Monitoruj warstwę 10–20 cm przez 7 dni.", priority: "Pilne" },
  { title: "Zachowaj resztki pożniwne", detail: "Zmniejszą parowanie i ograniczą erozję.", priority: "Polecane" },
  { title: "Spowolnij odpływ wody", detail: "Rozważ małe rowki retencyjne po opadach.", priority: "Długoterminowe" },
];

export const ActionsCard = () => {
  return (
    <section className="rounded-2xl border border-kowr-border bg-kowr-white p-5">
      <div className="mb-3">
        <p className="text-xs font-bold uppercase tracking-widest text-kowr-gray">Rekomendacje</p>
        <h2 className="mt-1 text-lg font-bold text-kowr-text">Co zrobić dalej</h2>
      </div>
      <div className="divide-y divide-kowr-border">
        {actions.map((action, index) => (
          <button key={action.title} className="grid w-full grid-cols-[32px_1fr] gap-3 py-3 text-left">
            <span className="flex center size-8 rounded-full bg-kowr-sage/35 text-xs font-bold text-kowr-forest">{index + 1}</span>
            <span>
              <span className="flex items-center justify-between gap-2">
                <strong className="text-sm text-kowr-text">{action.title}</strong>
                <span className="shrink-0 text-[9px] font-bold uppercase tracking-wide text-kowr-gray">{action.priority}</span>
              </span>
              <span className="mt-1 block text-xs leading-5 text-kowr-gray">{action.detail}</span>
            </span>
          </button>
        ))}
      </div>
    </section>
  );
};
