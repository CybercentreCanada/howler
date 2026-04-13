/// <reference types="vitest" />
import { render, screen, waitFor } from '@testing-library/react';
import userEvent, { type UserEvent } from '@testing-library/user-event';
import { ModalContext } from 'components/app/providers/ModalProvider';
import i18n from 'i18n';
import type { Case } from 'models/entities/generated/Case';
import type { Hit } from 'models/entities/generated/Hit';
import type { Observable } from 'models/entities/generated/Observable';
import type { PropsWithChildren } from 'react';
import { I18nextProvider } from 'react-i18next';
import { createMockCase, createMockHit, createMockObservable } from 'tests/utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AddToCaseModal from './AddToCaseModal';

// ---------------------------------------------------------------------------
// Hoisted mocks
// ---------------------------------------------------------------------------

const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockClose = vi.hoisted(() => vi.fn());

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('components/elements/hit/elements/EscalationChip', () => ({
  default: () => null
}));

vi.mock('components/elements/case/CaseCard', () => ({
  default: ({ case: c }: { case: Case }) => <div>{c.title ?? c.case_id}</div>
}));

vi.mock('api', () => ({
  default: {
    search: {
      case: { post: vi.fn().mockReturnValue('search-case-request') }
    },
    v2: {
      case: {
        items: { post: vi.fn().mockReturnValue('items-post-request') }
      }
    }
  }
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const CASE_A: Case = createMockCase({ case_id: 'case-a', title: 'Case Alpha', items: [] });
const CASE_B: Case = createMockCase({
  case_id: 'case-b',
  title: 'Case Beta',
  items: [{ path: 'folder/subfolder/item', type: 'hit', value: 'x', visible: true }]
});

const MOCK_HIT_1: Hit = createMockHit({
  howler: { id: 'hit-001', analytic: 'AnalyticOne', status: 'open' } as any
});

const MOCK_HIT_2: Hit = createMockHit({
  howler: { id: 'hit-002', analytic: 'AnalyticTwo', status: 'open' } as any
});

const MOCK_OBSERVABLE: Observable = createMockObservable({
  howler: { id: 'obs-001' } as any
});

// ---------------------------------------------------------------------------
// Wrapper
// ---------------------------------------------------------------------------

const Wrapper = ({ children }: PropsWithChildren) => (
  <I18nextProvider i18n={i18n as any}>
    <ModalContext.Provider value={{ close: mockClose, open: vi.fn(), setContent: vi.fn() } as any}>
      {children}
    </ModalContext.Provider>
  </I18nextProvider>
);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const renderModal = (records: (Hit | Observable)[]) =>
  render(<AddToCaseModal records={records} />, { wrapper: Wrapper });

const selectCase = async (user: UserEvent, caseTitle: string) => {
  const combobox = screen.getAllByRole('combobox')[0];
  await user.click(combobox);
  const option = await screen.findByRole('option', { name: caseTitle });
  await user.click(option);
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('AddToCaseModal', () => {
  let user: UserEvent;

  beforeEach(() => {
    user = userEvent.setup();
    vi.clearAllMocks();
    mockDispatchApi.mockResolvedValue({ items: [CASE_A, CASE_B] });
  });

  // -------------------------------------------------------------------------
  // Initial render
  // -------------------------------------------------------------------------

  describe('initial render', () => {
    it('shows the modal title', async () => {
      renderModal([MOCK_HIT_1]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      expect(screen.getByText(i18n.t('modal.cases.add_to_case'))).toBeInTheDocument();
    });

    it('renders cancel and confirm buttons', async () => {
      renderModal([MOCK_HIT_1]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      expect(screen.getByRole('button', { name: i18n.t('cancel') })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: i18n.t('confirm') })).toBeInTheDocument();
    });

    it('confirm is disabled before a case is selected', async () => {
      renderModal([MOCK_HIT_1]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      expect(screen.getByRole('button', { name: i18n.t('confirm') })).toBeDisabled();
    });

    it('fetches cases on mount', async () => {
      const api = (await import('api')).default;
      renderModal([MOCK_HIT_1]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      expect(api.search.case.post).toHaveBeenCalledWith({ query: 'case_id:*', rows: 100 });
    });
  });

  // -------------------------------------------------------------------------
  // Default item titles
  // -------------------------------------------------------------------------

  describe('default item titles', () => {
    it('pre-populates title for a hit with analytic and id', async () => {
      renderModal([MOCK_HIT_1]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      await selectCase(user, 'Case Alpha');

      const titleInput = screen.getByPlaceholderText(i18n.t('modal.cases.add_to_case.title'));
      expect(titleInput).toHaveValue(`${MOCK_HIT_1.howler.analytic} (${MOCK_HIT_1.howler.id})`);
    });

    it('pre-populates title for an observable with Observable and id', async () => {
      renderModal([MOCK_OBSERVABLE]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      await selectCase(user, 'Case Alpha');

      const titleInput = screen.getByPlaceholderText(i18n.t('modal.cases.add_to_case.title'));
      expect(titleInput).toHaveValue(`Observable (${MOCK_OBSERVABLE.howler.id})`);
    });

    it('title input is editable', async () => {
      renderModal([MOCK_HIT_1]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      await selectCase(user, 'Case Alpha');

      const titleInput = screen.getByPlaceholderText(i18n.t('modal.cases.add_to_case.title'));
      await user.clear(titleInput);
      await user.type(titleInput, 'Custom Title');
      expect(titleInput).toHaveValue('Custom Title');
    });
  });

  // -------------------------------------------------------------------------
  // Multiple records
  // -------------------------------------------------------------------------

  describe('multiple records', () => {
    it('renders a row for each hit record', async () => {
      renderModal([MOCK_HIT_1, MOCK_HIT_2]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      await selectCase(user, 'Case Alpha');

      expect(screen.getByText(MOCK_HIT_1.howler.analytic)).toBeInTheDocument();
      expect(screen.getByText(MOCK_HIT_2.howler.analytic)).toBeInTheDocument();
    });

    it('renders independent title inputs for each record', async () => {
      renderModal([MOCK_HIT_1, MOCK_HIT_2]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      await selectCase(user, 'Case Alpha');

      const titleInputs = screen.getAllByPlaceholderText(i18n.t('modal.cases.add_to_case.title'));
      expect(titleInputs).toHaveLength(2);
      expect(titleInputs[0]).toHaveValue(`${MOCK_HIT_1.howler.analytic} (${MOCK_HIT_1.howler.id})`);
      expect(titleInputs[1]).toHaveValue(`${MOCK_HIT_2.howler.analytic} (${MOCK_HIT_2.howler.id})`);
    });

    it('editing one record title does not affect the other', async () => {
      renderModal([MOCK_HIT_1, MOCK_HIT_2]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      await selectCase(user, 'Case Alpha');

      const titleInputs = screen.getAllByPlaceholderText(i18n.t('modal.cases.add_to_case.title'));
      await user.clear(titleInputs[0]);
      await user.type(titleInputs[0], 'Edited');

      expect(titleInputs[0]).toHaveValue('Edited');
      expect(titleInputs[1]).toHaveValue(`${MOCK_HIT_2.howler.analytic} (${MOCK_HIT_2.howler.id})`);
    });

    it('mixed hit and observable records each get correct default titles', async () => {
      renderModal([MOCK_HIT_1, MOCK_OBSERVABLE]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      await selectCase(user, 'Case Alpha');

      const titleInputs = screen.getAllByPlaceholderText(i18n.t('modal.cases.add_to_case.title'));
      expect(titleInputs[0]).toHaveValue(`${MOCK_HIT_1.howler.analytic} (${MOCK_HIT_1.howler.id})`);
      expect(titleInputs[1]).toHaveValue(`Observable (${MOCK_OBSERVABLE.howler.id})`);
    });
  });

  // -------------------------------------------------------------------------
  // Folder path options
  // -------------------------------------------------------------------------

  describe('folder path options', () => {
    it('shows folder options derived from the selected case items', async () => {
      renderModal([MOCK_HIT_1]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      await selectCase(user, 'Case Beta');

      const pathInputs = screen.getAllByPlaceholderText(i18n.t('modal.cases.add_to_case.select_path'));
      await user.click(pathInputs[0]);
      expect(await screen.findByRole('option', { name: 'folder' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'folder/subfolder' })).toBeInTheDocument();
    });

    it('shows the full path preview when a path and title are set', async () => {
      renderModal([MOCK_HIT_1]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      await selectCase(user, 'Case Beta');

      const pathInput = screen.getAllByPlaceholderText(i18n.t('modal.cases.add_to_case.select_path'))[0];
      await user.type(pathInput, 'myfolder');

      const expectedFull = `myfolder/${MOCK_HIT_1.howler.analytic} (${MOCK_HIT_1.howler.id})`;
      await waitFor(() => {
        expect(
          screen.getByText(i18n.t('modal.cases.add_to_case.full_path', { path: expectedFull }))
        ).toBeInTheDocument();
      });
    });
  });

  // -------------------------------------------------------------------------
  // Validation
  // -------------------------------------------------------------------------

  describe('validation', () => {
    it('enables confirm after a case is selected and titles are filled', async () => {
      renderModal([MOCK_HIT_1]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      await selectCase(user, 'Case Alpha');
      expect(screen.getByRole('button', { name: i18n.t('confirm') })).toBeEnabled();
    });

    it('disables confirm when an item title is cleared', async () => {
      renderModal([MOCK_HIT_1]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      await selectCase(user, 'Case Alpha');

      const titleInput = screen.getByPlaceholderText(i18n.t('modal.cases.add_to_case.title'));
      await user.clear(titleInput);

      expect(screen.getByRole('button', { name: i18n.t('confirm') })).toBeDisabled();
    });
  });

  // -------------------------------------------------------------------------
  // Cancel
  // -------------------------------------------------------------------------

  describe('cancel button', () => {
    it('calls close when cancel is clicked', async () => {
      renderModal([MOCK_HIT_1]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      await user.click(screen.getByRole('button', { name: i18n.t('cancel') }));
      expect(mockClose).toHaveBeenCalledTimes(1);
    });
  });

  // -------------------------------------------------------------------------
  // Submission — single record
  // -------------------------------------------------------------------------

  describe('form submission — single record', () => {
    beforeEach(() => {
      mockDispatchApi
        .mockResolvedValueOnce({ items: [CASE_A, CASE_B] }) // case list fetch
        .mockResolvedValue(undefined); // items.post
    });

    it('calls items.post with the correct arguments and closes', async () => {
      const api = (await import('api')).default;
      renderModal([MOCK_HIT_1]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      await selectCase(user, 'Case Alpha');

      await user.click(screen.getByRole('button', { name: i18n.t('confirm') }));
      await waitFor(() => expect(mockClose).toHaveBeenCalled());

      expect(api.v2.case.items.post).toHaveBeenCalledWith(
        'case-a',
        expect.objectContaining({
          path: `${MOCK_HIT_1.howler.analytic} (${MOCK_HIT_1.howler.id})`,
          value: MOCK_HIT_1.howler.id,
          type: 'hit'
        })
      );
    });

    it('combines folder path and title in the submitted path', async () => {
      const api = (await import('api')).default;
      renderModal([MOCK_HIT_1]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      await selectCase(user, 'Case Alpha');

      const pathInput = screen.getByPlaceholderText(i18n.t('modal.cases.add_to_case.select_path'));
      await user.type(pathInput, 'investigations');

      await user.click(screen.getByRole('button', { name: i18n.t('confirm') }));
      await waitFor(() => expect(mockClose).toHaveBeenCalled());

      expect(api.v2.case.items.post).toHaveBeenCalledWith(
        'case-a',
        expect.objectContaining({
          path: `investigations/${MOCK_HIT_1.howler.analytic} (${MOCK_HIT_1.howler.id})`
        })
      );
    });

    it('uses observable __index for observable records', async () => {
      const api = (await import('api')).default;
      renderModal([MOCK_OBSERVABLE]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      await selectCase(user, 'Case Alpha');

      await user.click(screen.getByRole('button', { name: i18n.t('confirm') }));
      await waitFor(() => expect(mockClose).toHaveBeenCalled());

      expect(api.v2.case.items.post).toHaveBeenCalledWith('case-a', expect.objectContaining({ type: 'observable' }));
    });
  });

  // -------------------------------------------------------------------------
  // Submission — multiple records
  // -------------------------------------------------------------------------

  describe('form submission — multiple records', () => {
    beforeEach(() => {
      mockDispatchApi.mockResolvedValueOnce({ items: [CASE_A, CASE_B] }).mockResolvedValue(undefined);
    });

    it('calls items.post once per record', async () => {
      const api = (await import('api')).default;
      renderModal([MOCK_HIT_1, MOCK_HIT_2]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      await selectCase(user, 'Case Alpha');

      await user.click(screen.getByRole('button', { name: i18n.t('confirm') }));
      await waitFor(() => expect(mockClose).toHaveBeenCalled());

      expect(api.v2.case.items.post).toHaveBeenCalledTimes(2);
    });

    it('submits the correct value for each record', async () => {
      const api = (await import('api')).default;
      renderModal([MOCK_HIT_1, MOCK_HIT_2]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      await selectCase(user, 'Case Alpha');

      await user.click(screen.getByRole('button', { name: i18n.t('confirm') }));
      await waitFor(() => expect(mockClose).toHaveBeenCalled());

      expect(api.v2.case.items.post).toHaveBeenCalledWith(
        'case-a',
        expect.objectContaining({ value: MOCK_HIT_1.howler.id })
      );
      expect(api.v2.case.items.post).toHaveBeenCalledWith(
        'case-a',
        expect.objectContaining({ value: MOCK_HIT_2.howler.id })
      );
    });

    it('uses an independently edited title for each record', async () => {
      const api = (await import('api')).default;
      renderModal([MOCK_HIT_1, MOCK_HIT_2]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      await selectCase(user, 'Case Alpha');

      const titleInputs = screen.getAllByPlaceholderText(i18n.t('modal.cases.add_to_case.title'));
      await user.clear(titleInputs[0]);
      await user.type(titleInputs[0], 'First Item');

      await user.click(screen.getByRole('button', { name: i18n.t('confirm') }));
      await waitFor(() => expect(mockClose).toHaveBeenCalled());

      expect(api.v2.case.items.post).toHaveBeenCalledWith(
        'case-a',
        expect.objectContaining({ path: 'First Item', value: MOCK_HIT_1.howler.id })
      );
      expect(api.v2.case.items.post).toHaveBeenCalledWith(
        'case-a',
        expect.objectContaining({ value: MOCK_HIT_2.howler.id })
      );
    });
  });
});
