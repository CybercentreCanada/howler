import type { AppSwitcherItem } from '@tui/apps';

// This list defines the list of apps that will be located in the app switcher.
const APP_SWITCHER_ITEMS = [
  {
    alt: 'AL',
    name: 'Assemblyline',
    img_d: '/branding/assemblyline/swoosh-dark.svg',
    img_l: '/branding/assemblyline/swoosh-light.svg',
    route: '/assemblyline'
  },
  {
    alt: 'LKG',
    name: 'LookingGlass',
    img_d: '/branding/lookingglass/swoosh-dark.svg',
    img_l: '/branding/lookingglass/swoosh-light.svg',
    route: '/lookingglass'
  },
  {
    alt: 'HL',
    name: 'Howler',
    img_d: '/branding/howler/swoosh-dark.svg',
    img_l: '/branding/howler/swoosh-light.svg',
    route: '/howler'
  },
  {
    alt: 'CL',
    name: 'Clue',
    img_d: '/branding/clue/swoosh-dark.svg',
    img_l: '/branding/clue/swoosh-light.svg',
    route: '/clue'
  },
  {
    alt: 'SB',
    name: 'Spellbook',
    img_d: '/branding/spellbook/swoosh-dark.svg',
    img_l: '/branding/spellbook/swoosh-light.svg',
    route: '/spellbook'
  },
  {
    alt: 'ALF',
    name: 'Alfred',
    img_d: '/branding/alfred/swoosh-dark.svg',
    img_l: '/branding/alfred/swoosh-light.svg',
    route: '/alfred'
  },
  {
    alt: 'OD',
    name: 'ObservationDeck',
    img_d: '/branding/odeck/swoosh-dark.svg',
    img_l: '/branding/odeck/swoosh-light.svg',
    route: '/odeck'
  }
];

export const useMyApps = (): AppSwitcherItem[] => {
  return APP_SWITCHER_ITEMS;
};
