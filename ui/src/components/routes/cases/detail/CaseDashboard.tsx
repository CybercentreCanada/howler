import { Grid, useTheme } from '@mui/material';
import api from 'api';
import useMyApi from 'components/hooks/useMyApi';
import dayjs from 'dayjs';
import type { Case } from 'models/entities/generated/Case';
import { useCallback, useEffect, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import AlertPanel from './AlertPanel';
import CaseAggregate from './CaseAggregate';
import CaseOverview from './CaseOverview';
import RelatedCasePanel from './RelatedCasePanel';
import TaskPanel from './TaskPanel';

const getDuration = (case_: Case) => {
  if (case_?.start) {
    return dayjs.duration(dayjs(case_?.end ?? new Date()).diff(dayjs(case_.start), 'minute'), 'minute');
  }
};

const CaseDashboard: FC<{ case?: Case; caseId?: string }> = ({ case: providedCase, caseId }) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const theme = useTheme();

  const [_case, setCase] = useState(providedCase);

  useEffect(() => {
    if (providedCase) {
      setCase(providedCase);
    }
  }, [providedCase]);

  useEffect(() => {
    if (caseId) {
      dispatchApi(api.v2.case.get(caseId), { throwError: false }).then(setCase);
    }
  }, [caseId, dispatchApi]);

  const updateCase = useCallback(
    async (_updatedCase: Partial<Case>) => {
      if (!_case?.case_id) {
        return;
      }

      try {
        setCase(await dispatchApi(api.v2.case.put(_case.case_id, _updatedCase)));
      } finally {
        return;
      }
    },
    [_case?.case_id, dispatchApi]
  );

  if (!_case) {
    return null;
  }

  return (
    <Grid container spacing={5} width="100%" px={3}>
      <Grid item xs={12}>
        <CaseOverview case={_case} updateCase={updateCase} />
      </Grid>
      <Grid item xs={12} md={6} xl={3}>
        <CaseAggregate
          icon="material-symbols:warning-rounded"
          iconColor={theme.palette.warning.main}
          field="howler.outline.threat"
          ids={_case.items.filter(item => ['hit', 'observable'].includes(item.type)).map(item => item.id)}
          subtitle={t('page.cases.dashboard.threat')}
        />
      </Grid>
      <Grid item xs={12} md={6} xl={3}>
        <CaseAggregate
          icon="material-symbols:group"
          iconColor={theme.palette.primary.main}
          field="howler.outline.target"
          ids={_case.items.filter(item => ['hit', 'observable'].includes(item.type)).map(item => item.id)}
          subtitle={t('page.cases.dashboard.target')}
        />
      </Grid>
      <Grid item xs={12} md={6} xl={3}>
        <CaseAggregate
          icon="fluent:number-symbol-24-filled"
          field="howler.outline.indicators"
          ids={_case.items.filter(item => ['hit', 'observable'].includes(item.type)).map(item => item.id)}
          subtitle={t('page.cases.dashboard.indicators')}
        />
      </Grid>
      <Grid item xs={12} md={6} xl={3}>
        <CaseAggregate
          icon="mingcute:heartbeat-line"
          iconColor={theme.palette.error.light}
          title={getDuration(_case).format('HH[h] mm[m]')}
          ids={_case.items.filter(item => ['hit', 'observable'].includes(item.type)).map(item => item.id)}
          subtitle={t('page.cases.dashboard.duration')}
        />
      </Grid>
      <Grid item xs={12}>
        <TaskPanel case={_case} updateCase={updateCase} />
      </Grid>
      <Grid item xs={12}>
        <AlertPanel case={_case} />
      </Grid>
      <Grid item xs={12}>
        <RelatedCasePanel case={_case} />
      </Grid>
    </Grid>
  );
};

export default CaseDashboard;
