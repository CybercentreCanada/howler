/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockShowErrorMessage = vi.hoisted(() => vi.fn());
const mockShowModal = vi.hoisted(() => vi.fn((node: any) => node.props.onConfirm()));
const mockNotebookPost = vi.hoisted(() => vi.fn((body: any) => body));
const mockEnvironmentsGet = vi.hoisted(() => vi.fn(() => ({ envs: true })));
const apiConfigContextToken = vi.hoisted(() => ({ name: 'api-config-context' }));
const modalContextToken = vi.hoisted(() => ({ name: 'modal-context' }));

let configValue: any = {
  configuration: {
    features: {
      notebook: true
    }
  }
};

vi.mock('@mui/material', () => ({
  Avatar: ({ children }: any) => <div>{children}</div>,
  Backdrop: ({ children, open }: any) => open ? <div>{children}</div> : null,
  Box: ({ children }: any) => <div>{children}</div>,
  Button: ({ children, onClick, disabled }: any) => <button onClick={onClick} disabled={disabled}>{children}</button>,
  Chip: ({ label }: any) => <span>{label}</span>,
  CircularProgress: () => <div>loading</div>,
  ClickAwayListener: ({ children }: any) => <>{children}</>,
  Fade: ({ children }: any) => <>{children}</>,
  MenuItem: ({ children, value, disabled }: any) => <option value={value} disabled={disabled}>{children}</option>,
  Paper: ({ children }: any) => <div>{children}</div>,
  Popper: ({ children, open }: any) => open ? children({ TransitionProps: {} }) : null,
  Stack: ({ children }: any) => <div>{children}</div>,
  TextField: ({ children, label, onChange, defaultValue, disabled, select }: any) =>
    select ? (
      <label>
        {label}
        <select aria-label={label} defaultValue={defaultValue} onChange={onChange} disabled={disabled}>
          {children}
        </select>
      </label>
    ) : (
      <label>
        {label}
        <input aria-label={label} onChange={onChange} disabled={disabled} />
      </label>
    ),
  Tooltip: ({ children }: any) => <>{children}</>
}));

vi.mock('api', () => ({
  default: {
    notebook: {
      environments: {
        get: mockEnvironmentsGet
      },
      post: mockNotebookPost
    }
  }
}));

vi.mock('components/app/providers/ApiConfigProvider', () => ({
  ApiConfigContext: apiConfigContextToken
}));

vi.mock('components/app/providers/ModalProvider', () => ({
  ModalContext: modalContextToken
}));

vi.mock('components/elements/display/HowlerCard', () => ({
  default: ({ children, onClick }: any) => <button onClick={onClick}>{children}</button>
}));

vi.mock('components/elements/hit/NotebookTooltip', () => ({
  default: () => <div>tooltip</div>
}));

vi.mock('components/elements/display/modals/ConfirmNotebookModal', () => ({
  default: ({ onConfirm }: any) => <button onClick={onConfirm}>confirm notebook</button>
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('components/hooks/useMySnackbar', () => ({
  default: () => ({ showErrorMessage: mockShowErrorMessage })
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === apiConfigContextToken) return { config: configValue };
      if (context === modalContextToken) return { showModal: mockShowModal };
      return actual.useContext(context);
    }
  };
});

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('utils/stringUtils', async importOriginal => {
  const actual = await importOriginal<typeof import('utils/stringUtils')>();
  return {
    ...actual,
    safeStringPropertyCompare: (key: string) => (a: any, b: any) => String(a[key] ?? '').localeCompare(String(b[key] ?? ''))
  };
});

import HitNotebooks from './HitNotebooks';

describe('HitNotebooks', () => {
  beforeEach(() => {
    configValue = { configuration: { features: { notebook: true } } };
    mockDispatchApi.mockReset();
    mockShowErrorMessage.mockReset();
    mockShowModal.mockClear();
    mockNotebookPost.mockClear();
    mockEnvironmentsGet.mockClear();
    vi.stubGlobal('fetch', vi.fn());
    vi.stubGlobal('open', vi.fn());
  });

  it('loads notebook content and opens jupyter when the notebook does not already exist', async () => {
    mockDispatchApi
      .mockResolvedValueOnce({ envs: [{ name: 'env', url: 'https://nb.example', default: true, user_interface: 'lab' }] })
      .mockResolvedValueOnce({ nb_content: { cells: [] }, name: 'Loaded Notebook' });
    (globalThis.fetch as any)
      .mockResolvedValueOnce({ status: 404 })
      .mockResolvedValueOnce({ status: 200 });

    render(
      <HitNotebooks
        analytic={{ notebooks: [{ name: 'Notebook A', value: 'link-a', detection: 'det-b' }] } as any}
        selectedNotebook="Notebook A"
        hit={{ howler: { id: 'hit-1' } } as any}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /hit\.notebook\.tooltip/i }));

    await waitFor(() => expect(mockDispatchApi).toHaveBeenCalledTimes(2));
    expect(mockNotebookPost).toHaveBeenCalledWith(
      expect.objectContaining({
        link: 'link-a',
        hit: { howler: { id: 'hit-1' } }
      })
    );

    fireEvent.click(screen.getByText('hit.notebook.goTo'));

    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalledWith(
      'https://nb.example/api/contents/Loaded Notebook - hit-1.ipynb',
      expect.any(Object)
    ));
    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalledWith(
      'https://nb.example/post/Loaded Notebook - hit-1.ipynb',
      expect.objectContaining({ method: 'post' })
    ));
    expect(globalThis.open).toHaveBeenCalledWith('https://nb.example/lab/tree/Loaded Notebook - hit-1.ipynb', '_blank');
  });

  it('confirms overwrite for existing notebooks and can hide itself when notebooks are disabled', async () => {
    configValue = { configuration: { features: { notebook: false } } };
    const { rerender } = render(<HitNotebooks analytic={{ notebooks: [{ name: 'Notebook A', value: 'link-a' }] } as any} />);
    expect(screen.queryByText('hit.notebook.tooltip')).not.toBeInTheDocument();

    configValue = { configuration: { features: { notebook: true } } };
    mockDispatchApi
      .mockResolvedValueOnce({ envs: [{ name: 'env', url: 'https://nb.example/', default: true, user_interface: 'lab' }] })
      .mockResolvedValueOnce({ nb_content: { cells: [] }, name: 'Notebook A' });
    (globalThis.fetch as any)
      .mockResolvedValueOnce({ status: 200 })
      .mockResolvedValueOnce({ status: 200 });

    rerender(<HitNotebooks analytic={{ notebooks: [{ name: 'Notebook A', value: 'link-a' }] } as any} selectedNotebook="Notebook A" />);

    fireEvent.click(screen.getByRole('button', { name: /hit\.notebook\.tooltip/i }));
    await waitFor(() => expect(mockDispatchApi).toHaveBeenCalledTimes(2));

    fireEvent.click(screen.getByText('hit.notebook.goTo'));

    await waitFor(() => expect(mockShowModal).toHaveBeenCalled());
    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalledWith(
      'https://nb.example/post/Notebook A.ipynb',
      expect.objectContaining({ method: 'post' })
    ));
  });
});
