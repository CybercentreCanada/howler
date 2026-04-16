import { Box, Stack } from '@mui/material';
import { SocketContext } from 'components/app/providers/SocketProvider';
import { memo, useContext, useEffect, type FC } from 'react';
import { Outlet, useParams } from 'react-router-dom';
import NotFoundPage from '../404';
import ErrorBoundary from '../ErrorBoundary';
import CaseDetails from './detail/CaseDetails';
import CaseSidebar from './detail/CaseSidebar';
import useCase from './hooks/useCase';

const CaseViewer: FC = () => {
  const params = useParams();
  const { case: _case, missing, update } = useCase({ caseId: params.id });
  const { emit, isOpen, fetchViewers } = useContext(SocketContext);

  useEffect(() => {
    if (!params.id) {
      return;
    }

    fetchViewers(params.id);

    if (isOpen()) {
      emit({
        broadcast: false,
        action: 'viewing',
        id: params.id
      });

      return () => {
        emit({
          broadcast: false,
          action: 'stop_viewing',
          id: params.id
        });
      };
    }
  }, [emit, params.id, isOpen, fetchViewers]);

  if (missing) {
    return <NotFoundPage />;
  }

  return (
    <ErrorBoundary>
      <Stack direction="row" height="100%">
        <CaseSidebar case={_case} update={updatedCase => update(updatedCase, false)} />
        <Box
          sx={{
            maxHeight: 'calc(100vh - 64px)',
            flex: 1,
            overflow: 'auto'
          }}
        >
          <ErrorBoundary>
            <Outlet context={_case} />
          </ErrorBoundary>
        </Box>
        <CaseDetails case={_case} />
      </Stack>
    </ErrorBoundary>
  );
};

export default memo(CaseViewer);
