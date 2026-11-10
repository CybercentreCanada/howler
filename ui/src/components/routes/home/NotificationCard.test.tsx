/// <reference types="vitest" />
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import i18n from 'i18n';
import type { PropsWithChildren } from 'react';
import { I18nextProvider } from 'react-i18next';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import NotificationCard from './NotificationCard';

const mockGetUserNotifications = vi.hoisted(() => vi.fn());
const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockMarkRead = vi.hoisted(() => vi.fn());
const mockDelete = vi.hoisted(() => vi.fn());
const mockNavigate = vi.hoisted(() => vi.fn());

vi.mock('api', () => ({
  default: {
    v2: {
      notification: {
        get: {
          user: {
            get: (...args: unknown[]) => mockGetUserNotifications(...args)
          }
        },
        read: {
          post: (...args: unknown[]) => mockMarkRead(...args)
        },
        del: (...args: unknown[]) => mockDelete(...args)
      }
    }
  }
}));

vi.mock('react-router', async importOriginal => ({
  ...(await importOriginal<typeof import('react-router')>()),
  useNavigate: () => mockNavigate
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

const Wrapper = ({ children }: PropsWithChildren) => (
  <I18nextProvider i18n={i18n}>
    <MemoryRouter>{children}</MemoryRouter>
  </I18nextProvider>
);

const notification = (id: string, name: string, read = false) => ({
  notification_id: id,
  recipient: 'owner',
  resource_id: `analytic-${id}`,
  resource_type: 'analytic' as const,
  sender: 'analyst',
  resource_name: name,
  message: `analyst commented on your analytic ${name}.`,
  url: `/analytics/analytic-${id}`,
  created: new Date().toISOString(),
  read
});

const listResponse = (...items: ReturnType<typeof notification>[]) => ({
  items,
  offset: 0,
  rows: items.length,
  total: items.length,
  unread: items.filter(item => !item.read).length
});

const applyUnread = (onUnreadChange: ReturnType<typeof vi.fn>, start: number) =>
  onUnreadChange.mock.calls.reduce(
    (current: number, [update]) => (typeof update === 'function' ? update(current) : update),
    start
  );

describe('NotificationCard', () => {
  let anchor: HTMLElement;

  beforeEach(() => {
    vi.clearAllMocks();
    anchor = document.createElement('button');
    document.body.appendChild(anchor);
    mockGetUserNotifications.mockReturnValue('notification-request');
    mockDispatchApi.mockResolvedValue({ items: [], offset: 0, rows: 25, total: 0 });
  });

  it('does not fetch notifications while closed', () => {
    render(<NotificationCard anchorEl={null} onClose={vi.fn()} />, { wrapper: Wrapper });

    expect(mockGetUserNotifications).not.toHaveBeenCalled();
    expect(mockDispatchApi).not.toHaveBeenCalled();
  });

  it('fetches the latest notifications when opened', async () => {
    mockDispatchApi.mockResolvedValue({
      items: [notification('n-1', 'Suspicious Login'), notification('n-2', 'Brute Force')],
      offset: 0,
      rows: 2,
      total: 2
    });

    render(<NotificationCard anchorEl={anchor} onClose={vi.fn()} />, { wrapper: Wrapper });

    expect(await screen.findByText('analyst commented on your analytic Suspicious Login.')).toBeInTheDocument();
    expect(screen.getByText('analyst commented on your analytic Brute Force.')).toBeInTheDocument();
    expect(mockGetUserNotifications).toHaveBeenCalledWith({ rows: 25 }, expect.any(AbortSignal));
    expect(mockDispatchApi).toHaveBeenCalledWith('notification-request', { showError: false });
    expect(screen.getAllByRole('menuitem')).toHaveLength(2);
  });

  it('shows an empty state when the user has no notifications', async () => {
    render(<NotificationCard anchorEl={anchor} onClose={vi.fn()} />, { wrapper: Wrapper });

    expect(await screen.findByText('You have no notifications.')).toBeInTheDocument();
  });

  it('shows an error when notifications cannot be loaded', async () => {
    mockDispatchApi.mockRejectedValue(new Error('failed'));

    render(<NotificationCard anchorEl={anchor} onClose={vi.fn()} />, { wrapper: Wrapper });

    expect(await screen.findByText('Unable to load notifications.')).toBeInTheDocument();
  });

  it('closes the menu and navigates when a notification is selected', async () => {
    const onClose = vi.fn();
    mockDispatchApi.mockResolvedValue({
      items: [notification('n-1', 'Suspicious Login')],
      offset: 0,
      rows: 1,
      total: 1
    });

    render(<NotificationCard anchorEl={anchor} onClose={onClose} />, { wrapper: Wrapper });

    await userEvent.click(await screen.findByText('analyst commented on your analytic Suspicious Login.'));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(mockNavigate).toHaveBeenCalledWith('/analytics/analytic-n-1');
  });

  it('only offers mark as read for unread notifications', async () => {
    mockDispatchApi.mockResolvedValue(
      listResponse(notification('n-1', 'Suspicious Login'), notification('n-2', 'Brute Force', true))
    );

    render(<NotificationCard anchorEl={anchor} onClose={vi.fn()} />, { wrapper: Wrapper });

    await screen.findByText('analyst commented on your analytic Suspicious Login.');

    expect(screen.getAllByRole('button', { name: 'Mark as read' })).toHaveLength(1);
    expect(screen.getAllByRole('button', { name: 'Delete notification' })).toHaveLength(2);
  });

  it('marks a notification as read without navigating', async () => {
    const onClose = vi.fn();
    mockDispatchApi.mockResolvedValueOnce(listResponse(notification('n-1', 'Suspicious Login')));
    mockMarkRead.mockReturnValue('read-request');

    render(<NotificationCard anchorEl={anchor} onClose={onClose} />, { wrapper: Wrapper });

    await userEvent.click(await screen.findByRole('button', { name: 'Mark as read' }));

    expect(mockMarkRead).toHaveBeenCalledWith('n-1');
    expect(mockDispatchApi).toHaveBeenCalledWith('read-request');
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Mark as read' })).not.toBeInTheDocument());
    expect(screen.getByText('analyst commented on your analytic Suspicious Login.')).toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('keeps a notification unread when marking it read fails', async () => {
    mockDispatchApi.mockResolvedValueOnce(listResponse(notification('n-1', 'Suspicious Login')));
    mockDispatchApi.mockRejectedValueOnce(new Error('failed'));

    render(<NotificationCard anchorEl={anchor} onClose={vi.fn()} />, { wrapper: Wrapper });

    await userEvent.click(await screen.findByRole('button', { name: 'Mark as read' }));

    await waitFor(() => expect(screen.getByRole('button', { name: 'Mark as read' })).toBeEnabled());
  });

  it('removes a deleted notification without navigating', async () => {
    const onClose = vi.fn();
    mockDispatchApi.mockResolvedValueOnce(
      listResponse(notification('n-1', 'Suspicious Login'), notification('n-2', 'Brute Force'))
    );
    mockDelete.mockReturnValue('delete-request');

    render(<NotificationCard anchorEl={anchor} onClose={onClose} />, { wrapper: Wrapper });

    await screen.findByText('analyst commented on your analytic Suspicious Login.');
    await userEvent.click(screen.getAllByRole('button', { name: 'Delete notification' })[0]);

    expect(mockDelete).toHaveBeenCalledWith('n-1');
    expect(mockDispatchApi).toHaveBeenCalledWith('delete-request');
    await waitFor(() =>
      expect(screen.queryByText('analyst commented on your analytic Suspicious Login.')).not.toBeInTheDocument()
    );
    expect(screen.getByText('analyst commented on your analytic Brute Force.')).toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('keeps a notification when deleting it fails', async () => {
    mockDispatchApi.mockResolvedValueOnce(listResponse(notification('n-1', 'Suspicious Login')));
    mockDispatchApi.mockRejectedValueOnce(new Error('failed'));

    render(<NotificationCard anchorEl={anchor} onClose={vi.fn()} />, { wrapper: Wrapper });

    await userEvent.click(await screen.findByRole('button', { name: 'Delete notification' }));

    await waitFor(() => expect(screen.getByRole('button', { name: 'Delete notification' })).toBeEnabled());
    expect(screen.getByText('analyst commented on your analytic Suspicious Login.')).toBeInTheDocument();
  });

  it('reports the unread count from the loaded notifications', async () => {
    const onUnreadChange = vi.fn();
    mockDispatchApi.mockResolvedValue({ ...listResponse(notification('n-1', 'Suspicious Login')), unread: 7 });

    render(<NotificationCard anchorEl={anchor} onClose={vi.fn()} onUnreadChange={onUnreadChange} />, {
      wrapper: Wrapper
    });

    await screen.findByText('analyst commented on your analytic Suspicious Login.');

    expect(onUnreadChange).toHaveBeenCalledWith(7);
  });

  it('decrements the unread count when a notification is marked read', async () => {
    const onUnreadChange = vi.fn();
    mockDispatchApi.mockResolvedValueOnce(listResponse(notification('n-1', 'Suspicious Login')));

    render(<NotificationCard anchorEl={anchor} onClose={vi.fn()} onUnreadChange={onUnreadChange} />, {
      wrapper: Wrapper
    });

    await userEvent.click(await screen.findByRole('button', { name: 'Mark as read' }));

    await waitFor(() => expect(onUnreadChange).toHaveBeenCalledTimes(2));
    expect(applyUnread(onUnreadChange, 0)).toBe(0);
    expect(onUnreadChange.mock.calls[1][0](5)).toBe(4);
    expect(onUnreadChange.mock.calls[1][0](0)).toBe(0);
  });

  it('decrements the unread count only when deleting an unread notification', async () => {
    const onUnreadChange = vi.fn();
    mockDispatchApi.mockResolvedValueOnce(
      listResponse(notification('n-1', 'Suspicious Login'), notification('n-2', 'Brute Force', true))
    );

    render(<NotificationCard anchorEl={anchor} onClose={vi.fn()} onUnreadChange={onUnreadChange} />, {
      wrapper: Wrapper
    });

    await screen.findByText('analyst commented on your analytic Suspicious Login.');
    const [deleteUnread, deleteRead] = screen.getAllByRole('button', { name: 'Delete notification' });

    await userEvent.click(deleteRead);
    await waitFor(() =>
      expect(screen.queryByText('analyst commented on your analytic Brute Force.')).not.toBeInTheDocument()
    );
    expect(onUnreadChange).toHaveBeenCalledTimes(1);

    await userEvent.click(deleteUnread);
    await waitFor(() => expect(onUnreadChange).toHaveBeenCalledTimes(2));
    expect(onUnreadChange.mock.calls[1][0](3)).toBe(2);
  });

  it('does not change the unread count when an action fails', async () => {
    const onUnreadChange = vi.fn();
    mockDispatchApi.mockResolvedValueOnce(listResponse(notification('n-1', 'Suspicious Login')));
    mockDispatchApi.mockRejectedValueOnce(new Error('failed'));

    render(<NotificationCard anchorEl={anchor} onClose={vi.fn()} onUnreadChange={onUnreadChange} />, {
      wrapper: Wrapper
    });

    await userEvent.click(await screen.findByRole('button', { name: 'Mark as read' }));

    await waitFor(() => expect(screen.getByRole('button', { name: 'Mark as read' })).toBeEnabled());
    expect(onUnreadChange).toHaveBeenCalledTimes(1);
  });
});
