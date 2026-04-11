/// <reference types="vitest" />
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent, { type UserEvent } from '@testing-library/user-event';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import { ModalContext } from 'components/app/providers/ModalProvider';
import i18n from 'i18n';
import type { Hit } from 'models/entities/generated/Hit';
import type { Observable } from 'models/entities/generated/Observable';
import type { PropsWithChildren } from 'react';
import { I18nextProvider } from 'react-i18next';
import { createMockHit, createMockObservable } from 'tests/utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import CreateCaseModal from './CreateCaseModal';

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

let mockSetContent: ((val: string) => void) | null = null;
vi.mock('components/elements/MarkdownEditor', () => ({
  default: ({ content, setContent }: { content: string; setContent: (v: string) => void }) => {
    mockSetContent = setContent;
    return <textarea id="markdown-editor" value={content} onChange={ev => setContent(ev.target.value)} />;
  }
}));

vi.mock('api', () => ({
  default: {
    v2: {
      case: {
        post: vi.fn().mockReturnValue('case-post-request'),
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

const MOCK_HIT_1: Hit = createMockHit({
  howler: { id: 'hit-001', analytic: 'AnalyticOne', status: 'open' } as any
});

const MOCK_HIT_2: Hit = createMockHit({
  howler: { id: 'hit-002', analytic: 'AnalyticTwo', status: 'open' } as any
});

const MOCK_OBSERVABLE: Observable = createMockObservable({
  howler: { id: 'obs-001' } as any
});

const MOCK_CONFIG = {
  lookups: {
    'howler.escalation': ['normal', 'focus', 'crisis']
  }
} as any;

// ---------------------------------------------------------------------------
// Wrapper
// ---------------------------------------------------------------------------

const Wrapper = ({ children }: PropsWithChildren) => (
  <I18nextProvider i18n={i18n as any}>
    <ApiConfigContext.Provider value={{ config: MOCK_CONFIG, setConfig: vi.fn() } as any}>
      <ModalContext.Provider value={{ close: mockClose, open: vi.fn(), setContent: vi.fn() } as any}>
        {children}
      </ModalContext.Provider>
    </ApiConfigContext.Provider>
  </I18nextProvider>
);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const renderModal = (records: (Hit | Observable)[]) =>
  render(<CreateCaseModal records={records} />, { wrapper: Wrapper });

const fillCaseMetadata = async (
  user: UserEvent,
  { title = 'My Case', summary = 'A summary' }: { title?: string; summary?: string } = {}
) => {
  await user.type(screen.getByPlaceholderText(i18n.t('modal.cases.create_case.title')), title);
  await user.type(screen.getByPlaceholderText(i18n.t('modal.cases.create_case.summary')), summary);
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('CreateCaseModal', () => {
  let user: UserEvent;

  beforeEach(() => {
    user = userEvent.setup();
    vi.clearAllMocks();
    // Default: case creation returns a case, item post resolves
    mockDispatchApi.mockResolvedValue({ case_id: 'new-case-id' });
  });

  // -------------------------------------------------------------------------
  // Initial render
  // -------------------------------------------------------------------------

  describe('initial render', () => {
    it('shows the modal title', () => {
      renderModal([MOCK_HIT_1]);
      expect(screen.getByText(i18n.t('modal.cases.create_case'))).toBeInTheDocument();
    });

    it('renders a cancel button', () => {
      renderModal([MOCK_HIT_1]);
      expect(screen.getByRole('button', { name: i18n.t('cancel') })).toBeInTheDocument();
    });

    it('renders a confirm button', () => {
      renderModal([MOCK_HIT_1]);
      expect(screen.getByRole('button', { name: i18n.t('confirm') })).toBeInTheDocument();
    });

    it('confirm button is disabled before required fields are filled', () => {
      renderModal([MOCK_HIT_1]);
      expect(screen.getByRole('button', { name: i18n.t('confirm') })).toBeDisabled();
    });

    it('renders case title, summary, and escalation inputs', () => {
      renderModal([MOCK_HIT_1]);
      expect(screen.getByPlaceholderText(i18n.t('modal.cases.create_case.title'))).toBeInTheDocument();
      expect(screen.getByPlaceholderText(i18n.t('modal.cases.create_case.summary'))).toBeInTheDocument();
      expect(screen.getByText(i18n.t('modal.cases.create_case.overview'))).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Per-record rows
  // -------------------------------------------------------------------------

  describe('per-record rows', () => {
    it('renders a row for each record', () => {
      renderModal([MOCK_HIT_1, MOCK_HIT_2]);
      expect(screen.getByText(MOCK_HIT_1.howler.analytic)).toBeInTheDocument();
      expect(screen.getByText(MOCK_HIT_2.howler.analytic)).toBeInTheDocument();
    });

    it('renders a row for an observable record', () => {
      renderModal([MOCK_OBSERVABLE]);
      expect(screen.getByText('Observable')).toBeInTheDocument();
    });

    it('pre-populates the title for a hit with analytic and id', () => {
      renderModal([MOCK_HIT_1]);
      const titleInputs = screen.getAllByPlaceholderText(i18n.t('modal.cases.add_to_case.title'));
      expect(titleInputs[0]).toHaveValue(`${MOCK_HIT_1.howler.analytic} (${MOCK_HIT_1.howler.id})`);
    });

    it('pre-populates the title for an observable with Observable and id', () => {
      renderModal([MOCK_OBSERVABLE]);
      const titleInput = screen.getByPlaceholderText(i18n.t('modal.cases.add_to_case.title'));
      expect(titleInput).toHaveValue(`Observable (${MOCK_OBSERVABLE.howler.id})`);
    });

    it('shows the alert placement section label when there are records', () => {
      renderModal([MOCK_HIT_1]);
      expect(screen.getByText(i18n.t('modal.cases.create_case.items_section'))).toBeInTheDocument();
    });

    it('does not show the alert placement section when records is empty', () => {
      renderModal([]);
      expect(screen.queryByText(i18n.t('modal.cases.create_case.items_section'))).not.toBeInTheDocument();
    });

    it('shows the full path preview when a title is set', async () => {
      renderModal([MOCK_HIT_1]);
      const expectedTitle = `${MOCK_HIT_1.howler.analytic} (${MOCK_HIT_1.howler.id})`;
      await waitFor(() => {
        expect(
          screen.getByText(i18n.t('modal.cases.add_to_case.full_path', { path: expectedTitle }))
        ).toBeInTheDocument();
      });
    });

    it('shows combined path/title in the full path preview', async () => {
      renderModal([MOCK_HIT_1]);
      const pathInput = screen.getByPlaceholderText(i18n.t('modal.cases.add_to_case.select_path'));
      await user.type(pathInput, 'folder');

      const expectedFull = `folder/${MOCK_HIT_1.howler.analytic} (${MOCK_HIT_1.howler.id})`;
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
    it('enables confirm after title and summary are filled', async () => {
      renderModal([MOCK_HIT_1]);
      await fillCaseMetadata(user);
      expect(screen.getByRole('button', { name: i18n.t('confirm') })).toBeEnabled();
    });

    it('disables confirm when case title is empty', async () => {
      renderModal([MOCK_HIT_1]);
      await user.type(screen.getByPlaceholderText(i18n.t('modal.cases.create_case.summary')), 'A summary');
      expect(screen.getByRole('button', { name: i18n.t('confirm') })).toBeDisabled();
    });

    it('disables confirm when summary is empty', async () => {
      renderModal([MOCK_HIT_1]);
      await user.type(screen.getByPlaceholderText(i18n.t('modal.cases.create_case.title')), 'My Case');
      expect(screen.getByRole('button', { name: i18n.t('confirm') })).toBeDisabled();
    });

    it('disables confirm when any item title is cleared', async () => {
      renderModal([MOCK_HIT_1]);
      await fillCaseMetadata(user);

      const titleInput = screen.getByPlaceholderText(i18n.t('modal.cases.add_to_case.title'));
      await user.clear(titleInput);

      expect(screen.getByRole('button', { name: i18n.t('confirm') })).toBeDisabled();
    });

    it('enables confirm without records (case-only creation)', async () => {
      renderModal([]);
      await fillCaseMetadata(user);
      expect(screen.getByRole('button', { name: i18n.t('confirm') })).toBeEnabled();
    });
  });

  // -------------------------------------------------------------------------
  // Cancel
  // -------------------------------------------------------------------------

  describe('cancel button', () => {
    it('calls close when cancel is clicked', async () => {
      renderModal([MOCK_HIT_1]);
      await user.click(screen.getByRole('button', { name: i18n.t('cancel') }));
      expect(mockClose).toHaveBeenCalledTimes(1);
    });
  });

  // -------------------------------------------------------------------------
  // Submission
  // -------------------------------------------------------------------------

  describe('form submission', () => {
    it('calls case.post with title, summary, and closes', async () => {
      const api = (await import('api')).default;
      mockDispatchApi.mockResolvedValue({ case_id: 'new-case-id' });

      renderModal([MOCK_HIT_1]);
      await fillCaseMetadata(user, { title: 'Test Case', summary: 'Test summary' });
      await user.click(screen.getByRole('button', { name: i18n.t('confirm') }));

      await waitFor(() => expect(mockClose).toHaveBeenCalled());

      expect(api.v2.case.post).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Test Case', summary: 'Test summary' })
      );
    });

    it('includes overview in case.post when filled', async () => {
      const api = (await import('api')).default;
      mockDispatchApi.mockResolvedValue({ case_id: 'new-case-id' });

      renderModal([]);
      await fillCaseMetadata(user);
      act(() => mockSetContent?.('## Overview\nSome detail'));

      await user.click(screen.getByRole('button', { name: i18n.t('confirm') }));
      await waitFor(() => expect(mockClose).toHaveBeenCalled());

      expect(api.v2.case.post).toHaveBeenCalledWith(expect.objectContaining({ overview: '## Overview\nSome detail' }));
    });

    it('does not include overview when left blank', async () => {
      const api = (await import('api')).default;
      mockDispatchApi.mockResolvedValue({ case_id: 'new-case-id' });

      renderModal([]);
      await fillCaseMetadata(user);
      await user.click(screen.getByRole('button', { name: i18n.t('confirm') }));
      await waitFor(() => expect(mockClose).toHaveBeenCalled());

      const callArg = vi.mocked(api.v2.case.post).mock.calls[0][0] as any;
      expect(callArg).not.toHaveProperty('overview');
    });

    it('includes escalation when selected', async () => {
      const api = (await import('api')).default;
      mockDispatchApi.mockResolvedValue({ case_id: 'new-case-id' });

      renderModal([]);
      await fillCaseMetadata(user);

      const combobox = screen.getByRole('combobox');
      await user.click(combobox);
      const option = await screen.findByRole('option', { name: 'crisis' });
      await user.click(option);

      await user.click(screen.getByRole('button', { name: i18n.t('confirm') }));
      await waitFor(() => expect(mockClose).toHaveBeenCalled());

      expect(api.v2.case.post).toHaveBeenCalledWith(expect.objectContaining({ escalation: 'crisis' }));
    });

    it('calls items.post for each record after case creation', async () => {
      const api = (await import('api')).default;
      mockDispatchApi.mockResolvedValue({ case_id: 'new-case-id' });

      renderModal([MOCK_HIT_1, MOCK_HIT_2]);
      await fillCaseMetadata(user);
      await user.click(screen.getByRole('button', { name: i18n.t('confirm') }));

      await waitFor(() => expect(mockClose).toHaveBeenCalled());

      // 1 case.post + 2 items.post
      expect(mockDispatchApi).toHaveBeenCalledTimes(3);
      expect(api.v2.case.items.post).toHaveBeenCalledTimes(2);
    });

    it('uses the default title as path for items', async () => {
      const api = (await import('api')).default;
      mockDispatchApi.mockResolvedValue({ case_id: 'new-case-id' });

      renderModal([MOCK_HIT_1]);
      await fillCaseMetadata(user);
      await user.click(screen.getByRole('button', { name: i18n.t('confirm') }));

      await waitFor(() => expect(mockClose).toHaveBeenCalled());

      expect(api.v2.case.items.post).toHaveBeenCalledWith(
        'new-case-id',
        expect.objectContaining({
          path: `${MOCK_HIT_1.howler.analytic} (${MOCK_HIT_1.howler.id})`,
          value: MOCK_HIT_1.howler.id,
          type: 'hit'
        })
      );
    });

    it('uses a custom edited item title in the path', async () => {
      const api = (await import('api')).default;
      mockDispatchApi.mockResolvedValue({ case_id: 'new-case-id' });

      renderModal([MOCK_HIT_1]);
      await fillCaseMetadata(user);

      const titleInput = screen.getByPlaceholderText(i18n.t('modal.cases.add_to_case.title'));
      await user.clear(titleInput);
      await user.type(titleInput, 'Custom Item Name');

      await user.click(screen.getByRole('button', { name: i18n.t('confirm') }));
      await waitFor(() => expect(mockClose).toHaveBeenCalled());

      expect(api.v2.case.items.post).toHaveBeenCalledWith(
        'new-case-id',
        expect.objectContaining({ path: 'Custom Item Name' })
      );
    });

    it('combines folder path and title when a folder path is provided', async () => {
      const api = (await import('api')).default;
      mockDispatchApi.mockResolvedValue({ case_id: 'new-case-id' });

      renderModal([MOCK_HIT_1]);
      await fillCaseMetadata(user);

      await user.type(screen.getByPlaceholderText(i18n.t('modal.cases.add_to_case.select_path')), 'investigations');

      await user.click(screen.getByRole('button', { name: i18n.t('confirm') }));
      await waitFor(() => expect(mockClose).toHaveBeenCalled());

      expect(api.v2.case.items.post).toHaveBeenCalledWith(
        'new-case-id',
        expect.objectContaining({
          path: `investigations/${MOCK_HIT_1.howler.analytic} (${MOCK_HIT_1.howler.id})`
        })
      );
    });

    it('uses observable __index for observable records', async () => {
      const api = (await import('api')).default;
      mockDispatchApi.mockResolvedValue({ case_id: 'new-case-id' });

      renderModal([MOCK_OBSERVABLE]);
      await fillCaseMetadata(user);
      await user.click(screen.getByRole('button', { name: i18n.t('confirm') }));

      await waitFor(() => expect(mockClose).toHaveBeenCalled());

      expect(api.v2.case.items.post).toHaveBeenCalledWith(
        'new-case-id',
        expect.objectContaining({ type: 'observable' })
      );
    });

    it('does not call items.post when there are no records', async () => {
      const api = (await import('api')).default;
      mockDispatchApi.mockResolvedValue({ case_id: 'new-case-id' });

      renderModal([]);
      await fillCaseMetadata(user);
      await user.click(screen.getByRole('button', { name: i18n.t('confirm') }));

      await waitFor(() => expect(mockClose).toHaveBeenCalled());

      expect(api.v2.case.items.post).not.toHaveBeenCalled();
    });

    it('does not close if case creation returns no case_id', async () => {
      mockDispatchApi.mockResolvedValue(null);

      renderModal([]);
      await fillCaseMetadata(user);
      await user.click(screen.getByRole('button', { name: i18n.t('confirm') }));

      await waitFor(() => expect(mockDispatchApi).toHaveBeenCalled());
      expect(mockClose).not.toHaveBeenCalled();
    });
  });

  // -------------------------------------------------------------------------
  // Multiple records
  // -------------------------------------------------------------------------

  describe('multiple records', () => {
    it('renders independent title inputs for each record', () => {
      renderModal([MOCK_HIT_1, MOCK_HIT_2]);
      const titleInputs = screen.getAllByPlaceholderText(i18n.t('modal.cases.add_to_case.title'));
      expect(titleInputs).toHaveLength(2);
      expect(titleInputs[0]).toHaveValue(`${MOCK_HIT_1.howler.analytic} (${MOCK_HIT_1.howler.id})`);
      expect(titleInputs[1]).toHaveValue(`${MOCK_HIT_2.howler.analytic} (${MOCK_HIT_2.howler.id})`);
    });

    it('editing one record title does not affect the other', async () => {
      renderModal([MOCK_HIT_1, MOCK_HIT_2]);
      const titleInputs = screen.getAllByPlaceholderText(i18n.t('modal.cases.add_to_case.title'));
      await user.clear(titleInputs[0]);
      await user.type(titleInputs[0], 'Edited Title');

      expect(titleInputs[0]).toHaveValue('Edited Title');
      expect(titleInputs[1]).toHaveValue(`${MOCK_HIT_2.howler.analytic} (${MOCK_HIT_2.howler.id})`);
    });

    it('mixed hit and observable records each get correct default titles', () => {
      renderModal([MOCK_HIT_1, MOCK_OBSERVABLE]);
      const titleInputs = screen.getAllByPlaceholderText(i18n.t('modal.cases.add_to_case.title'));
      expect(titleInputs[0]).toHaveValue(`${MOCK_HIT_1.howler.analytic} (${MOCK_HIT_1.howler.id})`);
      expect(titleInputs[1]).toHaveValue(`Observable (${MOCK_OBSERVABLE.howler.id})`);
    });
  });
});
