import { Box, Divider, Pagination, Skeleton, Stack, Typography, useTheme } from '@mui/material';
import HitCard from 'components/elements/hit/HitCard';
import { HitLayout } from 'components/elements/hit/HitLayout';
import { chunk, uniq } from 'lodash-es';
import type { Case } from 'models/entities/generated/Case';
import { useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

const AlertPanel: FC<{ case: Case }> = ({ case: _case }) => {
  const theme = useTheme();
  const { t } = useTranslation();

  const [alertPage, setAlertPage] = useState(1);

  const alertPages = useMemo(
    () => chunk(uniq((_case?.items ?? []).filter(item => item.type === 'hit')), 5),
    [_case?.items]
  );

  if (!_case) {
    return <Skeleton height={240} />;
  }

  return (
    <Stack spacing={1}>
      <Stack direction="row">
        <Typography flex={1} variant="h4">
          {t('page.cases.dashboard.alerts')}
        </Typography>

        <Pagination count={alertPages.length} page={alertPage} onChange={(_, page) => setAlertPage(page)} />
      </Stack>
      <Divider />
      {alertPages?.length > 0 &&
        alertPages[alertPage - 1].map(item => (
          <Box key={item.path} position="relative">
            <HitCard layout={HitLayout.DENSE} id={item.value} lazy />
            <Box
              component={Link}
              to={item.path}
              sx={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: '100%',
                cursor: 'pointer',
                zIndex: 100,
                borderRadius: '4px',
                '&:hover': {
                  background: theme.palette.divider,
                  border: `thin solid ${theme.palette.primary.light}`
                }
              }}
            />
          </Box>
        ))}
    </Stack>
  );
};

export default AlertPanel;
