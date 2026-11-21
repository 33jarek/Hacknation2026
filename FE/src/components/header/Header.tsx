export const Header = () => {
  return (
    <header className="w-dvw">
      <div className="w-full flex flex-col center py-3 bg-kowr-green">
        <h1 className="text-5xl font-semibold">DroughtPredict</h1>
      </div>
      <div className="flex center bg-kowr-light-green text-xl py-3 gap-6">
        <input
          type="text"
          placeholder="Miejscowość, NR. Identyfikacyjny"
          className="border border-"
        />
        <select name="uprawa" id="uprawa" defaultValue="">
          <option value="" disabled>
            Wybierz uprawę
          </option>
          <option value="pszenica-ozima">Pszenica ozima</option>
          <option value="pszenica-jara">Pszenica jara</option>
          <option value="rzepak">Rzepak</option>
          <option value="kukurydza">Kukurydza</option>
          <option value="ziemniaki">Ziemniaki</option>
          <option value="burak-cukrowy">Burak cukrowy</option>
        </select>
      </div>
    </header>
  );
};
