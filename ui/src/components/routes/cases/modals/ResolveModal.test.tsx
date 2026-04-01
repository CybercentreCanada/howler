/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent, { type UserEvent } from '@testing-library/user-event';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import { ModalContext } from 'components/app/providers/ModalProvider';
import { RecordContext } from 'components/app/providers/RecordProvider';
import i18n from 'i18n';
import type { Hit } from 'models/entities/generated/Hit';
import { type FC, type PropsWithChildren } from 'react';
import { I18nextProvider } from 'react-i18next';
import { MemoryRouter } from 'react-router-dom';
import { createMockCase, createMockHit } from 'tests/utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ResolveModal from './ResolveModal';

// ---------------------------------------------------------------------------
// Hoisted mocks
// ---------------------------------------------------------------------------

const mockAssess = vi.hoisted(() => vi.fn().mockResolvedValue(undefined));
const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockUpdateCase = vi.hoisted(() => vi.fn().mockResolvedValue(undefined));
const mockClose = vi.hoisted(() => vi.fn());
const mockLoadRecords = vi.hoisted(() => vi.fn());

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('components/hooks/useHitActions', () => ({
  default: () => ({ assess: mockAssess })
}));

vi.mock('../hooks/useCase', () => ({
  default: () => ({ update: mockUpdateCase })
}));

vi.mock('components/elements/hit/elements/AnalyticLink', () => ({
  default: ({ hit }: any) => <span data-testid={`analytic-${hit.howler.id}`}>{hit.howler.analytic}</span>
}));

vi.mock('components/elements/hit/elements/EscalationChip', () => ({
  default: () => null
}));

vi.mock('components/elements/hit/HitCard', () => ({
  default: ({ id }: any) => <div>{`HitCard:${id}`}</div>
}));

vi.mock('api', () => ({
  default: {
    search: {
      hit: {
        post: (params: any) => params
      }
    }
  }
}));

