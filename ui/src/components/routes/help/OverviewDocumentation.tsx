import PageCenter from 'commons/components/pages/PageCenter';
import HandlebarsMarkdown from 'components/elements/display/HandlebarsMarkdown';
import { useScrollRestoration } from 'components/hooks/useScrollRestoration';
import { type FC } from 'react';
import ErrorBoundary from '../ErrorBoundary';
import { useStartingTemplate } from '../overviews/startingTemplate';

const OverviewDocumentation: FC = () => {
  useScrollRestoration();

  const template = useStartingTemplate();

  return (
    <PageCenter margin={4} width="100%" textAlign="left">
      <ErrorBoundary>
        <HandlebarsMarkdown md={template} />
      </ErrorBoundary>
    </PageCenter>
  );
};
export default OverviewDocumentation;
