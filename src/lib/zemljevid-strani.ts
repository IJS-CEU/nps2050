/** Zemljevid strani po skupinah obiskovalcev: blok »Kaj iščete?« na naslovnici in noga strani. */
import { pageUrl, withBase } from '../i18n/routes';

export interface Skupina { id: string; icon: string; naslov: string; povezave: { label: string; href: string }[] }

export const skupine = (): Skupina[] => [
  { id: 'lastniki', icon: 'house', naslov: 'Za lastnike', povezave: [
    { label: 'Preverite svojo stavbo', href: pageUrl('preveri') },
    { label: 'Paketi prenove', href: pageUrl('paketi') },
    { label: 'Vprašanja in odgovori', href: pageUrl('lastniki') },
    { label: 'Koledar za lastnike', href: `${pageUrl('koledar')}?za=hise` },
    { label: 'Energetska revščina', href: pageUrl('revscina') },
    { label: 'Kaj NPS 2050 ne pomeni', href: pageUrl('napacna') },
  ] },
  { id: 'obcine', icon: 'map', naslov: 'Za občine in regije', povezave: [
    { label: 'Moja občina', href: pageUrl('obcine') },
    { label: 'Primerjava občin', href: pageUrl('primerjava') },
    { label: 'Kartice regij', href: `${pageUrl('obcine')}#regije` },
    { label: 'Tempo prenove na zemljevidu', href: `${pageUrl('obcine')}?kazalnik=t_semafor#graf-obcine` },
    { label: 'Koledar za občine', href: `${pageUrl('koledar')}?za=obcine` },
  ] },
  { id: 'stroka', icon: 'chart-column', naslov: 'Za stroko', povezave: [
    { label: 'Strokovne podlage', href: pageUrl('strokovne-podlage') },
    { label: 'Kaj pa, če? Stopnje prenove', href: `${pageUrl('strokovne-podlage')}#drsnik` },
    { label: 'Ukrepi in financiranje', href: pageUrl('ukrepi') },
    { label: 'Spremljanje', href: pageUrl('spremljanje') },
    { label: 'Podatki za prenos (CSV)', href: `${pageUrl('strokovne-podlage')}#podatkovne-priloge` },
    { label: 'Dokumenti in viri', href: pageUrl('dokumenti') },
  ] },
  { id: 'javnost', icon: 'newspaper', naslov: 'Za javnost in medije', povezave: [
    { label: 'Kaj je NPS 2050', href: pageUrl('kaj-je-nps') },
    { label: 'Javna obravnava', href: pageUrl('javna-obravnava') },
    { label: 'Za medije', href: pageUrl('mediji') },
    { label: 'Povzetek (PDF)', href: withBase('nps2050-povzetek.pdf') },
    { label: 'Slovar izrazov', href: pageUrl('slovar') },
    { label: 'Dnevnik sprememb', href: pageUrl('dnevnik') },
  ] },
];
