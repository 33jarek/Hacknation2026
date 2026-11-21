import { Logo } from "@Components/Logo";

export const Header = () => {
  return (
    <header className="w-full border-b border-kowr-border bg-kowr-white">
      <div className="mx-auto flex h-16 max-w-[1440px] items-center gap-2 px-5 md:px-8">
        <div className="flex size-10 shrink-0 items-center justify-center">
          <Logo w={40} h={40} />
        </div>
        <div className="mr-auto">
          <h1 className="text-lg font-bold tracking-tight text-kowr-forest">
            Drought Predict
          </h1>
        </div>
        <div className="hidden items-center gap-2 md:flex">
          <span className="size-2 rounded-full bg-kowr-light-green" />
          <span className="text-xs text-kowr-gray">Dane aktualne</span>
        </div>
      </div>
    </header>
  );
};
