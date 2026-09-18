/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockShowSuccessMessage = vi.hoisted(() => vi.fn());
const mockSetSearchParams = vi.hoisted(() => vi.fn());
const mockWithConfirmDeleteModal = vi.hoisted(() => vi.fn((cb: () => Promise<void>) => cb()));
const mockTemplateGet = vi.hoisted(() => vi.fn(() => ({ list: true })));
const mockTemplatePut = vi.hoisted(() => vi.fn((id: string, keys: string[]) => ({ id, keys })));
const mockTemplateDelete = vi.hoisted(() => vi.fn((id: string) => ({ id })));
const mockAnalyticSearchPost = vi.hoisted(() => vi.fn((body: any) => body));
const mockGroupedHitPost = vi.hoisted(() => vi.fn((field: string, body: any) => ({ field, body })));
const modalContextToken = vi.hoisted(() => ({ name: 'modal-context' }));

let searchParamsValue = new URLSearchParams('analytic=Alpha&type=personal');

vi.mock('@mui/icons-material', () => ({
  Check: () => <div>check-icon</div>,
  Delete: () => <div>delete-icon</div>,
  SsidChart: () => <div>ssid-icon</div>
}));

vi.mock('@mui/material', () => ({
  Autocomplete: ({ options, value, onChange, renderInput }: any) => (
    <div>
      {renderInput({})}
      <button onClick={() => onChange(null, options[0] ?? null)}>{typeof value === 'object' ? value?.name : value || 'empty'}</button>
    </div>
  ),
  Button: ({ children, onClick, disabled }: any) => <button onClick={onClick} disabled={disabled}>{children}</button>,
  CircularProgress: () => <div>loading</div>,
  Divider: () => <div>divider</div>,
  FormControl: ({ children }: any) => <div>{children}</div>,
  LinearProgress: () => <div>progress</div>,
  Stack: ({ children }: any) => <div>{children}</div>,
  TextField: ({ label, size }: any) => <div>{label ?? size}</div>,
  ToggleButton: ({ children, value }: any) => <button data-value={value}>{children}</button>,
  ToggleButtonGroup: ({ children, onChange }: any) => (
    <div>
      <button onClick={() => onChange(null, 'global')}>switch-global</button>
      {children}
    </div>
  ),
  Tooltip: ({ children }: any) => <>{children}</>
}));

vi.mock('@tui/core', () => ({
  AppInfoPanel: ({ i18nKey }: any) => <div>{i18nKey}</div>,
  PageCenter: ({ children }: any) => <div>{children}</div>
}));

vi.mock('api', () => ({
  default: {
    search: {
      analytic: {
        post: mockAnalyticSearchPost
      },
      grouped: {
        hit: {
          post: mockGroupedHitPost
        }
      }
    },
    template: {
      get: mockTemplateGet,
      put: mockTemplatePut,
      del: mockTemplateDelete
    }
  }
}));

vi.mock('components/app/providers/ModalProvider', () => ({
  ModalContext: modalContextToken
}));

vi.mock('components/elements/hit/HitOutline', () => ({
  DEFAULT_FIELDS: ['default.field']
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('components/hooks/useMySnackbar', () => ({
  default: () => ({ showSuccessMessage: mockShowSuccessMessage })
}));

vi.mock('components/routes/templates/TemplateEditor', () => ({
  default: ({ fields, onAdd, onRemove }: any) => (
    <div>
      <div>{fields.join(',')}</div>
      <button onClick={() => onAdd('field.added')}>add-field</button>
      <button onClick={() => onRemove(fields[0])}>remove-field</button>
    </div>
  )
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react-router', () => ({
  useSearchParams: () => [searchParamsValue, mockSetSearchParams]
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === modalContextToken) return { withConfirmDeleteModal: mockWithConfirmDeleteModal };
      return actual.useContext(context);
    }
  };
});

vi.mock('utils/exampleHit', () => ({
  getExampleHit: () => ({ howler: { analytic: 'example' } })
}));

vi.mock('utils/stringUtils', () => ({
  sanitizeLuceneQuery: (value: string) => value
}));

import TemplateViewer from './TemplateViewer';

describe('TemplateViewer', () => {
  beforeEach(() => {
    searchParamsValue = new URLSearchParams('analytic=Alpha&type=personal');
    mockDispatchApi.mockReset();
    mockShowSuccessMessage.mockReset();
    mockSetSearchParams.mockReset();
    mockWithConfirmDeleteModal.mockClear();
    mockTemplateGet.mockClear();
    mockTemplatePut.mockClear();
    mockTemplateDelete.mockClear();
    mockAnalyticSearchPost.mockClear();
    mockGroupedHitPost.mockClear();
  });

  it('loads an existing template, saves field changes, and deletes the template', async () => {
    mockDispatchApi.mockResolvedValue({ items: [] } as any);
    mockDispatchApi
      .mockResolvedValueOnce({ items: [{ name: 'Alpha' }] })
      .mockResolvedValueOnce([{ template_id: 'tpl-1', analytic: 'Alpha', type: 'personal', keys: ['field.one'] }])
      .mockResolvedValueOnce({ items: [] })
      .mockResolvedValueOnce({ template_id: 'tpl-1', analytic: 'Alpha', type: 'personal', keys: ['field.one', 'field.added'] })
      .mockResolvedValueOnce({});

    render(<TemplateViewer />);

    await waitFor(() => expect(mockTemplateGet).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByText('field.one')).toBeInTheDocument());
    expect(mockSetSearchParams).toHaveBeenCalled();

    fireEvent.click(screen.getByText('add-field'));
    fireEvent.click(screen.getByText('button.save'));

    await waitFor(() => expect(mockTemplatePut).toHaveBeenCalledWith('tpl-1', ['field.one', 'field.added']));

    fireEvent.click(screen.getByText('button.delete'));
    await waitFor(() => expect(mockTemplateDelete).toHaveBeenCalledWith('tpl-1'));
    expect(mockShowSuccessMessage).toHaveBeenCalledWith('route.templates.manager.delete.success');
  });

  it('falls back to default fields when toggling to a type without a saved template', async () => {
    mockDispatchApi.mockResolvedValue({ items: [] } as any);
    mockDispatchApi
      .mockResolvedValueOnce({ items: [{ name: 'Alpha' }] })
      .mockResolvedValueOnce([{ template_id: 'tpl-1', analytic: 'Alpha', type: 'personal', keys: ['field.one'] }])
      .mockResolvedValueOnce({ items: [] });

    render(<TemplateViewer />);

    await waitFor(() => expect(screen.getByText('field.one')).toBeInTheDocument());

    fireEvent.click(screen.getByText('add-field'));
    fireEvent.click(screen.getByText('switch-global'));

    await waitFor(() => expect(screen.getByText('default.field')).toBeInTheDocument());
  });
});