vi.mock('commons/components/app/hooks/useAppUser', () => ({
  useAppUser: () => ({ user: { username: 'test-user' } })
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockConfig = {
  lookups: {
    'howler.assessment': ['legitimate', 'false_positive', 'non_issue']
  }
} as any;

const makeUnresolvedHit = (id: string): Hit =>
  createMockHit({ howler: { id, status: 'open', analytic: `analytic-${id}` } as any });

const makeResolvedHit = (id: string): Hit =>
  createMockHit({ howler: { id, status: 'resolved', analytic: `analytic-${id}` } as any });

const HIT_1 = makeUnresolvedHit('hit-1');
const HIT_2 = makeUnresolvedHit('hit-2');
const HIT_RESOLVED = makeResolvedHit('hit-resolved');

const caseWithHits = (hitIds: string[]) =>
  createMockCase({
    case_id: 'case-1',
    items: hitIds.map(id => ({ type: 'hit', value: id }) as any)
  });

// ---------------------------------------------------------------------------
// Wrapper factory
// ---------------------------------------------------------------------------

const createWrapper = (records: Record<string, Hit> = {}): FC<PropsWithChildren> => {
  const Wrapper: FC<PropsWithChildren> = ({ children }) => (
    <I18nextProvider i18n={i18n as any}>
      <ModalContext.Provider value={{ close: mockClose, open: vi.fn(), setContent: vi.fn() } as any}>
        <ApiConfigContext.Provider value={{ config: mockConfig, setConfig: vi.fn() } as any}>
          <RecordContext.Provider value={{ records, loadRecords: mockLoadRecords } as any}>
            <MemoryRouter>{children}</MemoryRouter>
          </RecordContext.Provider>
        </ApiConfigContext.Provider>
      </ModalContext.Provider>
    </I18nextProvider>
  );
  return Wrapper;
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Clicks a MUI Checkbox — operates on the ButtonBase parent of the hidden input
 * so that user-event's special checkbox-input code path is bypassed and the
 * component's own onClick handler fires correctly.
 */
const clickCheckbox = (checkbox: HTMLElement) => {
  fireEvent.click(checkbox.parentElement!);
};

/** Fills in assessment and rationale so the confirm button becomes enabled. */
const fillForm = async (user: UserEvent, assessment = 'legitimate', rationale = 'Test rationale') => {
  const rationaleInput = screen.getByPlaceholderText(i18n.t('modal.rationale.label'));
  await user.clear(rationaleInput);
  await user.type(rationaleInput, rationale);

  // Typing into the combobox triggers MUI Autocomplete's onInputChange which
  // opens the listbox — a plain click does not reliably open it in jsdom.
  // The combobox has no accessible label (only a placeholder), so we query by
  // role alone — there is exactly one combobox in the modal.
  const assessmentInput = screen.getByRole('combobox');
  await user.type(assessmentInput, assessment.slice(0, 3));

  const option = await screen.findByRole('option', { name: assessment });
  await user.click(option);
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ResolveModal', () => {
  let user: UserEvent;
  let mockOnConfirm: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    user = userEvent.setup();
    mockOnConfirm = vi.fn();
    vi.clearAllMocks();
    // Default: resolve immediately with an empty items list
    mockDispatchApi.mockResolvedValue({ items: [] });
  });

  // -------------------------------------------------------------------------
  // Initial render
  // -------------------------------------------------------------------------

  describe('initial render', () => {
    it('shows the modal title', () => {
      render(<ResolveModal case={caseWithHits([])} onConfirm={mockOnConfirm} />, {
        wrapper: createWrapper()
      });
      expect(screen.getByText(i18n.t('modal.cases.resolve'))).toBeInTheDocument();
    });

    it('shows the modal description', () => {
      render(<ResolveModal case={caseWithHits([])} onConfirm={mockOnConfirm} />, {
        wrapper: createWrapper()
      });
      expect(screen.getByText(i18n.t('modal.cases.resolve.description'))).toBeInTheDocument();
    });

    it('renders a cancel button', () => {
      render(<ResolveModal case={caseWithHits([])} onConfirm={mockOnConfirm} />, {
        wrapper: createWrapper()
      });
      expect(screen.getByRole('button', { name: i18n.t('cancel') })).toBeInTheDocument();
    });

    it('renders a confirm button', () => {
      render(<ResolveModal case={caseWithHits([])} onConfirm={mockOnConfirm} />, {
        wrapper: createWrapper()
      });
      expect(screen.getByRole('button', { name: i18n.t('confirm') })).toBeInTheDocument();
    });

    it('shows the "Resolved Alerts" accordion', () => {
      render(<ResolveModal case={caseWithHits([])} onConfirm={mockOnConfirm} />, {
        wrapper: createWrapper()
      });
      expect(screen.getByText(i18n.t('modal.cases.alerts.resolved'))).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Loading state
  // -------------------------------------------------------------------------

  describe('loading state', () => {
    it('shows a LinearProgress while the API call is pending', () => {
      mockDispatchApi.mockReturnValue(new Promise(() => {})); // never resolves

      const { container } = render(<ResolveModal case={caseWithHits(['hit-1'])} onConfirm={mockOnConfirm} />, {
        wrapper: createWrapper()
      });

      const progress = container.querySelector('.MuiLinearProgress-root');
      expect(progress).toBeInTheDocument();
      // opacity is 1 while loading
      expect(progress).toHaveStyle({ opacity: '1' });
    });

    it('disables the confirm button while loading', () => {
      mockDispatchApi.mockReturnValue(new Promise(() => {}));

      render(<ResolveModal case={caseWithHits(['hit-1'])} onConfirm={mockOnConfirm} />, {
        wrapper: createWrapper()
      });

      expect(screen.getByRole('button', { name: i18n.t('confirm') })).toBeDisabled();
    });

    it('shows a CircularProgress inside the confirm button while loading', () => {
      mockDispatchApi.mockReturnValue(new Promise(() => {}));

      const { container } = render(<ResolveModal case={caseWithHits(['hit-1'])} onConfirm={mockOnConfirm} />, {
        wrapper: createWrapper()
      });

      expect(container.querySelector('.MuiCircularProgress-root')).toBeInTheDocument();
    });

    it('fades out the LinearProgress after loading completes', async () => {
      const { container } = render(<ResolveModal case={caseWithHits([])} onConfirm={mockOnConfirm} />, {
        wrapper: createWrapper()
      });

      await waitFor(() => {
        const progress = container.querySelector('.MuiLinearProgress-root');
        expect(progress).toHaveStyle({ opacity: '0' });
      });
    });
  });

  // -------------------------------------------------------------------------
  // Hit rendering
  // -------------------------------------------------------------------------

  describe('hit rendering', () => {
    it('renders unresolved hits with checkboxes after loading', async () => {
      render(<ResolveModal case={caseWithHits(['hit-1', 'hit-2'])} onConfirm={mockOnConfirm} />, {
        wrapper: createWrapper({ 'hit-1': HIT_1, 'hit-2': HIT_2 })
      });

      await waitFor(() => {
        expect(screen.getAllByRole('checkbox')).toHaveLength(2);
      });
    });

    it('does not show a checkbox for resolved hits', async () => {
      render(<ResolveModal case={caseWithHits(['hit-1', 'hit-resolved'])} onConfirm={mockOnConfirm} />, {
        wrapper: createWrapper({ 'hit-1': HIT_1, 'hit-resolved': HIT_RESOLVED })
      });

      await waitFor(() => {
        // only the single unresolved hit gets a checkbox
        expect(screen.getAllByRole('checkbox')).toHaveLength(1);
      });
    });

    it('calls loadRecords with the API search results', async () => {
      const items = [HIT_1];
      mockDispatchApi.mockResolvedValueOnce({ items });

      render(<ResolveModal case={caseWithHits(['hit-1'])} onConfirm={mockOnConfirm} />, {
        wrapper: createWrapper()
      });

      await waitFor(() => {
        expect(mockLoadRecords).toHaveBeenCalledWith(items);
      });
    });
  });

  // -------------------------------------------------------------------------
  // Confirm button disabled states
  // -------------------------------------------------------------------------

  describe('confirm button enablement', () => {
    it('is disabled when no hits are selected', async () => {
      render(<ResolveModal case={caseWithHits(['hit-1'])} onConfirm={mockOnConfirm} />, {
        wrapper: createWrapper({ 'hit-1': HIT_1 })
      });

      // Wait for the hit to load (checkbox appears) but don't select it
      await screen.findAllByRole('checkbox');

      await fillForm(user);

      // No hit selected → selectedHitIds.size === 0 → button still disabled
      expect(screen.getByRole('button', { name: i18n.t('confirm') })).toBeDisabled();
    });

    it('is disabled when assessment is missing', async () => {
      render(<ResolveModal case={caseWithHits(['hit-1'])} onConfirm={mockOnConfirm} />, {
        wrapper: createWrapper({ 'hit-1': HIT_1 })
      });

      const [checkbox] = await screen.findAllByRole('checkbox');
      clickCheckbox(checkbox);
      await waitFor(() => expect(checkbox).toBeChecked());

      const rationaleInput = screen.getByPlaceholderText(i18n.t('modal.rationale.label'));
      await user.type(rationaleInput, 'some reason');

      // no assessment chosen → still disabled
      expect(screen.getByRole('button', { name: i18n.t('confirm') })).toBeDisabled();
    });

    it('is disabled when rationale is empty', async () => {
      render(<ResolveModal case={caseWithHits(['hit-1'])} onConfirm={mockOnConfirm} />, {
        wrapper: createWrapper({ 'hit-1': HIT_1 })
      });

      const [checkbox] = await screen.findAllByRole('checkbox');
      clickCheckbox(checkbox);
      await waitFor(() => expect(checkbox).toBeChecked());

      // fill only assessment, no rationale
      const assessmentInput = screen.getByRole('combobox');
      await user.type(assessmentInput, 'leg');
      const option = await screen.findByRole('option', { name: 'legitimate' });
      await user.click(option);

      expect(screen.getByRole('button', { name: i18n.t('confirm') })).toBeDisabled();
    });

    it('is enabled when a hit is selected + assessment + rationale are provided', async () => {
      render(<ResolveModal case={caseWithHits(['hit-1'])} onConfirm={mockOnConfirm} />, {
        wrapper: createWrapper({ 'hit-1': HIT_1 })
      });

      const [checkbox] = await screen.findAllByRole('checkbox');
      clickCheckbox(checkbox);
      await waitFor(() => expect(checkbox).toBeChecked());

      await fillForm(user);

      expect(screen.getByRole('button', { name: i18n.t('confirm') })).toBeEnabled();
    });
  });

  // -------------------------------------------------------------------------
  // Checkbox / selection toggling
  // -------------------------------------------------------------------------

  describe('hit selection', () => {
    it('checks a hit when its checkbox is clicked', async () => {
      render(<ResolveModal case={caseWithHits(['hit-1'])} onConfirm={mockOnConfirm} />, {
        wrapper: createWrapper({ 'hit-1': HIT_1 })
      });

      const [checkbox] = await screen.findAllByRole('checkbox');
      expect(checkbox).not.toBeChecked();

      clickCheckbox(checkbox);

      await waitFor(() => expect(checkbox).toBeChecked());
    });

    it('unchecks a hit when its checkbox is clicked a second time', async () => {
      render(<ResolveModal case={caseWithHits(['hit-1'])} onConfirm={mockOnConfirm} />, {
        wrapper: createWrapper({ 'hit-1': HIT_1 })
      });

      const [checkbox] = await screen.findAllByRole('checkbox');

      clickCheckbox(checkbox);
      await waitFor(() => expect(checkbox).toBeChecked());

      clickCheckbox(checkbox);
      await waitFor(() => expect(checkbox).not.toBeChecked());
    });

    it('tracks each hit independently when there are multiple', async () => {
      render(<ResolveModal case={caseWithHits(['hit-1', 'hit-2'])} onConfirm={mockOnConfirm} />, {
        wrapper: createWrapper({ 'hit-1': HIT_1, 'hit-2': HIT_2 })
      });

      const checkboxes = await screen.findAllByRole('checkbox');
      expect(checkboxes).toHaveLength(2);

      clickCheckbox(checkboxes[0]);

      await waitFor(() => {
        expect(checkboxes[0]).toBeChecked();
        expect(checkboxes[1]).not.toBeChecked();
      });
    });
  });

  // -------------------------------------------------------------------------
  // Confirm action
  // -------------------------------------------------------------------------

  describe('confirm action', () => {
    it('calls assess with the chosen assessment, true, and rationale', async () => {
      render(<ResolveModal case={caseWithHits(['hit-1'])} onConfirm={mockOnConfirm} />, {
        wrapper: createWrapper({ 'hit-1': HIT_1 })
      });

      const [checkbox] = await screen.findAllByRole('checkbox');
      clickCheckbox(checkbox);
      await waitFor(() => expect(checkbox).toBeChecked());
      await fillForm(user, 'legitimate', 'My rationale');

      await user.click(screen.getByRole('button', { name: i18n.t('confirm') }));

      await waitFor(() => {
        expect(mockAssess).toHaveBeenCalledWith('legitimate', true, 'My rationale');
      });
    });

    it('clears the selection after confirm completes', async () => {
      render(<ResolveModal case={caseWithHits(['hit-1'])} onConfirm={mockOnConfirm} />, {
        wrapper: createWrapper({ 'hit-1': HIT_1 })
      });

      const [checkbox] = await screen.findAllByRole('checkbox');
      clickCheckbox(checkbox);
      await waitFor(() => expect(checkbox).toBeChecked());

      await fillForm(user);
      await user.click(screen.getByRole('button', { name: i18n.t('confirm') }));

      await waitFor(() => {
        expect(checkbox).not.toBeChecked();
      });
    });
  });

  // -------------------------------------------------------------------------
  // Cancel button
  // -------------------------------------------------------------------------

  describe('cancel button', () => {
    it('calls close() when cancel is clicked', async () => {
      // Use a case with an unresolved hit so the auto-resolve effect does not fire
      // and call close() before we even click cancel.
      render(<ResolveModal case={caseWithHits(['hit-1'])} onConfirm={mockOnConfirm} />, {
        wrapper: createWrapper({ 'hit-1': HIT_1 })
      });

      // Wait for loading to finish so no unexpected state transitions happen mid-click
      await screen.findAllByRole('checkbox');

      await user.click(screen.getByRole('button', { name: i18n.t('cancel') }));

      expect(mockClose).toHaveBeenCalledTimes(1);
    });
  });

  // -------------------------------------------------------------------------
  // Auto-resolve when all hits are already resolved
  // -------------------------------------------------------------------------

  describe('auto-resolve', () => {
    it('calls updateCase, onConfirm, and close when no unresolved hits remain after loading', async () => {
      // All hits in the case are already resolved
      render(<ResolveModal case={caseWithHits(['hit-resolved'])} onConfirm={mockOnConfirm} />, {
        wrapper: createWrapper({ 'hit-resolved': HIT_RESOLVED })
      });

      // dispatchApi resolves → loading becomes false → unresolvedHits.length === 0 → auto-close
      await waitFor(() => {
        expect(mockUpdateCase).toHaveBeenCalledWith({ status: 'resolved' });
      });

      await waitFor(() => {
        expect(mockOnConfirm).toHaveBeenCalledTimes(1);
        expect(mockClose).toHaveBeenCalledTimes(1);
      });
    });

    it('does NOT auto-resolve while hits are still unresolved', async () => {
      render(<ResolveModal case={caseWithHits(['hit-1'])} onConfirm={mockOnConfirm} />, {
        wrapper: createWrapper({ 'hit-1': HIT_1 })
      });

      // Wait for loading to complete: the unresolved hit's checkbox appears once the
      // dispatchApi call settles and the LinearProgress opacity drops to 0.
      await screen.findAllByRole('checkbox');

      // Should not have auto-resolved
      expect(mockUpdateCase).not.toHaveBeenCalled();
      expect(mockClose).not.toHaveBeenCalled();
    });
  });
});
