import type { PageId } from './routes';

export const nav: Record<Exclude<PageId, 'domov'>, string> = {
  'kaj-je-nps': 'Kaj je NPS 2050',
  lastniki: 'Za lastnike in občane',
  'strokovne-podlage': 'Strokovne podlage',
  'javna-obravnava': 'Javna obravnava',
  dokumenti: 'Dokumenti in viri',
};

export const ui = {
  siteName: 'NPS 2050',
  siteSub: 'Strokovne podlage za Nacionalni načrt prenove stavb',
  skip: 'Preskoči na vsebino',
  menu: 'Meni',
  mainNav: 'Glavna navigacija',
  themeToDark: 'Preklopi na temno temo',
  themeToLight: 'Preklopi na svetlo temo',
  footerBy:
    'Strokovne podlage pripravlja Center za energetsko učinkovitost Instituta »Jožef Stefan« (IJS CEU) za Ministrstvo za infrastrukturo in energetiko (naročnik).',
  footerVersion: 'Podatki iz osnutka NPS 2050, različica z dne',
  logoIjs: 'Institut »Jožef Stefan«',
  logoMin: 'Ministrstvo za infrastrukturo in energetiko',
  notFound: 'Strani ni mogoče najti.',
  backHome: 'Na naslovno stran',
} as const;
