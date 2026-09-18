/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockDispatchApi = vi.hoisted(() => vi.fn());

let appUserValue: any = { user: { username: 'demo', roles: ['admin'] } };

vi.mock('@mui/icons-material', async importOriginal => {
  const actual = await importOriginal<typeof import('@mui/icons-material')>();
  return {
    ...actual,
    Add: () => <div>add-icon</div>,
    Delete: () => <div>delete-icon</div>,
    Label: () => <div>label-icon</div>,
    LinkRounded: () => <div>link-icon</div>,
    Plagiarism: () => <div>plagiarism-icon</div>
  };
});

vi.mock('@mui/material', () => ({
  Box: ({ children }: any) => <div>{children}</div>,
  Card: ({ children }: any) => <div>{children}</div>,
  CircularProgress: () => <div>loading</div>,
  Divider: () => <div>divider</div>,
  FormControl: ({ children }: any) => <div>{children}</div>,
  Grid: ({ children }: any) => <div>{children}</div>,
  IconButton: ({ children, onClick, disabled }: any) => <button disabled={disabled} onClick={onClick}>{children}</button>,
  InputAdornment: ({ children }: any) => <div>{children}</div>,
  InputLabel: ({ children }: any) => <div>{children}</div>,
  MenuItem: ({ children }: any) => <div>{children}</div>,
  Select: ({ onChange }: any) => <button onClick={() => onChange({ target: { value: 'Det-2' } })}>set-detection</button>,
  Stack: ({ children }: any) => <div>{children}</div>,
  TextField: ({ label, value, onChange }: any) => (
    <label>
      {label}
      <input aria-label={label} value={value} onChange={onChange} />
    </label>
  ),
  Tooltip: ({ children }: any) => <div>{children}</div>,
  Typography: ({ children }: any) => <div>{children}</div>
}));

vi.mock('@tui/core', () => ({
  useAppUser: () => appUserValue
}));

vi.mock('api', () => ({
  default: {
    analytic: {
      notebooks: {
        post: (id: string, payload: any) => ({ id, payload, op: 'post' }),
        del: (id: string, notebookIds: string[]) => ({ id, notebookIds, op: 'del' })
      }
    }
  }
}));

vi.mock('components/elements/addons/layout/FlexOne', () => ({
  default: () => <div>flex</div>
}));

vi.mock('components/elements/display/HowlerAvatar', () => ({
  default: ({ userId }: any) => <div>{`avatar:${userId}`}</div>
}));

vi.mock('components/elements/hit/HitNotebooks', () => ({
  default: ({ selectedNotebook }: any) => <div>{`hits:${selectedNotebook}`}</div>
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

import AnalyticNotebooks from './AnalyticNotebooks';

describe('AnalyticNotebooks', () => {
  beforeEach(() => {
    appUserValue = { user: { username: 'demo', roles: ['admin'] } };
    mockDispatchApi.mockReset();
  });

  it('adds notebooks and clears the form when the request succeeds', async () => {
    const setAnalytic = vi.fn();
    mockDispatchApi.mockResolvedValueOnce({ analytic_id: 'an-1', notebooks: [] });

    render(
      <AnalyticNotebooks
        analytic={{ analytic_id: 'an-1', detections: ['Det-1', 'Det-2'], notebooks: [] } as any}
        setAnalytic={setAnalytic}
      />
    );

    fireEvent.click(screen.getByText('set-detection'));
    fireEvent.change(screen.getByLabelText('analytic.notebook.name'), { target: { value: 'Notebook 1' } });
    fireEvent.change(screen.getByLabelText('analytic.notebook.link'), { target: { value: 'https://example.test' } });
    fireEvent.click(screen.getByText('add-icon'));

    await waitFor(() =>
      expect(mockDispatchApi).toHaveBeenCalledWith(
        { id: 'an-1', op: 'post', payload: { detection: 'Det-2', link: 'https://example.test', name: 'Notebook 1', value: 'https://example.test' } },
        expect.any(Object)
      )
    );
    expect(setAnalytic).toHaveBeenCalledWith({ analytic_id: 'an-1', notebooks: [] });
    expect(screen.getByLabelText('analytic.notebook.name')).toHaveValue('');
    expect(screen.getByLabelText('analytic.notebook.link')).toHaveValue('');
  });

  it('renders notebooks in detection order and deletes removable entries', async () => {
    const setAnalytic = vi.fn();
    const analytic = {
      analytic_id: 'an-1',
      detections: ['Det-1', 'Det-2'],
      notebooks: [
        { id: 'n2', detection: 'Det-2', name: 'Second', value: 'link-2', user: 'other' },
        { id: 'n1', detection: 'Det-1', name: 'First', value: 'link-1', user: 'demo' }
      ]
    };

    render(<AnalyticNotebooks analytic={analytic as any} setAnalytic={setAnalytic} />);

    expect(screen.getByText('avatar:demo')).toBeInTheDocument();
    expect(screen.getByText('hits:First')).toBeInTheDocument();
    expect(screen.getByText('Det-1')).toBeInTheDocument();

    fireEvent.click(screen.getAllByText('delete-icon')[0]);
    await waitFor(() =>
      expect(mockDispatchApi).toHaveBeenCalledWith({ id: 'an-1', notebookIds: ['n1'], op: 'del' })
    );
    expect(setAnalytic).toHaveBeenCalledWith({
      ...analytic,
      notebooks: [{ id: 'n2', detection: 'Det-2', name: 'Second', value: 'link-2', user: 'other' }]
    });
  });
});
