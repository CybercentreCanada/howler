import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import type { Hit } from 'models/entities/generated/Hit';
import type { Pivot } from 'models/entities/generated/Pivot';
import type { PropsWithChildren, ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import CluePivot from './CluePivot';

const clueState = vi.hoisted(() => ({
  actions: {} as Record<string, any>,
  executeAction: vi.fn(),
  guessType: vi.fn()
}));
const showErrorMessage = vi.hoisted(() => vi.fn());

vi.mock('@cccsaurora/clue-ui', () => ({
  useClueActionsSelector: (selector: (context: unknown) => unknown) =>
    selector({ availableActions: clueState.actions, executeAction: clueState.executeAction }),
  useClueEnrichSelector: (selector: (context: unknown) => unknown) => selector({ guessType: clueState.guessType })
}));

vi.mock('@iconify/react', () => ({
  Icon: ({ icon }: { icon: string }) => <span data-testid="pivot-icon">{icon}</span>
}));

vi.mock('components/elements/display/HowlerCard', () => ({
  default: ({ children, onClick }: { children: ReactNode; onClick?: () => void }) => (
    <div data-testid="howler-card" onClick={onClick}>
      {children}
    </div>
  )
}));

vi.mock('components/hooks/useMySnackbar', () => ({
  default: () => ({ showErrorMessage })
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    i18n: { language: 'en' },
    t: (key: string) => key
  })
}));

const action = {
  accept_multiple: false,
  params: {
    properties: {
      selector: { type: 'string' },
      note: { type: 'string' }
    }
  }
};

const pivot = (overrides: Partial<Pivot> = {}): Pivot =>
  ({
    value: 'enrich',
    icon: 'material-symbols:bolt',
    label: { en: 'Enrich', fr: 'Enrichir' },
    mappings: [
      { key: 'selector', field: 'howler.id' },
      { key: 'note', field: 'custom', custom_value: 'from-pivot' }
    ],
    ...overrides
  }) as Pivot;

const hit = { howler: { id: 'hit-1' } } as unknown as Hit;
const dossier = { dossier_id: 'dossier-1' } as any;

const Wrapper = ({ children }: PropsWithChildren) => (
  <ApiConfigContext.Provider
    value={{
      config: {
        indexes: { hit: { 'howler.id': {} } },
        configuration: { mapping: {} }
      } as any,
      setConfig: vi.fn(),
      loaded: true
    }}
  >
    {children}
  </ApiConfigContext.Provider>
);

describe('CluePivot', () => {
  beforeEach(() => {
    clueState.actions = { enrich: action };
    clueState.executeAction.mockReset();
    clueState.executeAction.mockResolvedValue(undefined);
    clueState.guessType.mockReset();
    clueState.guessType.mockReturnValue('indicator');
    showErrorMessage.mockReset();
  });

  it('renders a menu item and executes the mapped action without opening a window', async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();

    render(
      <Wrapper>
        <CluePivot pivot={pivot()} hit={hit} dossier={dossier} variant="menu-item" onNavigate={onNavigate} />
      </Wrapper>
    );

    await user.click(screen.getByRole('menuitem', { name: /Enrich/ }));

    expect(onNavigate).toHaveBeenCalledOnce();
    await waitFor(() => {
      expect(clueState.executeAction).toHaveBeenCalledWith(
        'enrich',
        [{ type: 'indicator', value: 'hit-1' }],
        { note: 'from-pivot' },
        { forceMenu: false }
      );
    });
  });

  it('passes forceMenu when the settings button is clicked on a card pivot', async () => {
    const user = userEvent.setup();

    render(
      <Wrapper>
        <CluePivot pivot={pivot()} hit={hit} dossier={dossier} compact />
      </Wrapper>
    );

    await user.click(screen.getByRole('button', { name: '' }));

    await waitFor(() => {
      expect(clueState.executeAction).toHaveBeenCalledWith(
        'enrich',
        [{ type: 'indicator', value: 'hit-1' }],
        { note: 'from-pivot' },
        { forceMenu: true }
      );
    });
  });

  it('does not render a pivot when its action is unavailable', () => {
    clueState.actions = {};

    const { container } = render(
      <Wrapper>
        <CluePivot pivot={pivot()} hit={hit} dossier={dossier} />
      </Wrapper>
    );

    expect(container).toBeEmptyDOMElement();
    expect(showErrorMessage).not.toHaveBeenCalled();
  });
});
