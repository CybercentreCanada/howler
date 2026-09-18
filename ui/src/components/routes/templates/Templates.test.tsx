/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockShowSuccessMessage = vi.hoisted(() => vi.fn());
const mockNavigate = vi.hoisted(() => vi.fn());
const mockSetSearchParams = vi.hoisted(() => vi.fn());
const mockLoad = vi.hoisted(() => vi.fn());
const mockRequest = vi.hoisted(() => vi.fn());
const mockRemove = vi.hoisted(() => vi.fn());
const mockGetSearchRequestData = vi.hoisted(() => vi.fn((data: any) => ({ offset: data.offset })));
const mockTemplateDelete = vi.hoisted(() => vi.fn((templateId: string) => ({ templateId })));
const analyticContextToken = vi.hoisted(() => ({ name: 'analytic-context' }));
const listMethodContextToken = vi.hoisted(() => ({ name: 'list-method-context' }));

let searchParamsValue = new URLSearchParams();
let responseValue: any = {
  total: 2,
  items: [
    { template_id: 'tpl-1', type: 'global', analytic: 'Alpha', detection: 'Match', title: 'Zulu' },
    { template_id: 'tpl-2', type: 'personal', analytic: 'Bravo', title: 'Alpha' }
  ]
};
let analyticContextValue: any = {
  analytics: [{ name: 'Alpha', detections: ['match'] }]
};

vi.mock('@mui/icons-material', async importOriginal => {
  const actual = await importOriginal<typeof import('@mui/icons-material')>();
  return {
    ...actual,
    Article: () => <div>article-icon</div>
  };
});

vi.mock('@mui/material', () => ({
  Stack: ({ children }: any) => <div>{children}</div>,
  ToggleButton: ({ children, value }: any) => <button data-value={value}>{children}</button>,
  ToggleButtonGroup: ({ children, onChange }: any) => (
    <div>
      <button onClick={() => onChange(null, ['personal'])}>filter-personal</button>
      <button onClick={() => onChange(null, ['personal', 'global'])}>filter-both</button>
      {children}
    </div>
  ),
  Typography: ({ children }: any) => <div>{children}</div>
}));

vi.mock('@tui/core', () => ({
  useAppUser: () => ({ user: { username: 'demo' } })
}));

vi.mock('api', () => ({
  default: {
    search: {
      template: {
        post: 'template-search'
      }
    },
    template: {
      del: mockTemplateDelete
    }
  }
}));

vi.mock('components/app/providers/AnalyticProvider', () => ({
  AnalyticContext: analyticContextToken
}));

vi.mock('components/app/providers/SearchResponseProvider', () => ({
  __esModule: true,
  default: ({ children }: any) => <div>{children}</div>,
  createSearchResponseContext: () => ({}),
  useSearchResponseContext: () => ({
    response: responseValue,
    request: mockRequest,
    remove: mockRemove,
    getSearchRequestData: mockGetSearchRequestData
  })
}));

vi.mock('components/elements/addons/lists', () => ({
  TuiListProvider: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/elements/addons/lists/TuiListProvider', () => ({
  TuiListMethodContext: listMethodContextToken
}));

vi.mock('components/elements/display/ItemManager', () => ({
  default: (props: any) => (
    <div>
      <button onClick={() => props.onSearch()}>search</button>
      <button onClick={() => props.onPageChange(25)}>page</button>
      <button onClick={() => props.onCreate()}>create</button>
      <button onClick={() => props.onSelect({ item: responseValue.items[0] })}>select</button>
      <div>{props.searchFilters}</div>
      {props.response?.items?.map((item: any) => (
        <div key={item.template_id}>{props.renderer({ item: { item, disabled: item.template_id === 'tpl-1' } }, () => 'card')}</div>
      ))}
    </div>
  )
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('components/hooks/useMyLocalStorage', () => ({
  useMyLocalStorageItem: () => [25]
}));

vi.mock('components/hooks/useMySnackbar', () => ({
  default: () => ({ showSuccessMessage: mockShowSuccessMessage })
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react-router', () => ({
  useNavigate: () => mockNavigate,
  useSearchParams: () => [searchParamsValue, mockSetSearchParams]
}));

vi.mock('./TemplateCard', () => ({
  default: ({ template, error, onRemove, className }: any) => (
    <div>
      <span>{`${template.template_id}:${String(error)}:${className}`}</span>
      <button onClick={() => onRemove(template.template_id)}>remove-{template.template_id}</button>
    </div>
  )
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === analyticContextToken) {
        return analyticContextValue;
      }
      if (context === listMethodContextToken) {
        return { load: mockLoad };
      }
      return actual.useContext(context);
    }
  };
});

import Templates from './Templates';

describe('Templates', () => {
  beforeEach(() => {
    searchParamsValue = new URLSearchParams();
    responseValue = {
      total: 2,
      items: [
        { template_id: 'tpl-1', type: 'global', analytic: 'Alpha', detection: 'Match', title: 'Zulu' },
        { template_id: 'tpl-2', type: 'personal', analytic: 'Bravo', title: 'Alpha' }
      ]
    };
    analyticContextValue = { analytics: [{ name: 'Alpha', detections: ['match'] }] };
    mockDispatchApi.mockReset();
    mockShowSuccessMessage.mockReset();
    mockNavigate.mockReset();
    mockSetSearchParams.mockReset();
    mockLoad.mockReset();
    mockRequest.mockReset();
    mockRemove.mockReset();
    mockTemplateDelete.mockReset();
  });

  it('searches, filters template types, paginates, and navigates', async () => {
    render(<Templates />);

    await waitFor(() =>
      expect(mockRequest).toHaveBeenCalledWith('template-search', {
        query: '*:* AND (type:global OR owner:(demo OR none)) AND type:(*)',
        rows: 25,
        offset: 0
      })
    );
    expect(mockLoad).toHaveBeenCalledWith([
      expect.objectContaining({ id: 'tpl-1', disabled: false }),
      expect.objectContaining({ id: 'tpl-2', disabled: false })
    ]);

    fireEvent.click(screen.getByText('filter-personal'));
    await waitFor(() =>
      expect(mockRequest).toHaveBeenLastCalledWith('template-search', {
        query: '*:* AND (type:global OR owner:(demo OR none)) AND type:(personal)',
        rows: 25,
        offset: 0
      })
    );

    fireEvent.click(screen.getByText('page'));
    expect(mockSetSearchParams).toHaveBeenCalled();

    fireEvent.click(screen.getByText('select'));
    expect(mockNavigate).toHaveBeenCalledWith('/templates/view?type=global&analytic=Alpha&detection=Match');

    fireEvent.click(screen.getByText('create'));
    expect(mockNavigate).toHaveBeenCalledWith('/templates/view');
  });

  it('removes templates successfully', async () => {
    mockDispatchApi.mockResolvedValueOnce({});
    render(<Templates />);

    fireEvent.click(screen.getByText('remove-tpl-1'));
    await waitFor(() => expect(mockTemplateDelete).toHaveBeenCalledWith('tpl-1'));
    expect(mockRemove).toHaveBeenCalledWith('tpl-1');
    expect(mockShowSuccessMessage).toHaveBeenCalledWith('route.templates.manager.delete.success');
  });
});
