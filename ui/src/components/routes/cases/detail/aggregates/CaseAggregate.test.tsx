import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import CaseAggregate from './CaseAggregate';

const mockShowErrorMessage = vi.hoisted(() => vi.fn());
const mockShowSuccessMessage = vi.hoisted(() => vi.fn());

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key
  })
}));

vi.mock('components/hooks/useMySnackbar', () => ({
  default: () => ({
    showErrorMessage: mockShowErrorMessage,
    showSuccessMessage: mockShowSuccessMessage
  })
}));

vi.mock('@iconify/react', () => ({
  Icon: () => <span />
}));

describe('CaseAggregate', () => {
  const writeText = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    writeText.mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText }
    });
  });

  it('opens a bottom dropdown with the aggregate values and copies them', async () => {
    const user = userEvent.setup();
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText }
    });

    render(
      <CaseAggregate
        field="howler.outline.threat"
        records={[
          { howler: { outline: { threat: 'phishing' } } } as any,
          { howler: { outline: { threat: 'malware' } } } as any,
          { howler: { outline: { threat: 'phishing' } } } as any
        ]}
        subtitle="Threats"
      />
    );

    await user.click(screen.getByRole('button', { name: 'page.cases.dashboard.show_values: Threats' }));

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByRole('dialog').closest('.MuiCollapse-root')).toHaveClass('MuiCollapse-entered')
    );
    expect(screen.getByText('phishing')).toBeInTheDocument();
    expect(screen.getByText('malware')).toBeInTheDocument();

    await user.click(screen.getByRole('checkbox', { name: 'phishing' }));
    await user.click(screen.getByRole('button', { name: 'button.copy' }));

    expect(writeText).toHaveBeenCalledWith('malware');
    expect(mockShowSuccessMessage).toHaveBeenCalledWith('Threats clipboard.success');

    await user.click(screen.getByRole('checkbox', { name: 'page.cases.dashboard.select_all' }));
    await user.click(screen.getByRole('button', { name: 'button.copy' }));

    expect(writeText).toHaveBeenLastCalledWith('phishing, malware');

    await user.click(screen.getByRole('checkbox', { name: 'page.cases.dashboard.select_all' }));
    expect(screen.getByRole('button', { name: 'button.copy' })).toBeDisabled();

    await user.keyboard('{Escape}');
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });
});
