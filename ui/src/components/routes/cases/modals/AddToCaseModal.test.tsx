/// <reference types="vitest" />
import { render, screen, waitFor } from '@testing-library/react';
import userEvent, { type UserEvent } from '@testing-library/user-event';
import { ModalContext } from 'components/app/providers/ModalProvider';
import i18n from 'i18n';
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

vi.mock('components/elements/case/CaseCard', () => ({
  default: ({ case: c }: any) => <div>{c?.title ?? c?.case_id}</div>
}));

vi.mock('api', () => ({
  default: {
    search: {
      case: {
        post: vi.fn().mockReturnValue('search-case-request')
      }
    },
    v2: {
      case: {
        items: {
          post: vi.fn().mockReturnValue('items-post-request')
        }
      }
    }
  }
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_HIT: Hit = createMockHit({
  howler: { id: 'hit-001', analytic: 'MyAnalytic' } as any
});

const MOCK_OBSERVABLE: Observable = createMockObservable({
  howler: { id: 'obs-001' } as any
});

const CASE_A = createMockCase({ case_id: 'case-a', title: 'Alpha Case', items: [] });
const CASE_B = createMockCase({
  case_id: 'case-b',
  title: 'Beta Case',
  items: [
    { type: 'hit', value: 'hit-001', path: 'folder/subfolder/Title' } as any,
    { type: 'hit', value: 'hit-002', path: 'folder/OtherTitle' } as any
  ]
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

const renderModal = (records: (Hit | Observable)[]) => {
  return render(<AddToCaseModal records={records} />, { wrapper: Wrapper });
};

/** Selects a case from the case Autocomplete. Requires cases to already be loaded. */
const selectCase = async (user: UserEvent, caseTitle: string) => {
  const comboboxes = screen.getAllByRole('combobox');
  // First combobox is the case selector
  await user.click(comboboxes[0]);
  await user.type(comboboxes[0], caseTitle.slice(0, 3));
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
      renderModal([MOCK_HIT]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      expect(screen.getByText(i18n.t('modal.cases.add_to_case'))).toBeInTheDocument();
    });

    it('renders a cancel button', async () => {
      renderModal([MOCK_HIT]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      expect(screen.getByRole('button', { name: i18n.t('cancel') })).toBeInTheDocument();
    });

    it('renders a confirm button', async () => {
      renderModal([MOCK_HIT]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      expect(screen.getByRole('button', { name: i18n.t('confirm') })).toBeInTheDocument();
    });

    it('confirm button is disabled before a case is selected', async () => {
      renderModal([MOCK_HIT]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      expect(screen.getByRole('button', { name: i18n.t('confirm') })).toBeDisabled();
    });

    it('fetches cases on mount', async () => {
      renderModal([MOCK_HIT]);
      await waitFor(() => {
        expect(mockDispatchApi).toHaveBeenCalledTimes(1);
      });
    });
  });

  // -------------------------------------------------------------------------
  // Default title – hit
  // -------------------------------------------------------------------------

  describe('default title for a hit record', () => {
    it('pre-populates the title field with analytic and id', async () => {
      renderModal([MOCK_HIT]);

      // Select a case so the title field is visible
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      await selectCase(user, CASE_A.title);

      const titleInput = screen.getByPlaceholderText(i18n.t('modal.cases.add_to_case.title'));
      expect(titleInput).toHaveValue(`${MOCK_HIT.howler.analytic} (${MOCK_HIT.howler.id})`);
    });

    it('confirm button is enabled after selecting a case (title already set)', async () => {
      renderModal([MOCK_HIT]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      await selectCase(user, CASE_A.title);

      expect(screen.getByRole('button', { name: i18n.t('confirm') })).toBeEnabled();
    });
  });

  // -------------------------------------------------------------------------
  // Default title – observable
  // -------------------------------------------------------------------------

  describe('default title for an observable record', () => {
    it('pre-populates the title field with Observable and id', async () => {
      renderModal([MOCK_OBSERVABLE]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      await selectCase(user, CASE_A.title);

      const titleInput = screen.getByPlaceholderText(i18n.t('modal.cases.add_to_case.title'));
      expect(titleInput).toHaveValue(`Observable (${MOCK_OBSERVABLE.howler.id})`);
    });
  });

  // -------------------------------------------------------------------------
  // Default title – empty records
  // -------------------------------------------------------------------------

  describe('default title with no records', () => {
    it('pre-populates title as empty string', async () => {
      renderModal([]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      await selectCase(user, CASE_A.title);

      const titleInput = screen.getByPlaceholderText(i18n.t('modal.cases.add_to_case.title'));
      expect(titleInput).toHaveValue('');
    });

    it('confirm button is disabled with no title', async () => {
      renderModal([]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      await selectCase(user, CASE_A.title);

      expect(screen.getByRole('button', { name: i18n.t('confirm') })).toBeDisabled();
    });
  });

  // -------------------------------------------------------------------------
  // Title is editable
  // -------------------------------------------------------------------------

  describe('title field is editable', () => {
    it('allows the user to overwrite the pre-populated title', async () => {
      renderModal([MOCK_HIT]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      await selectCase(user, CASE_A.title);

      const titleInput = screen.getByPlaceholderText(i18n.t('modal.cases.add_to_case.title'));
      await user.clear(titleInput);
      await user.type(titleInput, 'Custom Title');

      expect(titleInput).toHaveValue('Custom Title');
    });

    it('disables confirm if user clears the title', async () => {
      renderModal([MOCK_HIT]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      await selectCase(user, CASE_A.title);

      const titleInput = screen.getByPlaceholderText(i18n.t('modal.cases.add_to_case.title'));
      await user.clear(titleInput);

      expect(screen.getByRole('button', { name: i18n.t('confirm') })).toBeDisabled();
    });
  });

  // -------------------------------------------------------------------------
  // Full path display
  // -------------------------------------------------------------------------

  describe('full path preview', () => {
    it('shows the full path when a title is set without a path', async () => {
      renderModal([MOCK_HIT]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      await selectCase(user, CASE_A.title);

      const expectedPath = `${MOCK_HIT.howler.analytic} (${MOCK_HIT.howler.id})`;
      await waitFor(() => {
        expect(
          screen.getByText(i18n.t('modal.cases.add_to_case.full_path', { path: expectedPath }))
        ).toBeInTheDocument();
      });
    });

    it('shows the full path combining path and title', async () => {
      renderModal([MOCK_HIT]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      await selectCase(user, CASE_B.title);

      // Wait for case to be selected (path/title fields appear)
      await screen.findByPlaceholderText(i18n.t('modal.cases.add_to_case.select_path'));

      // Type a path prefix in the path field
      const pathCombobox = screen.getAllByRole('combobox')[1];
      await user.type(pathCombobox, 'myfolder');

      const expectedFullPath = `myfolder/${MOCK_HIT.howler.analytic} (${MOCK_HIT.howler.id})`;
      await waitFor(() => {
        expect(
          screen.getByText(i18n.t('modal.cases.add_to_case.full_path', { path: expectedFullPath }))
        ).toBeInTheDocument();
      });
    });
  });

  // -------------------------------------------------------------------------
  // Folder options derived from existing case items
  // -------------------------------------------------------------------------

  describe('folder options', () => {
    it('derives folder path options from the selected case items', async () => {
      renderModal([MOCK_HIT]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      await selectCase(user, CASE_B.title);

      // Open the path autocomplete
      await screen.findByPlaceholderText(i18n.t('modal.cases.add_to_case.select_path'));
      const pathCombobox = screen.getAllByRole('combobox')[1];
      await user.click(pathCombobox);

      // Both 'folder' and 'folder/subfolder' should appear as options
      await waitFor(() => {
        expect(screen.getByRole('option', { name: 'folder' })).toBeInTheDocument();
        expect(screen.getByRole('option', { name: 'folder/subfolder' })).toBeInTheDocument();
      });
    });

    it('clears the path when a new case is selected', async () => {
      renderModal([MOCK_HIT]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());

      // Select CASE_B and type a path
      await selectCase(user, CASE_B.title);
      await screen.findByPlaceholderText(i18n.t('modal.cases.add_to_case.select_path'));
      const pathCombobox = screen.getAllByRole('combobox')[1];
      await user.type(pathCombobox, 'myfolder');

      // Now switch to CASE_A
      const caseCombobox = screen.getAllByRole('combobox')[0];
      await user.clear(caseCombobox);
      await user.type(caseCombobox, CASE_A.title.slice(0, 3));
      const option = await screen.findByRole('option', { name: CASE_A.title });
      await user.click(option);

      // The path in the second combobox is reset
      const updatedPathCombobox = screen.getAllByRole('combobox')[1];
      expect(updatedPathCombobox).toHaveValue('');
    });
  });

  // -------------------------------------------------------------------------
  // Cancel button
  // -------------------------------------------------------------------------

  describe('cancel button', () => {
    it('calls close when cancel is clicked', async () => {
      renderModal([MOCK_HIT]);
      await user.click(screen.getByRole('button', { name: i18n.t('cancel') }));
      expect(mockClose).toHaveBeenCalledTimes(1);
    });
  });

  // -------------------------------------------------------------------------
  // Submission
  // -------------------------------------------------------------------------

  describe('form submission', () => {
    it('calls items.post with correct arguments and closes the modal', async () => {
      // Second dispatchApi call (items.post) resolves to a case
      mockDispatchApi
        .mockResolvedValueOnce({ items: [CASE_A, CASE_B] }) // search
        .mockResolvedValueOnce(CASE_A); // items.post

      renderModal([MOCK_HIT]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      await selectCase(user, CASE_A.title);

      await user.click(screen.getByRole('button', { name: i18n.t('confirm') }));

      await waitFor(() => {
        expect(mockDispatchApi).toHaveBeenCalledTimes(2);
      });

      const secondCall = mockDispatchApi.mock.calls[1][0];
      // The second call argument is the return value of api.v2.case.items.post
      expect(secondCall).toBe('items-post-request');

      expect(mockClose).toHaveBeenCalledTimes(1);
    });

    it('passes the default title as fullPath when no folder path is chosen', async () => {
      const api = (await import('api')).default;
      mockDispatchApi.mockResolvedValueOnce({ items: [CASE_A] }).mockResolvedValueOnce(CASE_A);

      renderModal([MOCK_HIT]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      await selectCase(user, CASE_A.title);

      await user.click(screen.getByRole('button', { name: i18n.t('confirm') }));
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalledTimes(2));

      expect(api.v2.case.items.post).toHaveBeenCalledWith(CASE_A.case_id, {
        path: `${MOCK_HIT.howler.analytic} (${MOCK_HIT.howler.id})`,
        value: MOCK_HIT.howler.id,
        type: 'hit'
      });
    });

    it('passes the combined path as fullPath when a folder path is chosen', async () => {
      const api = (await import('api')).default;
      mockDispatchApi.mockResolvedValueOnce({ items: [CASE_B] }).mockResolvedValueOnce(CASE_B);

      renderModal([MOCK_HIT]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      await selectCase(user, CASE_B.title);

      await screen.findByPlaceholderText(i18n.t('modal.cases.add_to_case.select_path'));
      const pathCombobox = screen.getAllByRole('combobox')[1];
      await user.type(pathCombobox, 'investigations');

      await user.click(screen.getByRole('button', { name: i18n.t('confirm') }));
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalledTimes(2));

      expect(api.v2.case.items.post).toHaveBeenCalledWith(CASE_B.case_id, {
        path: `investigations/${MOCK_HIT.howler.analytic} (${MOCK_HIT.howler.id})`,
        value: MOCK_HIT.howler.id,
        type: 'hit'
      });
    });

    it('uses the observable __index type when the record is an observable', async () => {
      const api = (await import('api')).default;
      mockDispatchApi.mockResolvedValueOnce({ items: [CASE_A] }).mockResolvedValueOnce(CASE_A);

      renderModal([MOCK_OBSERVABLE]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      await selectCase(user, CASE_A.title);

      await user.click(screen.getByRole('button', { name: i18n.t('confirm') }));
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalledTimes(2));

      expect(api.v2.case.items.post).toHaveBeenCalledWith(
        CASE_A.case_id,
        expect.objectContaining({ type: 'observable' })
      );
    });

    it('uses a custom edited title in the submitted path', async () => {
      const api = (await import('api')).default;
      mockDispatchApi.mockResolvedValueOnce({ items: [CASE_A] }).mockResolvedValueOnce(CASE_A);

      renderModal([MOCK_HIT]);
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      await selectCase(user, CASE_A.title);

      const titleInput = screen.getByPlaceholderText(i18n.t('modal.cases.add_to_case.title'));
      await user.clear(titleInput);
      await user.type(titleInput, 'My Custom Title');

      await user.click(screen.getByRole('button', { name: i18n.t('confirm') }));
      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalledTimes(2));

      expect(api.v2.case.items.post).toHaveBeenCalledWith(
        CASE_A.case_id,
        expect.objectContaining({ path: 'My Custom Title' })
      );
    });
  });
});
