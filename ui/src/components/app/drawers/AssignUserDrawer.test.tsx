/// <reference types="vitest" />
import { act, fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockShowInfoMessage = vi.hoisted(() => vi.fn());
const mockAssignPut = vi.hoisted(() => vi.fn((id: string, body: any) => ({ id, body })));

vi.mock('@mui/icons-material', () => ({
  PersonOff: () => <div>person-off</div>
}));

vi.mock('@mui/material', () => ({
  Autocomplete: ({ onChange, options, renderInput, disabled }: any) => (
    <div>
      <div>{String(disabled)}</div>
      <button onClick={() => onChange(null, options[0])}>pick-first</button>
      <button onClick={() => onChange(null, options[options.length - 1])}>pick-unassigned</button>
      {renderInput({})}
    </div>
  ),
  Avatar: ({ children }: any) => <div>{children}</div>,
  Box: ({ children }: any) => <div>{children}</div>,
  Button: ({ children, disabled, onClick }: any) => (
    <button disabled={disabled} onClick={onClick}>
      {children}
    </button>
  ),
  CircularProgress: () => <div>loading</div>,
  Stack: ({ children }: any) => <div>{children}</div>,
  TextField: ({ label }: any) => <div>{label}</div>,
  Typography: ({ children }: any) => <div>{children}</div>
}));

vi.mock('api', () => ({
  default: {
    hit: {
      assign: { put: mockAssignPut }
    }
  }
}));

vi.mock('components/elements/display/HowlerAvatar', () => ({
  default: ({ userId }: any) => <div>{userId}</div>
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('components/hooks/useMySnackbar', () => ({
  default: () => ({ showInfoMessage: mockShowInfoMessage })
}));

vi.mock('components/hooks/useMyUserList', () => ({
  default: () => ({
    alice: { username: 'alice', name: 'Alice', email: 'alice@example.com' }
  })
}));

vi.mock('react-i18next', () => ({
  Trans: ({ i18nKey }: any) => <span>{i18nKey}</span>,
  useTranslation: () => ({ t: (key: string) => key })
}));

import AssignUserDrawer from './AssignUserDrawer';

describe('AssignUserDrawer', () => {
  beforeEach(() => {
    mockDispatchApi.mockReset();
    mockShowInfoMessage.mockReset();
    mockAssignPut.mockReset();
  });

  it('submits assignments through the API and reports success', async () => {
    const onAssigned = vi.fn();
    render(<AssignUserDrawer assignment="unassigned" ids={['h1', 'h2']} onAssigned={onAssigned} />);

    fireEvent.click(screen.getByText('pick-first'));
    await act(async () => {
      fireEvent.click(screen.getByText('button.save'));
    });

    expect(mockAssignPut).toHaveBeenCalledWith('h1', { value: 'alice' });
    expect(mockAssignPut).toHaveBeenCalledWith('h2', { value: 'alice' });
    expect(mockShowInfoMessage).toHaveBeenCalledWith('app.drawer.hit.assignment.success');
    expect(onAssigned).toHaveBeenCalledWith('alice');
  });

  it('supports unassigned targets and skip-submit mode', async () => {
    const onAssigned = vi.fn();
    render(<AssignUserDrawer assignment="alice" ids={['h1']} onAssigned={onAssigned} skipSubmit />);

    fireEvent.click(screen.getByText('pick-unassigned'));
    await act(async () => {
      fireEvent.click(screen.getByText('button.save'));
    });

    expect(mockDispatchApi).not.toHaveBeenCalled();
    expect(onAssigned).toHaveBeenCalledWith('unassigned');
  });
});
