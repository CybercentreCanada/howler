import {
  Box,
  Card,
  CardContent,
  CardHeader,
  Divider,
  Grid,
  Pagination,
  Stack,
  Typography,
  useTheme
} from '@mui/material';
import Markdown from 'components/elements/display/Markdown';
import HitCard from 'components/elements/hit/HitCard';
import { HitLayout } from 'components/elements/hit/HitLayout';
import dayjs from 'dayjs';
import { chunk, uniq } from 'lodash-es';
import type { Case } from 'models/entities/generated/Case';
import { useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import CaseAggregate from './CaseAggregate';

const getDuration = (case_: Case) => {
  if (case_?.start) {
    return dayjs.duration(dayjs(case_?.end ?? new Date()).diff(dayjs(case_.start), 'minute'), 'minute');
  }
};

const CaseDashboard: FC<{ case: Case }> = ({ case: case_ }) => {
  const { t } = useTranslation();
  const theme = useTheme();

  const [alertPage, setAlertPage] = useState(1);

  const alertPages = useMemo(
    () => chunk(uniq((case_?.items ?? []).filter(item => item.type === 'hit')), 5),
    [case_?.items]
  );

  if (!case_) {
    return null;
  }

  return (
    <Grid container spacing={5} width="100%" px={3}>
      <Grid item xs={12}>
        <Card>
          <CardHeader title={case_.title} subheader={case_.summary} />
          <Divider />
          <CardContent>
            <Markdown md={case_.overview} />
          </CardContent>
        </Card>
      </Grid>
      <Grid item xs={3}>
        <CaseAggregate
          icon="material-symbols:warning-rounded"
          iconColor={theme.palette.warning.main}
          field="howler.outline.threat"
          ids={case_.items.filter(item => ['hit', 'observable'].includes(item.type)).map(item => item.id)}
          subtitle={t('page.cases.dashboard.threat')}
        />
      </Grid>
      <Grid item xs={3}>
        <CaseAggregate
          icon="material-symbols:group"
          iconColor={theme.palette.primary.main}
          field="howler.outline.target"
          ids={case_.items.filter(item => ['hit', 'observable'].includes(item.type)).map(item => item.id)}
          subtitle={t('page.cases.dashboard.target')}
        />
      </Grid>
      <Grid item xs={3}>
        <CaseAggregate
          icon="fluent:number-symbol-24-filled"
          field="howler.outline.indicators"
          ids={case_.items.filter(item => ['hit', 'observable'].includes(item.type)).map(item => item.id)}
          subtitle={t('page.cases.dashboard.indicators')}
        />
      </Grid>
      <Grid item xs={3}>
        <CaseAggregate
          icon="mingcute:heartbeat-line"
          iconColor={theme.palette.error.light}
          title={getDuration(case_).format('HH[h] mm[m]')}
          ids={case_.items.filter(item => ['hit', 'observable'].includes(item.type)).map(item => item.id)}
          subtitle={t('page.cases.dashboard.duration')}
        />
      </Grid>
      <Grid item xs={12}>
        <Stack spacing={1}>
          <Stack direction="row">
            <Typography flex={1} variant="h4">
              {t('page.cases.dashboard.alerts')}
            </Typography>

            <Pagination count={alertPages.length} page={alertPage} onChange={(_, page) => setAlertPage(page)} />
          </Stack>
          <Divider />
          {alertPages[alertPage - 1].map(item => (
            <Box key={item.id} position="relative">
              <HitCard layout={HitLayout.DENSE} id={item.id} />
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
      </Grid>
    </Grid>
  );
};

export default CaseDashboard;
