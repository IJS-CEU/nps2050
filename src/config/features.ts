/**
 * Zastavice za nove rubrike (CLAUDE.md §11): rubrika se zgradi in je dosegljiva po naslovu, a je do Gašperjeve potrditve
 * skrita – ni v navigaciji in nogi, stran ima noindex. Ob potrditvi se zastavica nastavi na true.
 */
export const features = {
  /** 11.9 Dnevnik sprememb: povezava v nogi ob različici podatkov. */
  dnevnik: true,
  /** 11.4 Paketi prenove: povezava iz orodja Preveri stavbo in s strani Za lastnike. */
  paketi: true,
} as const;
