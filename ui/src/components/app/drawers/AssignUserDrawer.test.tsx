import type { AutocompleteProps } from '@mui/material';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { HowlerUser } from 'models/entities/HowlerUser';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AssignUserDrawer from './AssignUserDrawer';

type UserAutocompleteProps = AutocompleteProps<HowlerUser, false, false, false>;

const mockAutocomplete = vi.hoisted(() => vi.fn<(props: UserAutocompleteProps) => void>());
const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockShowInfoMessage = vi.hoisted(() => vi.fn());
const mockAssignPut = vi.hoisted(() => vi.fn((id: string, body: { value: string | null }) => ({ id, body })));

vi.mock('@mui/material', async importOriginal => {
  const material = await importOriginal<typeof import('@mui/material')>();
  return {
    ...material,
    Autocomplete: (props: UserAutocompleteProps) => {
      mockAutocomplete(props);
      return <material.Autocomplete {...props} />;
    }
  };
});

vi.mock('api', () => ({
  default: {
    hit: {
      assign: { put: mockAssignPut }
    }
  }
}));

vi.mock('components/elements/display/HowlerAvatar', () => ({
  default: () => null
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('components/hooks/useMySnackbar', () => ({
  default: () => ({ showInfoMessage: mockShowInfoMessage })
}));

vi.mock('components/hooks/useMyUserList', () => {
  const users = {
    alice1: { username: 'alice1', name: 'Alice Duplicate', email: ' ALICE@EXAMPLE.COM ' },
    alice: { username: 'alice', name: 'Alice', email: 'alice@example.com' },
    bob: { username: 'bob', name: 'Bob Duplicate', email: 'other@example.com' },
    BOB: { username: 'BOB', name: 'Bob', email: 'bob@example.com' },
    charlie: { username: 'charlie', name: 'C. Smith', email: 'charlie@example.com' },
    chris: { username: 'chris', name: 'C. Smith', email: 'chris@example.com' },
    dee: { username: 'dee', name: 'Dee', email: null },
    ellen: { username: 'ellen', name: 'Ellen' }
  };
  return { default: () => users };
});

vi.mock('react-i18next', () => ({
  Trans: ({ i18nKey }: { i18nKey: string }) => <span>{i18nKey}</span>,
  useTranslation: () => ({ t: (key: string) => key })
}));

describe('AssignUserDrawer', () => {
  beforeEach(() => {
    mockAutocomplete.mockClear();
    mockDispatchApi.mockReset();
    mockShowInfoMessage.mockReset();
    mockAssignPut.mockReset();
  });

  it('passes one option per identity plus unassigned to Autocomplete', () => {
    render(<AssignUserDrawer assignment="unassigned" ids={['h1']} onAssigned={vi.fn()} />);

    const { options } = mockAutocomplete.mock.lastCall![0];
    expect(options.map(user => user.username).sort()).toEqual([
      'BOB',
      'alice',
      'charlie',
      'chris',
      'dee',
      'ellen',
      'unassigned'
    ]);
  });

  it('submits the canonical username through the API and reports success', async () => {
    const user = userEvent.setup();
    const onAssigned = vi.fn();
    render(<AssignUserDrawer assignment="unassigned" ids={['h1', 'h2']} onAssigned={onAssigned} />);

    await user.click(screen.getByRole('combobox'));
    await user.click(screen.getByRole('option', { name: /alice/i }));
    await user.click(screen.getByRole('button', { name: 'button.save' }));

    await waitFor(() => expect(onAssigned).toHaveBeenCalledWith('alice'));
    expect(mockAssignPut).toHaveBeenCalledWith('h1', { value: 'alice' });
    expect(mockAssignPut).toHaveBeenCalledWith('h2', { value: 'alice' });
    expect(mockShowInfoMessage).toHaveBeenCalledWith('app.drawer.hit.assignment.success');
  });

  it.each([
    { assignment: 'alice1', name: 'Alice', username: 'alice', skipSubmit: false },
    { assignment: 'bob', name: 'Bob', username: 'BOB', skipSubmit: true }
  ])(
    'shows the canonical option for $assignment and lets the user save it',
    async ({ assignment, name, username, skipSubmit }) => {
      const user = userEvent.setup();
      const onAssigned = vi.fn();
      render(<AssignUserDrawer assignment={assignment} ids={['h1']} onAssigned={onAssigned} skipSubmit={skipSubmit} />);

      const input = screen.getByRole('combobox');
      const save = screen.getByRole('button', { name: 'button.save' });
      expect(input).toHaveValue(name);
      expect(save).toBeDisabled();

      await user.click(input);
      const option = screen.getByRole('option', { name: new RegExp(name, 'i') });
      expect(option).toHaveAttribute('aria-selected', 'true');
      await user.click(option);
      expect(save).toBeEnabled();
      await user.click(save);

      await waitFor(() => expect(onAssigned).toHaveBeenCalledWith(username));
      if (skipSubmit) {
        expect(mockDispatchApi).not.toHaveBeenCalled();
      } else {
        expect(mockAssignPut).toHaveBeenCalledWith('h1', { value: username });
      }
    }
  );

  it('filters by name even when email is null or missing', async () => {
    const user = userEvent.setup();
    render(<AssignUserDrawer assignment="unassigned" ids={['h1']} onAssigned={vi.fn()} />);

    await user.type(screen.getByRole('combobox'), 'eE');

    expect(screen.getAllByRole('option')).toHaveLength(1);
    expect(screen.getByRole('option', { name: 'Dee' })).toBeVisible();
  });

  it.each([false, true])('supports unassigned targets with skipSubmit=%s', async skipSubmit => {
    const user = userEvent.setup();
    const onAssigned = vi.fn();
    render(<AssignUserDrawer assignment="alice" ids={['h1']} onAssigned={onAssigned} skipSubmit={skipSubmit} />);

    await user.click(screen.getByRole('combobox'));
    await user.click(screen.getByRole('option', { name: /unassigned\.name/ }));
    await user.click(screen.getByRole('button', { name: 'button.save' }));

    await waitFor(() => expect(onAssigned).toHaveBeenCalledWith('unassigned'));
    if (skipSubmit) {
      expect(mockDispatchApi).not.toHaveBeenCalled();
    } else {
      expect(mockAssignPut).toHaveBeenCalledWith('h1', { value: null });
    }
  });
});
