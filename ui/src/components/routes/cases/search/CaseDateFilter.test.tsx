/// <reference types="vitest" />
import { render, screen, waitFor } from '@testing-library/react';
import userEvent, { type UserEvent } from '@testing-library/user-event';
import dayjs from 'dayjs';
import i18n from 'i18n';
import type { PropsWithChildren } from 'react';
import { I18nextProvider } from 'react-i18next';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { DateRangeOption } from './CaseDateFilter';
import CaseDateFilter from './CaseDateFilter';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

// ---------------------------------------------------------------------------
// Stub the date pickers so jsdom doesn't choke on them
// ---------------------------------------------------------------------------

vi.mock('@mui/x-date-pickers/DateTimePicker', () => ({
  DateTimePicker: ({ label, onChange }: { label: string; onChange: (v: any) => void }) => (
    <button id={`picker-${label}`} onClick={() => onChange(dayjs('2025-06-01'))}>
      {label}
    </button>
  )
}));

// ---------------------------------------------------------------------------
// Wrapper / render helper
// ---------------------------------------------------------------------------

const FIXED_START = dayjs('2025-01-01');
const FIXED_END = dayjs('2025-03-01');

const Wrapper = ({ children }: PropsWithChildren) => <I18nextProvider i18n={i18n as any}>{children}</I18nextProvider>;

const renderFilter = ({
  dateRange = 'date.range.all' as DateRangeOption,
  onChange = vi.fn(),
  onCustomStartChange = vi.fn(),
  onCustomEndChange = vi.fn()
} = {}) =>
  render(
    <CaseDateFilter
      dateRange={dateRange}
      onChange={onChange}
      customStart={FIXED_START}
      customEnd={FIXED_END}
      onCustomStartChange={onCustomStartChange}
      onCustomEndChange={onCustomEndChange}
    />,
    { wrapper: Wrapper }
  );

const openPopper = async (user: UserEvent) => {
  // The chip label varies; find the chip by the AvTimer icon's sibling
  const chip = document.querySelector('.MuiChip-root') as HTMLElement;
  await user.click(chip);
  await waitFor(() => {
    expect(screen.getByRole('combobox')).toBeInTheDocument();
  });
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('CaseDateFilter', () => {
  let user: UserEvent;

  beforeEach(() => {
    user = userEvent.setup();
    vi.clearAllMocks();
  });

  describe('label', () => {
    it('shows "Date Range" label when date.range.all is selected', () => {
      renderFilter({ dateRange: 'date.range.all' });
      expect(screen.getByText(i18n.t('route.cases.filter.date'))).toBeInTheDocument();
    });

    it('shows the translated range label for a non-all preset', () => {
      renderFilter({ dateRange: 'date.range.1.week' });
      expect(screen.getByText(i18n.t('date.range.1.week'))).toBeInTheDocument();
    });

    it('shows formatted start/end dates for the custom range', () => {
      renderFilter({ dateRange: 'date.range.custom' });
      const expected = `${FIXED_START.format('YYYY-MM-DD')} ${i18n.t('to')} ${FIXED_END.format('YYYY-MM-DD')}`;
      expect(screen.getByText(expected)).toBeInTheDocument();
    });
  });

  describe('chip color', () => {
    it('uses default color for date.range.all', () => {
      renderFilter({ dateRange: 'date.range.all' });
      const chip = document.querySelector('.MuiChip-root');
      expect(chip).not.toHaveClass('MuiChip-colorPrimary');
    });

    it('uses primary color for any non-all range', () => {
      renderFilter({ dateRange: 'date.range.1.day' });
      const chip = document.querySelector('.MuiChip-root');
      expect(chip).toHaveClass('MuiChip-colorPrimary');
    });
  });

  describe('popper content', () => {
    it('does not show the autocomplete before the chip is clicked', () => {
      renderFilter();
      expect(screen.queryByRole('combobox')).toBeNull();
    });

    it('shows the range autocomplete after the chip is clicked', async () => {
      renderFilter();
      await openPopper(user);
      expect(screen.getByRole('combobox')).toBeInTheDocument();
    });

    it('does not show date pickers when a preset (non-custom) range is active', async () => {
      renderFilter({ dateRange: 'date.range.1.day' });
      await openPopper(user);
      expect(screen.queryByTestId(`picker-${i18n.t('date.select.start')}`)).toBeNull();
    });

    it('shows start and end date pickers when custom range is active', async () => {
      renderFilter({ dateRange: 'date.range.custom' });
      await openPopper(user);
      expect(screen.getByTestId(`picker-${i18n.t('date.select.start')}`)).toBeInTheDocument();
      expect(screen.getByTestId(`picker-${i18n.t('date.select.end')}`)).toBeInTheDocument();
    });
  });

  describe('interactions', () => {
    it('calls onChange when a range option is selected from the autocomplete', async () => {
      const onChange = vi.fn();
      renderFilter({ dateRange: 'date.range.all', onChange });
      await openPopper(user);

      await user.click(screen.getByRole('combobox'));
      const option = await screen.findByRole('option', { name: i18n.t('date.range.1.week') });
      await user.click(option);

      expect(onChange).toHaveBeenCalledWith('date.range.1.week');
    });

    it('calls onCustomStartChange when the start date picker fires', async () => {
      const onCustomStartChange = vi.fn();
      renderFilter({ dateRange: 'date.range.custom', onCustomStartChange });
      await openPopper(user);

      await user.click(screen.getByTestId(`picker-${i18n.t('date.select.start')}`));

      expect(onCustomStartChange).toHaveBeenCalledWith(dayjs('2025-06-01'));
    });

    it('calls onCustomEndChange when the end date picker fires', async () => {
      const onCustomEndChange = vi.fn();
      renderFilter({ dateRange: 'date.range.custom', onCustomEndChange });
      await openPopper(user);

      await user.click(screen.getByTestId(`picker-${i18n.t('date.select.end')}`));

      expect(onCustomEndChange).toHaveBeenCalledWith(dayjs('2025-06-01'));
    });
  });
});
