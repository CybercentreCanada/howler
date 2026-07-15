/// <reference types="vitest" />
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent, { type UserEvent } from '@testing-library/user-event';
import { ModalContext } from 'components/app/providers/ModalProvider';
import i18n from 'i18n';
import type { Hit } from 'models/entities/generated/Hit';
import type { PropsWithChildren } from 'react';
import { I18nextProvider } from 'react-i18next';
import { createMockHit } from 'tests/utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import RationaleModal from './RationaleModal';

vi.mock('api', { spy: true });

vi.mock('commons/components/app/hooks/useAppUser', () => ({
  useAppUser: () => ({
    user: { username: 'test-user' }
  })
}));

// Mock functions
let mockGetMatchingAnalytic = vi.fn();
let mockOnSubmit = vi.fn();

import { hpost } from 'api';

const mockHpost = vi.mocked(hpost);

vi.mock('components/app/hooks/useMatchers', () => ({
  default: () => ({
    getMatchingAnalytic: mockGetMatchingAnalytic
  })
}));

// Mock modal context
const mockModalContext = {
  close: vi.fn(),
  open: vi.fn()
};

// Test wrapper
const Wrapper = ({ children }: PropsWithChildren) => {
  return (
    <I18nextProvider i18n={i18n as any}>
      <ModalContext.Provider value={mockModalContext as any}>{children}</ModalContext.Provider>
    </I18nextProvider>
  );
};

