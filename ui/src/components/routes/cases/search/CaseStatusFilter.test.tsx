/// <reference types="vitest" />
import { render, screen, waitFor } from '@testing-library/react';
import userEvent, { type UserEvent } from '@testing-library/user-event';
import i18n from 'i18n';
import type { PropsWithChildren } from 'react';
import { I18nextProvider } from 'react-i18next';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import CaseStatusFilter from './CaseStatusFilter';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const Wrapper = ({ children }: PropsWithChildren) => <I18nextProvider i18n={i18n as any}>{children}</I18nextProvider>;

const renderFilter = (statusFilter: string[], onChange = vi.fn()) =>
  render(<CaseStatusFilter statusFilter={statusFilter} onChange={onChange} />, { wrapper: Wrapper });

const openPopper = async (user: UserEvent) => {
  const chip = screen.getByText(i18n.t('route.cases.filter.status')).closest('.MuiChip-root');
  await user.click(chip);
  await waitFor(() => {
    expect(screen.getByRole('group')).toBeInTheDocument();
  });
};

describe('CaseStatusFilter', () => {
  let user: UserEvent;

  beforeEach(() => {
    user = userEvent.setup();
    vi.clearAllMocks();
  });

  describe('label', () => {
    it('shows the default "Status" label when no statuses are selected', () => {
      renderFilter([]);
      expect(screen.getByText(i18n.t('route.cases.filter.status'))).toBeInTheDocument();
    });

    it('shows a comma-separated list of status labels when statuses are selected', () => {
      renderFilter(['open', 'on-hold']);
      const expected = [i18n.t('page.cases.status.open'), i18n.t('page.cases.status.on-hold')].join(', ');
      expect(screen.getByText(expected)).toBeInTheDocument();
    });

    it('shows a single status label when one status is selected', () => {
      renderFilter(['resolved']);
      expect(screen.getByText(i18n.t('page.cases.status.resolved'))).toBeInTheDocument();
    });
  });

  describe('chip color', () => {
    it('uses default color when no statuses are selected', () => {
      renderFilter([]);
      const chip = screen.getByText(i18n.t('route.cases.filter.status')).closest('.MuiChip-root');
      expect(chip).not.toHaveClass('MuiChip-colorPrimary');
    });

    it('uses primary color when statuses are selected', () => {
      renderFilter(['open']);
      const chip = screen.getByText(i18n.t('page.cases.status.open')).closest('.MuiChip-root');
      expect(chip).toHaveClass('MuiChip-colorPrimary');
    });
  });

  describe('popper content', () => {
    it('does not show toggle buttons before the chip is clicked', () => {
      renderFilter([]);
      expect(screen.queryByRole('group')).toBeNull();
    });

    it('shows all four status toggle buttons when the chip is clicked', async () => {
      renderFilter([]);
      await openPopper(user);

      expect(screen.getByText(i18n.t('page.cases.status.open'))).toBeInTheDocument();
      expect(screen.getByText(i18n.t('page.cases.status.in-progress'))).toBeInTheDocument();
      expect(screen.getByText(i18n.t('page.cases.status.on-hold'))).toBeInTheDocument();
      expect(screen.getByText(i18n.t('page.cases.status.resolved'))).toBeInTheDocument();
    });
  });

  describe('interactions', () => {
    it('calls onChange when a toggle button is clicked', async () => {
      const onChange = vi.fn();
      renderFilter([], onChange);
      await openPopper(user);

      await user.click(screen.getByText(i18n.t('page.cases.status.open')));

      expect(onChange).toHaveBeenCalledWith(['open']);
    });

    it('calls onChange with empty array when the only selected status is deselected', async () => {
      const onChange = vi.fn();
      renderFilter(['open'], onChange);

      const chip = screen.getByText(i18n.t('page.cases.status.open')).closest('.MuiChip-root');
      await user.click(chip);
      await waitFor(() => {
        expect(screen.getByRole('group')).toBeInTheDocument();
      });

      await user.click(screen.getAllByText(i18n.t('page.cases.status.open'))[1]);

      expect(onChange).toHaveBeenCalledWith([]);
    });
  });
});
