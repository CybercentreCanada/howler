import { Box, Stack } from '@mui/material';
import api from 'api';
import useMyApi from 'components/hooks/useMyApi';
import type { Case } from 'models/entities/generated/Case';
import { memo, useEffect, useState, type FC } from 'react';
import { useParams } from 'react-router-dom';
import NotFoundPage from '../404';
import CaseDashboard from './detail/CaseDashboard';
import CaseSidebar from './detail/CaseSidebar';
import ItemPage from './detail/ItemPage';

const CaseViewer: FC = () => {
  const params = useParams();
  const { dispatchApi } = useMyApi();

  const [_case, setCase] = useState<Case>();
  const [loading, setLoading] = useState(false);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!params.id) {
      return;
    }

    setLoading(true);

    dispatchApi(api.v2.case.get(params.id))
      .then(_dossier => {
        setCase(_dossier);
      })
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false));
  }, [dispatchApi, params.id]);

  if (notFound) {
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
        {!_case || location.pathname.endsWith(_case.case_id) ? (
          <CaseDashboard case={_case} />
        ) : (
          <ItemPage case={_case} />
        )}
      </Box>
    </Stack>
  );
};

export default memo(CaseViewer);
