import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { setupLocalStorageMock } from 'tests/mocks';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

import PivotGroupMenuItem from './PivotGroupMenuItem';

const mockLocalStorage = setupLocalStorageMock();

describe('PivotGroupMenuItem', () => {
  beforeEach(() => {
    mockLocalStorage.clear();
  });

  it('toggles the preference when the row is clicked', async () => {
    render(<PivotGroupMenuItem />);

    expect(screen.getByRole('switch')).toBeChecked();

    await userEvent.setup().click(screen.getByTestId('personalization-pivot-group'));

    expect(screen.getByRole('switch')).not.toBeChecked();
  });

  it('toggles the preference when the switch is clicked', async () => {
    render(<PivotGroupMenuItem />);

    expect(screen.getByRole('switch')).toBeChecked();

    await userEvent.setup().click(screen.getByRole('switch'));

    expect(screen.getByRole('switch')).not.toBeChecked();
  });
});
