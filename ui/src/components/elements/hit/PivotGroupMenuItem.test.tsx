import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const mockToggle = vi.fn();

vi.mock('components/app/providers/PivotGroupProvider', () => ({
  usePivotGroup: () => ({ enabled: true, toggle: mockToggle })
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

import PivotGroupMenuItem from './PivotGroupMenuItem';

describe('PivotGroupMenuItem', () => {
  beforeEach(() => {
    mockToggle.mockReset();
  });

  it('toggles once when the row is clicked', async () => {
    render(<PivotGroupMenuItem />);

    await userEvent.setup().click(screen.getByTestId('personalization-pivot-group'));

    expect(mockToggle).toHaveBeenCalledOnce();
  });

  it('toggles once when the switch is clicked', async () => {
    render(<PivotGroupMenuItem />);

    await userEvent.setup().click(screen.getByRole('switch'));

    expect(mockToggle).toHaveBeenCalledOnce();
  });
});
