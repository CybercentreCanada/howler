import { Box, Stack } from '@mui/material';
import { memo, type FC } from 'react';
import { useParams } from 'react-router-dom';
import NotFoundPage from '../404';
import ErrorBoundary from '../ErrorBoundary';
import CaseDashboard from './detail/CaseDashboard';
import CaseDetails from './detail/CaseDetails';
import CaseSidebar from './detail/CaseSidebar';
import ItemPage from './detail/ItemPage';
import useCase from './hooks/useCase';

const CaseViewer: FC = () => {
  const params = useParams();
  const { case: _case, missing } = useCase({ caseId: params.id });

  if (missing) {
    return <NotFoundPage />;
  }

  return (
    <Stack direction="row" height="100%">
      <CaseSidebar case={_case} />
      <Box
        sx={{
          maxHeight: 'calc(100vh - 64px)',
          flex: 1,
          overflow: 'auto'
        }}
      >
        <ErrorBoundary>
          {!_case || location.pathname.endsWith(_case.case_id) ? (
            <CaseDashboard case={_case} />
          ) : (
            <ItemPage case={_case} />
          )}
        </ErrorBoundary>
      </Box>
      <CaseDetails case={_case} />
    </Stack>
  );
};

export default memo(CaseViewer);
