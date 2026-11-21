const weatherItems = [
  { label: "Temperatura", value: "21°C", icon: "T" },
  { label: "Opady", value: "18 mm", icon: "O" },
  { label: "Wilgotność", value: "68%", icon: "W" },
];

export const WeatherPlaceholder = () => {
  return (
    <section className="rounded-2xl border border-kowr-border bg-kowr-white p-5">
      <div className="mb-4">
        <p className="text-xs font-bold uppercase tracking-widest text-kowr-gray">Pogoda</p>
        <h2 className="mt-1 text-lg font-bold text-kowr-text">Najbliższe dane</h2>
      </div>
      <div className="grid grid-cols-3 gap-2">
        {weatherItems.map((item) => (
          <div key={item.label} className="rounded-xl border border-kowr-border bg-kowr-background px-2 py-4 text-center">
            <span className="flex center mx-auto mb-2 size-7 rounded-full bg-kowr-white text-xs font-bold text-kowr-forest">{item.icon}</span>
            <strong className="block text-base text-kowr-text">{item.value}</strong>
            <span className="mt-1 block text-[10px] text-kowr-gray">{item.label}</span>
          </div>
        ))}
      </div>
      <div className="mt-3 flex center min-h-20 rounded-xl border border-dashed border-kowr-sage bg-kowr-background text-xs text-kowr-gray">
        Placeholder informacji pogodowej z backendu
      </div>
    </section>
  );
};
