import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import dayjs from 'dayjs';
import type { PropsWithChildren } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AddEventModal from './AddEventModal';

const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockClose = vi.hoisted(() => vi.fn());
const mockIngestPost = vi.hoisted(() => vi.fn());
const mockItemsPost = vi.hoisted(() => vi.fn());
const mockFieldsGet = vi.hoisted(() => vi.fn());

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('@mui/x-date-pickers/LocalizationProvider', () => ({
  LocalizationProvider: ({ children }: PropsWithChildren) => children
}));

vi.mock('@mui/x-date-pickers/AdapterDayjs', () => ({ AdapterDayjs: class {} }));

vi.mock('@mui/x-date-pickers/DateTimePicker', () => ({
  DateTimePicker: ({ label, onChange }: { label: string; onChange: (value: dayjs.Dayjs) => void }) => (
    <>
      <button type="button" onClick={() => onChange(dayjs('2026-09-21T12:00:00Z'))}>
        {label} valid
      </button>
      <button type="button" onClick={() => onChange(dayjs('not-a-date'))}>
        {label} invalid
      </button>
    </>
  )
}));

vi.mock('api', () => ({
  default: {
    search: {
      fields: {
        event: {
          get: () => mockFieldsGet()
        }
      }
    },
    v2: {
      ingest: {
        post: (...args: unknown[]) => mockIngestPost(...args)
      },
      case: {
        items: {
          post: (...args: unknown[]) => mockItemsPost(...args)
        }
      }
    }
  }
}));

vi.mock('components/app/providers/ModalProvider', async () => {
  const { createContext } = await import('react');
  return {
    ModalContext: createContext({ close: mockClose })
  };
});

const testCase = {
  __index: 'case',
  case_id: 'case-1',
  classification: 'UNCLASSIFIED',
  items: []
} as any;

const fields = [
  {
    key: 'destination.ip',
    default: false,
    indexed: true,
    list: false,
    stored: true,
    type: 'ip',
    description: 'IP address of the destination'
  }
];

const renderModal = () =>
  render(<AddEventModal case={testCase} />, {
    wrapper: ({ children }) => children
  });

describe('AddEventModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('requires escalation in addition to the other required fields', async () => {
    mockFieldsGet.mockResolvedValue(fields);
    mockDispatchApi.mockImplementation(async request => request);

    renderModal();
    await waitFor(() => expect(mockFieldsGet).toHaveBeenCalled());

    fireEvent.change(screen.getByLabelText(/modal\.cases\.add_event\.title/), { target: { value: 'Manual event' } });
    fireEvent.click(screen.getByRole('button', { name: 'modal.cases.add_event.created valid' }));
    fireEvent.change(screen.getByLabelText(/modal\.cases\.add_event\.provider/), { target: { value: 'Analyst' } });
    fireEvent.change(screen.getByLabelText(/modal\.cases\.add_event\.target/), { target: { value: 'host-1' } });

    expect(screen.getByRole('button', { name: 'modal.cases.add_event.submit' })).toBeDisabled();
  });

  it('rejects an invalid created date', async () => {
    const user = userEvent.setup();
    mockFieldsGet.mockResolvedValue(fields);
    mockDispatchApi.mockImplementation(async request => request);

    renderModal();
    await waitFor(() => expect(mockFieldsGet).toHaveBeenCalled());

    fireEvent.change(screen.getByLabelText(/modal\.cases\.add_event\.title/), { target: { value: 'Manual event' } });
    fireEvent.click(screen.getByRole('button', { name: 'modal.cases.add_event.created invalid' }));
    fireEvent.change(screen.getByLabelText(/modal\.cases\.add_event\.provider/), { target: { value: 'Analyst' } });
    fireEvent.change(screen.getByLabelText(/modal\.cases\.add_event\.target/), { target: { value: 'host-1' } });
    await user.click(screen.getByRole('combobox', { name: /modal\.cases\.add_event\.escalation/ }));
    await user.click(await screen.findByRole('option', { name: 'evidence' }));

    expect(screen.getByRole('button', { name: 'modal.cases.add_event.submit' })).toBeDisabled();
  });

  it('fuzzy-searches optional fields and submits summary and escalation', async () => {
    const user = userEvent.setup();
    const updatedCase = { ...testCase, items: [{ type: 'event', value: 'event-1' }] };
    mockFieldsGet.mockResolvedValue(fields);
    mockIngestPost.mockReturnValue(Promise.resolve(['event-1']));
    mockItemsPost.mockReturnValue(Promise.resolve(updatedCase));
    mockDispatchApi.mockImplementation(async request => request);

    renderModal();
    await waitFor(() => expect(mockFieldsGet).toHaveBeenCalled());

    fireEvent.change(screen.getByLabelText(/modal\.cases\.add_event\.title/), { target: { value: 'Manual event' } });
    fireEvent.click(screen.getByRole('button', { name: 'modal.cases.add_event.created valid' }));
    fireEvent.change(screen.getByLabelText(/modal\.cases\.add_event\.provider/), { target: { value: 'Analyst' } });
    await user.click(screen.getByRole('combobox', { name: /modal\.cases\.add_event\.escalation/ }));
    await user.click(await screen.findByRole('option', { name: 'evidence' }));
    fireEvent.change(screen.getByLabelText(/modal\.cases\.add_event\.target/), { target: { value: 'host-1' } });
    fireEvent.change(screen.getByLabelText(/modal\.cases\.add_event\.summary/), {
      target: { value: 'Observed manually' }
    });

    const fieldSearch = screen.getByLabelText(/modal\.cases\.add_event\.search_fields/);
    fireEvent.change(fieldSearch, { target: { value: 'destination IP' } });
    await user.click(await screen.findByText('destination.ip'));
    fireEvent.change(screen.getByLabelText(/destination\.ip/), { target: { value: '192.0.2.10' } });
    await user.click(screen.getByRole('button', { name: 'modal.cases.add_event.submit' }));

    expect(mockIngestPost).toHaveBeenCalledWith(
      'event',
      [
        expect.objectContaining({
          classification: 'UNCLASSIFIED',
          message: 'Manual event',
          event: expect.objectContaining({
            created: '2026-09-21T12:00:00.000Z',
            kind: 'event',
            provider: 'Analyst'
          }),
          howler: expect.objectContaining({
            escalation: 'evidence',
            outline: expect.objectContaining({
              target: 'host-1',
              summary: 'Observed manually'
            })
          }),
          destination: expect.objectContaining({ ip: '192.0.2.10' })
        })
      ],
      'wait_for'
    );
    expect(mockItemsPost).toHaveBeenCalledWith('case-1', {
      type: 'event',
      value: 'event-1',
      name: 'Manual event',
      parent: undefined
    });
    expect(mockClose).toHaveBeenCalled();
  });
});
