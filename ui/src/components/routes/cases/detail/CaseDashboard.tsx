import { Grid, useTheme } from '@mui/material';
import api from 'api';
import useMyApi from 'components/hooks/useMyApi';
import dayjs from 'dayjs';
import { get } from 'lodash-es';
import type { Case } from 'models/entities/generated/Case';
import type { Hit } from 'models/entities/generated/Hit';
import type { Observable } from 'models/entities/generated/Observable';
import { useCallback, useEffect, useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import AlertPanel from './AlertPanel';
import CaseAggregate from './CaseAggregate';
import CaseOverview from './CaseOverview';
import RelatedCasePanel from './RelatedCasePanel';
import TaskPanel from './TaskPanel';

const AGGREGATE_FIELDS = [
  ['howler.outline.threat', 'material-symbols:warning-rounded', 'warning.main', 'page.cases.dashboard.threat'],
  ['howler.outline.target', 'material-symbols:group', 'primary.main', 'page.cases.dashboard.target'],
  ['howler.outline.indicators', 'fluent:number-symbol-24-filled', null, 'page.cases.dashboard.indicators']
];

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
  const [records, setRecords] = useState<Partial<Hit | Observable>[] | null>(null);

  const ids = useMemo(
    () => (_case?.items ?? []).filter(item => ['hit', 'observable'].includes(item.type)).map(item => item.id),
    [_case?.items]
  );

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

  useEffect(() => {
    if (ids?.length < 1) {
      return;
    }

    dispatchApi(
      api.v2.search.post(['hit', 'observable'], {
        query: `howler.id:(${ids?.join(' OR ') || '*'})`,
        fl: AGGREGATE_FIELDS.map(([field]) => field).join(',')
      })
    ).then(response => setRecords(response.items));
  }, [dispatchApi, ids]);

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
      {AGGREGATE_FIELDS.map(([field, icon, iconColor, subtitle]) => (
        <Grid key={field} item xs={12} md={6} xl={3}>
          <CaseAggregate
            icon={icon}
            iconColor={iconColor && get(theme.palette, iconColor)}
            field={field}
            records={records}
            subtitle={t(subtitle)}
          />
        </Grid>
      ))}
      <Grid item xs={12} md={6} xl={3}>
        <CaseAggregate
          icon="mingcute:heartbeat-line"
          iconColor={theme.palette.error.light}
          title={getDuration(_case).format('HH[h] mm[m]')}
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
