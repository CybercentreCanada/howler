import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createElement } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { createMockCase } from 'tests/utils';
import { describe, expect, it, vi } from 'vitest';
import type { ObservableEntry } from '../types';
import ObservableTable from './ObservableTable';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('components/elements/PluginTypography', () => ({
  default: ({ value }: { value: string }) => createElement('span', null, value)
}));

const makeObservable = (overrides: Partial<ObservableEntry> = {}): ObservableEntry => ({
  type: 'ip',
  value: '192.168.1.1',
  sources: [],
  ...overrides
});

const renderTable = (observables: ObservableEntry[]) => {
  render(
    <MemoryRouter>
      <ObservableTable observables={observables} case={createMockCase({ case_id: 'case-123' })} />
    </MemoryRouter>
  );
};

const getObservableValues = (): string[] =>
  screen
    .getAllByRole('row')
    .slice(1)
    .map(row => within(row).getAllByRole('cell')[1].textContent ?? '');

describe('ObservableTable', () => {
  it('sorts by type initially and reverses the sort when the active column is clicked', async () => {
    const user = userEvent.setup();
    renderTable([
      makeObservable({ type: 'user', value: 'bravo' }),
      makeObservable({ type: 'hash', value: 'alpha' }),
      makeObservable({ type: 'ip', value: 'charlie' })
    ]);

    expect(getObservableValues()).toEqual(['alpha', 'charlie', 'bravo']);

    await user.click(screen.getByText('page.cases.observables.columns.type'));

    expect(getObservableValues()).toEqual(['bravo', 'charlie', 'alpha']);
  });

  it('sorts observables numerically by their source count', async () => {
    const user = userEvent.setup();
    renderTable([
      makeObservable({
        value: 'three',
        sources: [
          { id: 'one', type: 'hit' },
          { id: 'two', type: 'hit' },
          { id: 'three', type: 'hit' }
        ]
      }),
      makeObservable({ value: 'one', sources: [{ id: 'one', type: 'hit' }] }),
      makeObservable({
        value: 'two',
        sources: [
          { id: 'one', type: 'hit' },
          { id: 'two', type: 'hit' }
        ]
      })
    ]);

    await user.click(screen.getByText('page.cases.observables.columns.seen_in'));

    expect(getObservableValues()).toEqual(['one', 'two', 'three']);
  });

  it('links a single source and renders its role and escalation', () => {
    renderTable([
      makeObservable({
        role: 'threat',
        sources: [{ id: 'source-1', type: 'hit', path: 'alerts/one', label: 'Alert one', escalation: 'evidence' }]
      })
    ]);

    expect(screen.getByText('page.cases.observables.role.threat')).toBeInTheDocument();
    expect(screen.getByText('evidence')).toBeInTheDocument();
    expect(screen.getByText('Alert one').closest('a')).toHaveAttribute('href', '/cases/case-123/alerts/one');
  });

  it('shows every linked source in the popover and de-duplicates escalations', async () => {
    const user = userEvent.setup();
    renderTable([
      makeObservable({
        sources: [
          { id: 'source-1', type: 'hit', path: 'alerts/one', label: 'Alert one', escalation: 'evidence' },
          {
            id: 'source-2',
            type: 'event',
            path: 'events/two',
            label: 'Event two',
            escalation: 'evidence'
          },
          { id: 'source-3', type: 'case', escalation: 'malicious' }
        ]
      })
    ]);

    expect(screen.getByText('Alert one (+1)')).toBeInTheDocument();
    expect(screen.getAllByText('evidence')).toHaveLength(1);
    expect(screen.getByText('malicious')).toBeInTheDocument();

    await user.click(screen.getByText('Alert one (+1)'));

    expect(screen.getByText('Observable two').closest('a')).toHaveAttribute('href', '/cases/case-123/observables/two');
  });
});
