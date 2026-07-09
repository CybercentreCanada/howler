import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import i18n from 'i18n';
import { I18nextProvider } from 'react-i18next';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import HomeSettings from './HomeSettings';

const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <I18nextProvider i18n={i18n as any}>{children}</I18nextProvider>
);

describe('HomeSettings', () => {
  let onRefreshRateChange: ReturnType<typeof vi.fn>;
  let onEdit: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    onRefreshRateChange = vi.fn();
    onEdit = vi.fn();
    vi.clearAllMocks();
  });

  it('renders the settings icon button', () => {
    render(
      <HomeSettings isEditing={false} refreshRate={30} onRefreshRateChange={onRefreshRateChange} onEdit={onEdit} />,
      { wrapper: Wrapper }
    );
    expect(screen.getByRole('button')).toBeInTheDocument();
  });

  it('opens the settings menu when the icon button is clicked', async () => {
    const user = userEvent.setup();
    render(
      <HomeSettings isEditing={false} refreshRate={30} onRefreshRateChange={onRefreshRateChange} onEdit={onEdit} />,
      { wrapper: Wrapper }
    );

    await user.click(screen.getByRole('button'));
    // The menu should now be open – the edit menu item should be visible
    expect(screen.getByRole('menu')).toBeInTheDocument();
  });

  it('calls onEdit when the Edit menu item is clicked', async () => {
    const user = userEvent.setup();
    render(
      <HomeSettings isEditing={false} refreshRate={30} onRefreshRateChange={onRefreshRateChange} onEdit={onEdit} />,
      { wrapper: Wrapper }
    );

    await user.click(screen.getByRole('button'));
    const editItem = screen.getAllByRole('menuitem')[0];
    await user.click(editItem);
    expect(onEdit).toHaveBeenCalledTimes(1);
  });

  it('disables the Edit menu item when isEditing=true', async () => {
    const user = userEvent.setup();
    render(
      <HomeSettings isEditing={true} refreshRate={30} onRefreshRateChange={onRefreshRateChange} onEdit={onEdit} />,
      { wrapper: Wrapper }
    );

    await user.click(screen.getByRole('button'));
    const editItem = screen.getAllByRole('menuitem')[0];
    expect(editItem).toHaveAttribute('aria-disabled', 'true');
  });
});
