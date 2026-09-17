import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type * as TuiCore from '@tui/core';
import { AppBarContext } from 'components/app/providers/AppBarProvider';
import { setupLocalStorageMock } from 'tests/mocks';
import { StorageKey } from 'utils/constants';
import { vi } from 'vitest';
import useMyPreferences from './useMyPreferences';

const resetCookies = vi.hoisted(() => vi.fn());

vi.mock('@tui/core', async () => {
  const actual = await vi.importActual<typeof TuiCore>('@tui/core');
  return {
    ...actual,
    useCookiesStore: (selector: (store: { reset: typeof resetCookies }) => unknown) => selector({ reset: resetCookies })
  };
});

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

const localStorage = setupLocalStorageMock();

const PersonalizationMenu = () => {
  const preferences = useMyPreferences();
  return <>{preferences.topnav!.profile!.slots!.bottom}</>;
};

describe('PersonalizationMenuItems', () => {
  beforeEach(() => {
    localStorage.clear();
    resetCookies.mockReset();
  });

  it('resets the pivot-grouping preference with the other personalization settings', async () => {
    const user = userEvent.setup();

    render(
      <AppBarContext.Provider
        value={{ leftItems: [], rightItems: [], addToAppBar: vi.fn(), removeFromAppBar: vi.fn() }}
      >
        <PersonalizationMenu />
      </AppBarContext.Provider>
    );

    await user.click(screen.getByRole('switch'));
    expect(localStorage.getItem(`howler.ui.${StorageKey.PIVOT_GROUP}`)).toBe('false');

    await user.click(screen.getByTestId('personalization-reset'));

    expect(resetCookies).toHaveBeenCalledOnce();
    expect(localStorage.getItem(`howler.ui.${StorageKey.PIVOT_GROUP}`)).toBeNull();
    expect(screen.getByRole('switch')).toBeChecked();
  });
});
