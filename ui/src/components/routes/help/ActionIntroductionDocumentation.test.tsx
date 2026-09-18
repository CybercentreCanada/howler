/// <reference types="vitest" />
import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const mockOperationsGet = vi.hoisted(() => vi.fn());

vi.mock('@tui/core', () => ({
  useAppUser: () => ({ user: { roles: ['analyst'] } })
}));

vi.mock('api', () => ({
  default: {
    action: {
      operations: {
        get: mockOperationsGet
      }
    }
  }
}));

vi.mock('components/elements/addons/search/phrase/Phrase', () => ({
  default: () => <div>phrase</div>
}));

vi.mock('components/elements/display/Markdown', () => ({
  default: ({ components }: any) => (
    <div>
      <div>{components.action_count}</div>
      <div>{components.action_list}</div>
      <div>{components.tui_phrase}</div>
      <div>{components.operation_select}</div>
      <div>{components.operation_configuration}</div>
      <div>{components.report}</div>
      <div>{components.automation_options}</div>
    </div>
  )
}));

vi.mock('../../elements/display/QueryResultText', () => ({
  default: ({ count, query }: any) => <div>{count}:{query}</div>
}));

vi.mock('../action/shared/ActionReportDisplay', () => ({
  default: ({ operations }: any) => <div>report:{operations.length}</div>
}));

vi.mock('../action/shared/OperationStep', () => ({
  default: ({ step }: any) => <div>step:{Object.keys(step.args).join(',')}</div>
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    i18n: { language: 'en' },
    t: (key: string) => key
  })
}));

import ActionIntroductionDocumentation from './ActionIntroductionDocumentation';

describe('ActionIntroductionDocumentation', () => {
  it('loads permitted operations and renders the markdown component slots', async () => {
    mockOperationsGet.mockResolvedValue([
      {
        id: 'add_label',
        title: 'Add Label',
        description: { short: 'Short desc' },
        roles: ['analyst'],
        steps: [{ args: { category: true } }]
      },
      {
        id: 'blocked',
        title: 'Blocked',
        description: { short: 'Blocked desc' },
        roles: ['admin'],
        steps: []
      }
    ]);

    render(<ActionIntroductionDocumentation />);

    await waitFor(() => expect(screen.getByText('1')).toBeInTheDocument());
    expect(screen.getByText(/operations.add_label/)).toBeInTheDocument();
    expect(screen.queryByText(/blocked/i)).toBeNull();
    expect(screen.getByText('phrase')).toBeInTheDocument();
    expect(screen.getByText('134:howler.id:*')).toBeInTheDocument();
    expect(screen.getByText('step:category')).toBeInTheDocument();
    expect(screen.getByText('report:1')).toBeInTheDocument();
    expect(screen.getByText('route.actions.trigger.create, route.actions.trigger.promote, route.actions.trigger.demote')).toBeInTheDocument();
  });
});
