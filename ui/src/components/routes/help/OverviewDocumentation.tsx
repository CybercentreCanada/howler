import { PageCenter } from '@tui/core';
import HandlebarsMarkdown from 'components/elements/display/HandlebarsMarkdown';
import { useScrollRestoration } from 'components/hooks/useScrollRestoration';
import type { FC } from 'react';
import ErrorBoundary from '../ErrorBoundary';
import { useStartingTemplate } from '../overviews/startingTemplate';

const EXAMPLE_HIT = {
  howler: {
    status: 'open',
    escalation: 'alert',
    is_bundle: false
  }
};

const OverviewDocumentation: FC = () => {
  useScrollRestoration();

  const template = useStartingTemplate();

  return (
    <PageCenter margin={4} width="100%" textAlign="left">
      <ErrorBoundary>
        <HandlebarsMarkdown md={template} object={EXAMPLE_HIT} />
      </ErrorBoundary>
    </PageCenter>
  );
};
export default OverviewDocumentation;
