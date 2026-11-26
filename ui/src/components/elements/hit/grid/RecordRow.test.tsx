import { Table, TableBody } from '@mui/material';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RecordContext, type RecordContextType } from 'components/app/providers/RecordProvider';
import type { Event } from 'models/entities/generated/Event';
import type { Hit } from 'models/entities/generated/Hit';
import { MemoryRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';
import RecordRow from './RecordRow';

vi.mock('components/elements/hit/HitCard', () => ({
  default: ({ id }: { id?: string }) => <div id="hit-card">{id}</div>
}));
vi.mock('components/elements/event/EventCard', () => ({
  default: ({ event }: { event?: Event }) => <div id="event-card">{event?.howler.id}</div>
}));
vi.mock('components/elements/hit/elements/EscalationChip', () => ({
  default: () => <span id="hit-escalation" />
}));
vi.mock('components/elements/hit/elements/Assigned', () => ({
  default: () => <span id="hit-assignment" />
}));
vi.mock('./EnhancedCell', () => ({
  default: () => null
}));

const renderRow = (record: Hit | Event) => {
  const onClick = vi.fn();
  const context: RecordContextType = {
    records: {},
    selectedRecords: [],
    addRecordToSelection: vi.fn(),
    removeRecordFromSelection: vi.fn(),
    clearSelectedRecords: vi.fn(),
    loadRecords: vi.fn(),
    updateRecord: vi.fn(),
    getRecord: vi.fn()
  };
  return {
    ...render(
      <MemoryRouter>
        <RecordContext.Provider value={context}>
          <Table>
            <TableBody>
              <RecordRow
                record={record}
                analyticIds={{ Analytic: 'analytic-1' }}
                columns={[]}
                columnWidths={{}}
                collapseMainColumn={false}
                onClick={onClick}
              />
            </TableBody>
          </Table>
        </RecordContext.Provider>
      </MemoryRouter>
    ),
    onClick
  };
};

describe('RecordRow', () => {
  it('preserves hit analytic links, detections, assignment, and hit expansion', async () => {
    const hit: Hit = {
      __index: 'hit',
      timestamp: '2026-01-01T00:00:00Z',
      howler: { id: 'hit-1', hash: 'abc', analytic: 'Analytic', detection: 'Detection', assignment: 'alice' }
    };
    const user = userEvent.setup();
    const { onClick } = renderRow(hit);

    const analytic = screen.getByRole('link', { name: 'Analytic' });
    expect(analytic).toHaveAttribute('href', '/analytics/analytic-1');
    expect(screen.getByTestId('hit-1')).toHaveTextContent('Analytic: Detection');
    expect(screen.getByTestId('hit-escalation')).toBeInTheDocument();
    expect(screen.getByTestId('hit-assignment')).toBeInTheDocument();
    await user.click(analytic);
    expect(onClick).not.toHaveBeenCalled();
    await user.click(screen.getByRole('button'));
    expect(await screen.findByTestId('hit-card')).toHaveTextContent('hit-1');
    expect(screen.queryByTestId('event-card')).not.toBeInTheDocument();
    expect(onClick).not.toHaveBeenCalled();
  });

  it.each([
    { message: 'VPN activity', provider: 'collector', label: 'VPN activity' },
    { message: '', provider: 'collector', label: 'collector' },
    { message: '', provider: undefined, label: 'event-1' }
  ])(
    'renders and expands an event using its message, provider, or id: $label',
    async ({ message, provider, label }) => {
      const event: Event = {
        __index: 'event',
        timestamp: '2026-01-01T00:00:00Z',
        message,
        event: { provider },
        howler: { id: 'event-1', hash: 'abc' }
      };
      const user = userEvent.setup();
      const { onClick } = renderRow(event);

      expect(screen.getByTestId('event-1')).toHaveTextContent(label);
      expect(screen.queryByRole('link')).not.toBeInTheDocument();
      expect(screen.queryByTestId('hit-escalation')).not.toBeInTheDocument();
      expect(screen.queryByTestId('hit-assignment')).not.toBeInTheDocument();
      await user.click(screen.getByRole('button'));
      expect(await screen.findByTestId('event-card')).toHaveTextContent('event-1');
      expect(screen.queryByTestId('hit-card')).not.toBeInTheDocument();
      expect(onClick).not.toHaveBeenCalled();
      await user.click(screen.getByTestId('event-1'));
      expect(onClick).toHaveBeenCalledWith(expect.anything(), event);
    }
  );
});
