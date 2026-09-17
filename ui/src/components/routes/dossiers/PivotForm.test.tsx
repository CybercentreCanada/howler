import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import type { Dossier } from 'models/entities/generated/Dossier';
import type { Pivot } from 'models/entities/generated/Pivot';
import { useState, type PropsWithChildren } from 'react';
import { MemoryRouter } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import PivotForm from './PivotForm';

const mockGroupsGet = vi.hoisted(() => vi.fn());
const mockExecuteFunction = vi.hoisted(() => vi.fn());

vi.mock('api', () => ({
  default: {
    dossier: {
      groups: {
        get: mockGroupsGet
      }
    }
  }
}));

vi.mock('@iconify/react', () => ({
  Icon: ({ icon }: { icon: string }) => <span data-testid="pivot-icon">{icon}</span>,
  iconExists: (icon: string) => icon.startsWith('material-symbols:')
}));

vi.mock('plugins/store', () => ({
  default: {
    pivotFormats: []
  }
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    i18n: { language: 'en' },
    t: (key: string) => key
  })
}));

vi.mock('react-pluggable', () => ({
  usePluginStore: () => ({ executeFunction: mockExecuteFunction })
}));

const basePivot = (overrides: Partial<Pivot> = {}): Pivot =>
  ({
    icon: 'material-symbols:link',
    label: { en: 'Example', fr: 'Exemple' },
    format: 'link',
    value: 'https://example.test/{{id}}',
    mappings: [],
    ...overrides
  }) as Pivot;

const baseDossier = (pivot: Pivot): Partial<Dossier> => ({
  dossier_id: 'dossier-1',
  pivots: [pivot]
});

const renderForm = (pivot: Pivot = basePivot(), loading = false) => {
  const Wrapper = ({ children }: PropsWithChildren) => {
    const [dossier, setDossier] = useState<Partial<Dossier>>(baseDossier(pivot));

    return (
      <ApiConfigContext.Provider
        value={{
          config: { indexes: { hit: { 'howler.id': {}, 'event.domain': {} } } } as any,
          setConfig: vi.fn(),
          loaded: true
        }}
      >
        {children}
        <output id="dossier-state">{JSON.stringify(dossier)}</output>
        <PivotForm dossier={dossier as Dossier} setDossier={setDossier} loading={loading} />
      </ApiConfigContext.Provider>
    );
  };

  return render(
    <MemoryRouter initialEntries={['/dossiers/dossier-1/edit?pivot=0']}>
      <Wrapper />
    </MemoryRouter>
  );
};

describe('PivotForm', () => {
  beforeEach(() => {
    mockGroupsGet.mockReset();
    mockExecuteFunction.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('shows inline validation feedback for malformed groups and removes the group when cleared', async () => {
    const user = userEvent.setup();
    renderForm(basePivot({ group: 'network//dns' }));

    const groupInput = screen.getByRole('combobox', { name: 'route.pivots.groups.label' });
    expect(groupInput).toHaveValue('network//dns');
    expect(groupInput).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByText('route.dossiers.pivots.invalid.format')).toBeInTheDocument();

    await user.clear(groupInput);

    expect(groupInput).toHaveValue('');
    expect(screen.getByText('route.dossiers.pivot.explanation')).toBeInTheDocument();
    expect(screen.getByTestId('dossier-state')).not.toHaveTextContent('"group"');
  });

  it('loads at most ten group suggestions after the throttled request', async () => {
    const user = userEvent.setup();
    mockGroupsGet.mockResolvedValue(Array.from({ length: 12 }, (_, index) => `network/${index}`));

    renderForm(basePivot({ group: 'network' }));
    const groupInput = screen.getByRole('combobox', { name: 'route.pivots.groups.label' });

    await user.click(groupInput);
    await waitFor(
      () => {
        expect(mockGroupsGet).toHaveBeenCalledWith('network');
      },
      { timeout: 3000 }
    );

    expect(await screen.findByRole('option', { name: 'network/0' })).toBeInTheDocument();
    expect(screen.getAllByRole('option')).toHaveLength(10);
    expect(screen.queryByRole('option', { name: 'network/10' })).not.toBeInTheDocument();
  });

  it('clears suggestions when the latest request fails', async () => {
    mockGroupsGet.mockImplementation((prefix: string) =>
      prefix === 'network' ? Promise.resolve(['network/dns']) : Promise.reject(new Error('request failed'))
    );

    renderForm();
    const groupInput = screen.getByRole('combobox', { name: 'route.pivots.groups.label' });

    fireEvent.change(groupInput, { target: { value: 'network' } });
    await waitFor(
      () => {
        expect(mockGroupsGet).toHaveBeenCalledWith('network');
      },
      { timeout: 3000 }
    );
    fireEvent.mouseDown(screen.getByTitle('Open'));
    await waitFor(() => expect(screen.getByRole('option', { name: 'network/dns' })).toBeInTheDocument());

    fireEvent.change(groupInput, { target: { value: 'other' } });
    await waitFor(
      () => {
        expect(mockGroupsGet).toHaveBeenLastCalledWith('other');
      },
      { timeout: 3000 }
    );

    await waitFor(() => expect(screen.queryByRole('option', { name: 'network/dns' })).not.toBeInTheDocument());
  });

  it('adds a link mapping and displays the custom value field when selected', async () => {
    const user = userEvent.setup();
    renderForm();

    await user.click(screen.getByTestId('add-pivot'));

    const mappingKey = screen.getByRole('textbox', { name: 'route.dossiers.manager.pivot.mapping.key' });
    await user.clear(mappingKey);
    await user.type(mappingKey, 'id');

    const field = screen.getByRole('combobox', { name: 'route.dossiers.manager.pivot.mapping.field' });
    await user.click(field);
    await user.click(screen.getByRole('option', { name: 'custom' }));

    const customValue = screen.getByRole('textbox', { name: 'route.dossiers.manager.pivot.mapping.custom' });
    await user.type(customValue, 'fixed-value');

    expect(screen.getByTestId('dossier-state')).toHaveTextContent('"key":"id"');
    expect(screen.getByTestId('dossier-state')).toHaveTextContent('"field":"custom"');
    expect(screen.getByTestId('dossier-state')).toHaveTextContent('"custom_value":"fixed-value"');
  });
});