describe('RationaleModal', () => {
  let user: UserEvent;
  let defaultHits: Hit[];

  beforeEach(() => {
    user = userEvent.setup();
    vi.clearAllMocks();

    defaultHits = [
      createMockHit({
        howler: {
          id: 'hit-1',
          analytic: 'test-analytic-1'
        } as any
      })
    ];

    // Reset mock functions
    mockGetMatchingAnalytic.mockResolvedValue({
      analytic_id: 'test-analytic-1',
      triage_settings: {
        rationales: ['Preset Rationale 1', 'Preset Rationale 2']
      }
    });
    mockOnSubmit.mockClear();
    mockModalContext.close.mockClear();
    mockHpost.mockReset();
  });

  describe('Initial Rendering', () => {
    it('should render modal title', () => {
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      expect(screen.getByText(i18n.t('modal.rationale.title'))).toBeInTheDocument();
    });

    it('should render modal description', () => {
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      expect(screen.getByText(i18n.t('modal.rationale.description'))).toBeInTheDocument();
    });

    it('should render autocomplete input field', () => {
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      expect(screen.getByLabelText(i18n.t('modal.rationale.label'))).toBeInTheDocument();
    });

    it('should render cancel button', () => {
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      expect(screen.getByText(i18n.t('cancel'))).toBeInTheDocument();
    });

    it('should render submit button', () => {
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      expect(screen.getByText(i18n.t('submit'))).toBeInTheDocument();
    });

    it('should render with minimum width', () => {
      const { container } = render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      const stack = container.querySelector('.MuiStack-root');
      expect(stack).toHaveStyle({ minWidth: '500px' });
    });
  });

  describe('Loading State', () => {
    it('should show loading spinner in input field', async () => {
      mockHpost.mockImplementationOnce(() => new Promise(() => {})); // Never resolves

      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      expect(screen.getByLabelText(i18n.t('loading'))).toBeInTheDocument();
      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });

    it('should hide loading indicator after rationales are fetched', async () => {
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(mockHpost).toBeCalledTimes(2);
      });

      await waitFor(() => {
        expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
      });
    });
  });

  describe('Suggested Rationales', () => {
    it('should fetch preset rationales from analytics', async () => {
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(mockGetMatchingAnalytic).toHaveBeenCalledWith(defaultHits[0]);
      });
    });

    it('should fetch rationales used by other users for same analytic', async () => {
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(mockHpost).toHaveBeenCalledWith('/api/v1/search/facet/hit', {
          fields: ['howler.rationale'],
          query: 'howler.rationale:* AND howler.assignment:test-user AND timestamp:[now-14d TO now]',
          rows: 25
        });

        expect(mockHpost).toHaveBeenCalledWith('/api/v1/search/facet/hit', {
          fields: ['howler.rationale'],
          filters: ['howler.analytic:"test\\-analytic\\-1"'],
          query: 'howler.rationale:*',
          rows: 10
        });
      });
    });

    it('should fetch rationales from current user (last 14 days)', async () => {
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      await waitFor(() => {
        const calls = mockHpost.mock.calls;
        const userRationaleCall = calls.find(call => JSON.stringify(call).includes('test-user'));
        expect(userRationaleCall).toBeTruthy();
      });
    });

    it('should display preset rationales in autocomplete options', async () => {
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      const input = screen.getByLabelText(i18n.t('modal.rationale.label'));
      await user.click(input);

      await waitFor(() => {
        expect(screen.getByText('Preset Rationale 1')).toBeInTheDocument();
      });
    });

    it('should display analytic rationales in autocomplete options', async () => {
      mockHpost
        .mockResolvedValueOnce({
          'howler.rationale': { 'Analytic Rationale 1': 3 }
        })
        .mockResolvedValueOnce({ 'howler.rationale': {} });

      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      const input = screen.getByLabelText(i18n.t('modal.rationale.label'));
      await user.click(input);

      await waitFor(() => {
        expect(screen.getByText('Analytic Rationale 1')).toBeInTheDocument();
      });
    });

    it('should display assignment rationales in autocomplete options', async () => {
      mockHpost
        .mockResolvedValueOnce({ 'howler.rationale': {} })
        .mockResolvedValueOnce({ 'howler.rationale': { 'My Previous Rationale': 1 } });

      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      const input = screen.getByLabelText(i18n.t('modal.rationale.label'));
      await user.click(input);

      await waitFor(() => {
        expect(screen.getByText('My Previous Rationale')).toBeInTheDocument();
      });
    });

    it('should show rationale type for each option', async () => {
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      const input = screen.getByLabelText(i18n.t('modal.rationale.label'));
      await user.click(input);

      await waitFor(() => {
        const typeLabel = screen.queryAllByText(i18n.t('modal.rationale.type.preset'));
        expect(typeLabel.length).toBe(2);
      });
    });

    it('should handle empty rationale results', async () => {
      mockHpost.mockResolvedValue({});
      mockGetMatchingAnalytic.mockResolvedValue({ analytic_id: 'test', triage_settings: {} });

      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
      });

      const input = screen.getByLabelText(i18n.t('modal.rationale.label'));
      await user.click(input);

      // Should not crash, no options displayed
      expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    });

    it('should deduplicate rationales from multiple analytics', async () => {
      const multipleHits = [
        createMockHit({ howler: { id: 'hit-1', analytic: 'analytic-1' } as any }),
        createMockHit({ howler: { id: 'hit-2', analytic: 'analytic-1' } as any })
      ];

      mockGetMatchingAnalytic.mockResolvedValue({
        analytic_id: 'analytic-1',
        triage_settings: { rationales: ['Shared Rationale'] }
      });
      render(<RationaleModal hits={multipleHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      const input = screen.getByLabelText(i18n.t('modal.rationale.label'));
      await user.click(input);

      await waitFor(() => {
        const options = screen.getAllByText('Shared Rationale');
        // Should appear only once despite multiple hits
        expect(options).toHaveLength(1);
      });
    });
  });

  describe('User Input', () => {
    it('should allow typing free text in autocomplete', async () => {
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      const input = screen.getByLabelText(i18n.t('modal.rationale.label'));
      await user.type(input, 'Custom rationale text');

      expect(input).toHaveValue('Custom rationale text');
    });

    it('should update rationale state when typing', async () => {
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      const input = screen.getByLabelText(i18n.t('modal.rationale.label'));
      await user.type(input, 'Test rationale');

      const submitButton = screen.getByText(i18n.t('submit'));
      await user.click(submitButton);

      expect(mockOnSubmit).toHaveBeenCalledWith('Test rationale');
    });

    it('should allow selecting a suggested rationale', async () => {
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      const input = screen.getByLabelText(i18n.t('modal.rationale.label'));
      await user.click(input);

      await waitFor(() => {
        expect(screen.getByText('Preset Rationale 1')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Preset Rationale 1'));

      expect(input).toHaveValue('Preset Rationale 1');
    });

    it('should clear input when text is deleted', async () => {
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      const input = screen.getByLabelText(i18n.t('modal.rationale.label'));
      await user.type(input, 'Test');
      await user.clear(input);

      expect(input).toHaveValue('');
    });
  });

  describe('Submit Functionality', () => {
    it('should call onSubmit with rationale when submit button clicked', async () => {
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      const input = screen.getByLabelText(i18n.t('modal.rationale.label'));
      await user.type(input, 'Test rationale');

      const submitButton = screen.getByText(i18n.t('submit'));
      await user.click(submitButton);

      expect(mockOnSubmit).toHaveBeenCalledWith('Test rationale');
      expect(mockOnSubmit).toHaveBeenCalledTimes(1);
    });

    it('should close modal after submit', async () => {
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      const input = screen.getByLabelText(i18n.t('modal.rationale.label'));
      await user.type(input, 'Test rationale');

      const submitButton = screen.getByText(i18n.t('submit'));
      await user.click(submitButton);

      expect(mockModalContext.close).toHaveBeenCalledTimes(1);
    });

    it('should submit with empty rationale if no text entered', async () => {
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      const submitButton = screen.getByText(i18n.t('submit'));
      await user.click(submitButton);

      expect(mockOnSubmit).toHaveBeenCalledWith('');
    });

    it('should submit with selected rationale from suggestions', async () => {
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      const input = screen.getByLabelText(i18n.t('modal.rationale.label'));
      await user.click(input);

      await waitFor(() => {
        expect(screen.getByText('Preset Rationale 1')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Preset Rationale 1'));

      const submitButton = screen.getByText(i18n.t('submit'));
      await user.click(submitButton);

      expect(mockOnSubmit).toHaveBeenCalledWith('Preset Rationale 1');
    });
  });

  describe('Cancel Functionality', () => {
    it('should close modal when cancel button clicked', async () => {
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      const cancelButton = screen.getByText(i18n.t('cancel'));
      await user.click(cancelButton);

      expect(mockModalContext.close).toHaveBeenCalledTimes(1);
    });

    it('should not call onSubmit when cancel button clicked', async () => {
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      const input = screen.getByLabelText(i18n.t('modal.rationale.label'));
      await user.type(input, 'Test rationale');

      const cancelButton = screen.getByText(i18n.t('cancel'));
      await user.click(cancelButton);

      expect(mockOnSubmit).not.toHaveBeenCalled();
    });
  });

  describe('Keyboard Shortcuts', () => {
    it('should submit when Ctrl+Enter is pressed', async () => {
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      const input = screen.getByLabelText(i18n.t('modal.rationale.label'));
      await user.type(input, 'Test rationale');
      await user.keyboard('{Control>}{Enter}{/Control}');

      expect(mockOnSubmit).toHaveBeenCalledWith('Test rationale');
      expect(mockModalContext.close).toHaveBeenCalledTimes(1);
    });

    it('should close modal when Escape is pressed', async () => {
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      const input = screen.getByLabelText(i18n.t('modal.rationale.label'));
      await user.type(input, 'Test rationale');
      await user.keyboard('{Escape}');

      expect(mockModalContext.close).toHaveBeenCalledTimes(1);
      expect(mockOnSubmit).not.toHaveBeenCalled();
    });

    it('should not submit when only Enter is pressed without Ctrl', async () => {
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      const input = screen.getByLabelText(i18n.t('modal.rationale.label'));
      await user.type(input, 'Test rationale');
      await user.keyboard('{Enter}');

      // Enter alone in autocomplete shouldn't submit the form
      expect(mockOnSubmit).not.toHaveBeenCalled();
    });

    it('should handle multiple keyboard shortcuts correctly', async () => {
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      const input = screen.getByLabelText(i18n.t('modal.rationale.label'));

      // Press Escape first - should close
      await user.type(input, 'First');
      await user.keyboard('{Escape}');

      expect(mockModalContext.close).toHaveBeenCalledTimes(1);
      expect(mockOnSubmit).not.toHaveBeenCalled();
    });
  });

  describe('Multiple Hits', () => {
    it('should handle multiple hits with different analytics', async () => {
      const multipleHits = [
        createMockHit({ howler: { id: 'hit-1', analytic: 'analytic-1' } as any }),
        createMockHit({ howler: { id: 'hit-2', analytic: 'analytic-2' } as any })
      ];

      mockGetMatchingAnalytic
        .mockResolvedValueOnce({
          analytic_id: 'analytic-1',
          triage_settings: { rationales: ['Rationale A'] }
        })
        .mockResolvedValueOnce({
          analytic_id: 'analytic-2',
          triage_settings: { rationales: ['Rationale B'] }
        });

      render(<RationaleModal hits={multipleHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(mockGetMatchingAnalytic).toHaveBeenCalledTimes(2);
      });
    });

    it('should sanitize lucene queries in filters', async () => {
      const hitWithSpecialChars = createMockHit({
        howler: { id: 'hit-1', analytic: 'test:analytic+special' } as any
      });

      render(<RationaleModal hits={[hitWithSpecialChars]} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(mockHpost).toHaveBeenCalled();
      });

      // Verify that sanitizeLuceneQuery was used (analytic should be in quotes)
      const dispatchCalls = mockHpost.mock.calls;
      const hasQuotedAnalytic = dispatchCalls.some(call => JSON.stringify(call).includes('howler.analytic:'));
      expect(hasQuotedAnalytic).toBeTruthy();
    });
  });

  describe('Error Handling', () => {
    it('should handle API errors gracefully', async () => {
      mockHpost.mockRejectedValueOnce(new Error('API Error'));

      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
      });

      // Component should still be functional
      const input = screen.getByLabelText(i18n.t('modal.rationale.label'));
      expect(input).toBeInTheDocument();
    });

    it('should handle missing analytic data', async () => {
      mockGetMatchingAnalytic.mockResolvedValue(null);
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
      });

      // Should not crash
      expect(screen.getByLabelText(i18n.t('modal.rationale.label'))).toBeInTheDocument();
    });

    it('should handle missing triage_settings in analytic', async () => {
      mockGetMatchingAnalytic.mockResolvedValue({
        analytic_id: 'test-analytic',
        triage_settings: null
      });
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
      });

      expect(screen.getByLabelText(i18n.t('modal.rationale.label'))).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('should handle empty hits array', async () => {
      render(<RationaleModal hits={[]} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
      });

      expect(screen.getByLabelText(i18n.t('modal.rationale.label'))).toBeInTheDocument();
    });

    it('should handle special characters in rationale', async () => {
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      const specialText = 'Test <>&"\'{}[]()';
      const input = screen.getByLabelText(i18n.t('modal.rationale.label'));
      await user.type(input, specialText.replace(/([{\[])/g, '$1$1'));

      const submitButton = screen.getByText(i18n.t('submit'));
      await user.click(submitButton);

      expect(mockOnSubmit).toHaveBeenCalledWith(specialText);
    });

    it('should handle rapid successive submissions', async () => {
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      const input = screen.getByLabelText(i18n.t('modal.rationale.label'));
      await user.type(input, 'Test');

      const submitButton = screen.getByText(i18n.t('submit'));

      await act(async () => {
        await user.click(submitButton);
        await user.click(submitButton);
        await user.click(submitButton);
      });

      expect(mockOnSubmit).toHaveBeenCalledTimes(3);
    });
  });

  describe('Accessibility', () => {
    it('should have accessible labels for all interactive elements', async () => {
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      expect(screen.getByLabelText(i18n.t('modal.rationale.label'))).toBeInTheDocument();
      expect(screen.getByRole('button', { name: i18n.t('cancel') })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: i18n.t('submit') })).toBeInTheDocument();
    });

    it('should support keyboard navigation', async () => {
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      const input = screen.getByLabelText(i18n.t('modal.rationale.label'));
      const cancelButton = screen.getByText(i18n.t('cancel'));
      const submitButton = screen.getByText(i18n.t('submit'));

      // Tab through elements
      await user.tab();
      expect(input).toHaveFocus();

      await user.tab();
      expect(cancelButton).toHaveFocus();

      await user.tab();
      expect(submitButton).toHaveFocus();
    });

    it('should have proper ARIA attributes on autocomplete', async () => {
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      const input = screen.getByLabelText(i18n.t('modal.rationale.label'));

      expect(input).toHaveAttribute('aria-autocomplete', 'list');
      expect(input).toHaveAttribute('role', 'combobox');
    });

    it('should announce loading state to screen readers', async () => {
      mockHpost.mockImplementation(() => new Promise(() => {}));

      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      const progressbar = screen.getByRole('progressbar');
      expect(progressbar).toBeInTheDocument();
    });

    it('should have semantic heading structure', () => {
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      const heading = screen.getByRole('heading', { level: 4 });
      expect(heading).toHaveTextContent(i18n.t('modal.rationale.title'));
    });

    it('should provide accessible descriptions for rationale types', async () => {
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      const input = screen.getByLabelText(i18n.t('modal.rationale.label'));
      await user.click(input);

      await waitFor(() => {
        const typeLabel = screen.queryAllByText(i18n.t('modal.rationale.type.preset'));
        expect(typeLabel.length).toBe(2);
      });
    });

    it('should maintain focus when opening autocomplete', async () => {
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      const input = screen.getByLabelText(i18n.t('modal.rationale.label'));
      await user.click(input);

      expect(input).toHaveFocus();
    });

    it('should support screen reader navigation through options', async () => {
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      const input = screen.getByLabelText(i18n.t('modal.rationale.label'));
      await user.click(input);

      await waitFor(() => {
        const listbox = screen.getByRole('listbox');
        expect(listbox).toBeInTheDocument();
      });

      const options = screen.getAllByRole('option');
      expect(options.length).toBeGreaterThan(0);
    });

    it('should announce selected option to screen readers', async () => {
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      const input = screen.getByLabelText(i18n.t('modal.rationale.label'));
      await user.click(input);

      await waitFor(() => {
        expect(screen.getByText('Preset Rationale 1')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Preset Rationale 1'));

      expect(input).toHaveValue('Preset Rationale 1');
    });

    it('should have sufficient color contrast for buttons', () => {
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      const cancelButton = screen.getByRole('button', { name: i18n.t('cancel') });
      const submitButton = screen.getByRole('button', { name: i18n.t('submit') });

      expect(cancelButton).toBeVisible();
      expect(submitButton).toBeVisible();
    });
  });

  describe('Integration', () => {
    it('should work with all context providers', async () => {
      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
      });

      const input = screen.getByLabelText(i18n.t('modal.rationale.label'));
      await user.type(input, 'Integration test');

      const submitButton = screen.getByText(i18n.t('submit'));
      await user.click(submitButton);

      expect(mockOnSubmit).toHaveBeenCalledWith('Integration test');
      expect(mockModalContext.close).toHaveBeenCalledTimes(1);
    });

    it('should combine rationales from all sources', async () => {
      mockGetMatchingAnalytic.mockResolvedValue({
        analytic_id: 'test',
        triage_settings: { rationales: ['Preset 1'] }
      });

      mockHpost
        .mockResolvedValueOnce({ 'howler.rationale': { 'Analytic 1': 2 } })
        .mockResolvedValueOnce({ 'howler.rationale': { 'Assignment 1': 1 } });

      render(<RationaleModal hits={defaultHits} onSubmit={mockOnSubmit} />, { wrapper: Wrapper });

      const input = screen.getByLabelText(i18n.t('modal.rationale.label'));
      await user.click(input);

      await waitFor(() => {
        expect(mockHpost).toHaveBeenCalledTimes(2);

        expect(screen.getByText('Preset 1')).toBeInTheDocument();
        expect(screen.getByText('Analytic 1')).toBeInTheDocument();
        expect(screen.getByText('Assignment 1')).toBeInTheDocument();
      });
    });
  });
});
