import { Box, Divider, Pagination, Skeleton, Stack, Typography, useTheme } from '@mui/material';
import { chunk, uniq } from 'lodash-es';
import type { Case } from 'models/entities/generated/Case';
import { useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import CaseCard from '../../../elements/case/CaseCard';

const RelatedCasePanel: FC<{ case: Case }> = ({ case: _case }) => {
  const { t } = useTranslation();
  const theme = useTheme();
  const [casePage, setCasePage] = useState(1);

  const casePages = useMemo(
    () => chunk(uniq((_case?.items ?? []).filter(item => item.type === 'case')), 5),
    [_case?.items]
  );

  if (!_case) {
    return <Skeleton height={240} />;
  }

  return (
    <Stack spacing={1}>
      <Stack direction="row">
        <Typography flex={1} variant="h4">
          {t('page.cases.dashboard.cases')}
        </Typography>

        <Pagination count={casePages.length} page={casePage} onChange={(_, page) => setCasePage(page)} />
      </Stack>
      <Divider />
      {casePages[casePage - 1]?.map(item => (
        <Box key={item.id} position="relative">
          <CaseCard caseId={item.id} />
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

export default RelatedCasePanel;
