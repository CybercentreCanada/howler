/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import i18n from 'i18n';
import type { Dispatch, SetStateAction } from 'react';
import { I18nextProvider } from 'react-i18next';
import { beforeEach, describe, expect, it, vi, type Mock } from 'vitest';
import HomeSettings from './HomeSettings';

vi.mock('./NotificationCard', () => ({
  default: ({
    anchorEl,
    onUnreadChange
  }: {
    anchorEl: HTMLElement | null;
    onUnreadChange: Dispatch<SetStateAction<number>>;
  }) =>
    anchorEl ? (
      <div id="notification-card">
        notification-card
        <button onClick={() => onUnreadChange(current => current - 1)}>read-one</button>
      </div>
    ) : null
}));

const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <I18nextProvider i18n={i18n as any}>{children}</I18nextProvider>
);

describe('HomeSettings', () => {
  let onRefreshRateChange: Mock<(rate: number) => void>;
  let onEdit: Mock<() => void>;
  let onUnreadNotificationsChange: Mock<Dispatch<SetStateAction<number>>>;

  const renderSettings = (props: { isEditing?: boolean; unreadNotifications?: number } = {}) =>
    render(
      <HomeSettings
        isEditing={props.isEditing ?? false}
        refreshRate={30}
        onRefreshRateChange={onRefreshRateChange}
        onEdit={onEdit}
        unreadNotifications={props.unreadNotifications ?? 0}
        onUnreadNotificationsChange={onUnreadNotificationsChange}
      />,
      { wrapper: Wrapper }
    );

  beforeEach(() => {
    vi.clearAllMocks();
    onRefreshRateChange = vi.fn<(rate: number) => void>();
    onEdit = vi.fn<() => void>();
    onUnreadNotificationsChange = vi.fn<Dispatch<SetStateAction<number>>>();
  });

  it('renders the settings icon button', () => {
    renderSettings();

    expect(screen.getByRole('button', { name: 'Open dashboard settings' })).toBeInTheDocument();
  });

  it('opens the settings menu when the icon button is clicked', async () => {
    const user = userEvent.setup();
    renderSettings();

    await user.click(screen.getByRole('button', { name: 'Open dashboard settings' }));

    expect(screen.getByRole('menu')).toBeInTheDocument();
  });

  it('calls onEdit when the Edit menu item is clicked', async () => {
    const user = userEvent.setup();
    renderSettings();

    await user.click(screen.getByRole('button', { name: 'Open dashboard settings' }));
    await user.click(screen.getAllByRole('menuitem')[0]);

    expect(onEdit).toHaveBeenCalledTimes(1);
  });

  it('disables the Edit menu item when isEditing=true', async () => {
    const user = userEvent.setup();
    renderSettings({ isEditing: true });

    await user.click(screen.getByRole('button', { name: 'Open dashboard settings' }));

    expect(screen.getAllByRole('menuitem')[0]).toHaveAttribute('aria-disabled', 'true');
  });

  it('opens the notification card when the notification icon is clicked', async () => {
    const user = userEvent.setup();
    renderSettings();

    expect(screen.queryByTestId('notification-card')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Open notifications' }));

    expect(screen.getByTestId('notification-card')).toBeInTheDocument();
  });

  it('shows an inactive bell without a badge when there are no unread notifications', () => {
    renderSettings({ unreadNotifications: 0 });

    expect(screen.getByTestId('notifications-none-icon')).toBeInTheDocument();
    expect(screen.queryByTestId('notifications-active-icon')).not.toBeInTheDocument();
    expect(screen.getByTestId('notification-badge').querySelector('.MuiBadge-invisible')).not.toBeNull();
  });

  it('shows an active bell with the unread count', () => {
    renderSettings({ unreadNotifications: 3 });

    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByTestId('notifications-active-icon')).toBeInTheDocument();
    expect(screen.getByTestId('notification-badge').querySelector('.MuiBadge-invisible')).toBeNull();
  });

  it('caps the unread badge at 99+', () => {
    renderSettings({ unreadNotifications: 150 });

    expect(screen.getByText('99+')).toBeInTheDocument();
  });

  it('forwards unread count changes from the notification card', async () => {
    const user = userEvent.setup();
    renderSettings({ unreadNotifications: 2 });

    await user.click(screen.getByRole('button', { name: 'Open notifications' }));
    await user.click(screen.getByRole('button', { name: 'read-one' }));

    expect(onUnreadNotificationsChange).toHaveBeenCalledTimes(1);
    const update = onUnreadNotificationsChange.mock.calls[0][0] as (current: number) => number;
    expect(update(2)).toBe(1);
  });
});
