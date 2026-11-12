import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import CaseRecordRow from 'components/routes/cases/modals/CaseRecordRow';
import { describe, expect, it, vi } from 'vitest';
import { AddRecordsPreview } from './CaseDocumentationPreviews';

vi.mock('components/routes/cases/modals/CaseRecordRow', async importOriginal => {
  const actual = await importOriginal<typeof import('components/routes/cases/modals/CaseRecordRow')>();
  return { default: vi.fn(actual.default) };
});
vi.mock('components/routes/cases/modals/CaseSelector', () => ({ default: () => null }));
vi.mock('components/elements/display/Notebook', () => ({ Notebook: () => null }));
vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key }) }));

describe('AddRecordsPreview', () => {
  it('renders and edits a real event example without hit-only analytic data', async () => {
    const user = userEvent.setup();
    render(<AddRecordsPreview />);

    expect(screen.getByText('Event')).toBeInTheDocument();
    expect(screen.getByText('event-vpn-001')).toBeInTheDocument();
    const record = vi.mocked(CaseRecordRow).mock.calls[0][0].entry.record;
    expect(record.__index).toBe('event');
    expect(record.message).toBe('Manual evidence from VPN investigation');
    expect(record.howler).not.toHaveProperty('analytic');
    expect(record.howler).not.toHaveProperty('detection');
    const name = screen.getByPlaceholderText('modal.cases.add_to_case.name');
    await user.clear(name);
    await user.type(name, 'Updated event evidence');
    expect(name).toHaveValue('Updated event evidence');
  });
});
