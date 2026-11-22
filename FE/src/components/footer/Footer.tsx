import { Logo } from "@Components/Logo";

const links = [
  {
    label: "GitHub",
    href: "https://github.com/kn-neuron-umg",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <path d="M12 2C6.48 2 2 6.58 2 12.23c0 4.52 2.87 8.35 6.84 9.71.5.1.68-.22.68-.49 0-.24-.01-1.05-.01-1.9-2.78.62-3.37-1.21-3.37-1.21-.45-1.18-1.11-1.49-1.11-1.49-.91-.64.07-.63.07-.63 1 .07 1.53 1.05 1.53 1.05.89 1.56 2.34 1.11 2.91.85.09-.66.35-1.11.64-1.36-2.22-.26-4.55-1.14-4.55-5.07 0-1.12.39-2.04 1.03-2.76-.1-.26-.45-1.31.1-2.72 0 0 .84-.27 2.75 1.05A9.28 9.28 0 0 1 12 6.77c.85 0 1.71.12 2.51.35 1.91-1.32 2.75-1.05 2.75-1.05.55 1.41.2 2.46.1 2.72.64.72 1.03 1.64 1.03 2.76 0 3.94-2.34 4.81-4.57 5.06.36.32.68.94.68 1.9 0 1.37-.01 2.47-.01 2.81 0 .27.18.59.69.49A10.23 10.23 0 0 0 22 12.23C22 6.58 17.52 2 12 2Z" />
      </svg>
    ),
  },
  {
    label: "Instagram",
    href: "https://www.instagram.com/kn_neuron/",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
        <rect x="3" y="3" width="18" height="18" rx="5" />
        <circle cx="12" cy="12" r="4" />
        <circle cx="17.5" cy="6.5" r="1" fill="currentColor" stroke="none" />
      </svg>
    ),
  },
  {
    label: "Facebook",
    href: "https://www.facebook.com/wi.umg",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <path d="M14 8.5V7.2c0-.63.42-.78.72-.78H17V3.02L14.12 3C11.17 3 10.5 5.2 10.5 6.94v1.56H8v3.5h2.5V21h3.5v-9h2.98l.39-3.5H14Z" />
      </svg>
    ),
  },
];

export const Footer = () => {
  return (
    <footer className="mt-6 border-t border-kowr-border bg-kowr-white">
      <div className="mx-auto flex max-w-360 flex-col gap-5 px-5 py-6 md:px-8 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-3">
          <Logo w={52} h={52} />
          <div>
            <strong className="block text-sm text-kowr-forest">Drought Predict</strong>
            <span className="mt-1 block text-xs text-kowr-gray">
              Inteligentne wsparcie gospodarowania wodą
            </span>
          </div>
        </div>
        <nav aria-label="Media społecznościowe" className="flex flex-wrap items-center gap-2">
          {links.map((link) => (
            <a
              key={link.label}
              href={link.href}
              target="_blank"
              rel="noreferrer"
              aria-label={link.label}
              title={link.label}
              className="flex size-10 items-center justify-center rounded-full border border-kowr-border text-kowr-gray transition-colors hover:border-kowr-light-green hover:text-kowr-forest"
            >
              {link.icon}
            </a>
          ))}
        </nav>
      </div>
    </footer>
  );
};
