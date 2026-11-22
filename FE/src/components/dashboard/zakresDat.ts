// Zakres dat analizy: ostatnie 10 lat do dziś (czas lokalny)
const isoLokalnie = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const DZIS = new Date();

export const DATA_MAX = isoLokalnie(DZIS);
export const DATA_MIN = isoLokalnie(new Date(DZIS.getFullYear() - 10, DZIS.getMonth(), DZIS.getDate()));

/** Pełna data RRRR-MM-DD z dozwolonego zakresu – tylko taką wysyłamy do API.
 *  Chroni przed zapytaniami w trakcie wpisywania roku (0002, 0020, 0202…) i dla pustego pola. */
export const czyPoprawnaData = (d: string) =>
  /^\d{4}-\d{2}-\d{2}$/.test(d) && d >= DATA_MIN && d <= DATA_MAX;
