import { Grid, useTheme } from '@mui/material';
import api from 'api';
import { RecordContext } from 'components/app/providers/RecordProvider';
import useMyApi from 'components/hooks/useMyApi';
import dayjs from 'dayjs';
import { difference, get, isNil } from 'lodash-es';
import type { Case } from 'models/entities/generated/Case';
import { useEffect, useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { useOutletContext } from 'react-router-dom';
import { useContextSelector } from 'use-context-selector';
import useCase from '../hooks/useCase';
import CaseAggregate from './aggregates/CaseAggregate';
import AlertPanel from './AlertPanel';
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
    return dayjs
      .duration(dayjs(case_?.end ?? new Date()).diff(dayjs(case_.start), 'minute'), 'minute')
      .format('HH[h] mm[m]');
  }

  return '--';
};

const CaseDashboard: FC<{ case?: Case; caseId?: string }> = ({ case: providedCase, caseId }) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const theme = useTheme();
  const routeCase = useOutletContext<Case>();
  const { case: _case, update: updateCase } = useCase({ case: providedCase ?? routeCase, caseId });

  const [invalidIds, setInvalidIds] = useState<string[]>([]);

  const ids = useMemo(
    () =>
      (_case?.items ?? [])
        .filter(item => ['hit', 'observable'].includes(item.type))
        .map(item => item.value)
        .filter(val => !!val),
    [_case?.items]
  );

  const records = useContextSelector(RecordContext, ctx => ctx.records);
  const loadRecords = useContextSelector(RecordContext, ctx => ctx.loadRecords);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const caseRecords = useMemo(() => Object.fromEntries(ids.map(id => [id, records[id]])), [ids, records]);

  useEffect(() => {
    const missingIds = Object.entries(caseRecords)
      .filter(([id, record]) => !invalidIds.includes(id) && isNil(record))
      .map(([id]) => id);

    if (missingIds.length < 1) {
      return;
    }

    dispatchApi(
      api.v2.search.post(['hit', 'observable'], {
        query: `howler.id:(${missingIds.join(' OR ')})`,
        metadata: ['template', 'analytic']
      })
    ).then(response => {
      loadRecords(response.items);

      setInvalidIds(
        difference(
          missingIds,
          response.items.map(record => record.howler.id)
        )
      );
    });
  }, [caseRecords, dispatchApi, ids, invalidIds, loadRecords]);

  if (!_case) {
    return null;
  }

  return (
    <Grid container spacing={5} width="100%" px={2}>
      <Grid item xs={12}>
        <CaseOverview case={_case} updateCase={updateCase} />
      </Grid>
      {AGGREGATE_FIELDS.map(([field, icon, iconColor, subtitle]) => (
        <Grid key={field} item xs={12} md={6} xl={3}>
          <CaseAggregate
            icon={icon}
            iconColor={iconColor && get(theme.palette, iconColor)}
            field={field}
            records={Object.values(caseRecords)}
            subtitle={t(subtitle)}
          />
        </Grid>
      ))}
      <Grid item xs={12} md={6} xl={3}>
        <CaseAggregate
          icon="mingcute:heartbeat-line"
          iconColor={theme.palette.error.light}
          title={getDuration(_case)}
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
