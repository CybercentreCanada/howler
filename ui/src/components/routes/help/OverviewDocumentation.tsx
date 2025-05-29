import PageCenter from 'commons/components/pages/PageCenter';
import HandlebarsMarkdown from 'components/elements/display/HandlebarsMarkdown';
import { useScrollRestoration } from 'components/hooks/useScrollRestoration';
import type { FC } from 'react';
import ErrorBoundary from '../ErrorBoundary';
import { STARTING_TEMPLATE } from '../overviews/startingTemplate';

const OverviewDocumentation: FC = () => {
  useScrollRestoration();

  return (
    <PageCenter margin={4} width="100%" textAlign="left">
      <ErrorBoundary>
        <HandlebarsMarkdown md={STARTING_TEMPLATE} />
      </ErrorBoundary>
    </PageCenter>
  );
};
export default OverviewDocumentation;
