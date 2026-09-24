import { HourglassBottom, UpdateOutlined } from '@mui/icons-material';
import {
  Alert,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Tooltip,
  Typography
} from '@mui/material';
import { AppListEmpty, useAppUser } from '@tui/core';
import api from 'api';
import StatusIcon from 'components/elements/case/StatusIcon';
import useMyApi from 'components/hooks/useMyApi';
import CaseTask from 'components/routes/cases/detail/CaseTask';
import dayjs from 'dayjs';
import type { Case } from 'models/entities/generated/Case';
import type { HowlerUser } from 'models/entities/HowlerUser';
import { useCallback, useEffect, useId, useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import { sanitizeLuceneQuery } from 'utils/stringUtils';
import { twitterShort } from 'utils/utils';

const SEARCH_PAGE_SIZE = 150;
type TaskFilter = 'all' | 'complete' | 'incomplete';

export interface TasksSettings {
  taskFilter?: TaskFilter;
}

interface TasksPanelProps extends TasksSettings {
  refreshTick?: symbol;
  onRefreshComplete?: () => void;
}

const TasksPanel: FC<TasksPanelProps> = ({
  taskFilter: initialTaskFilter = 'incomplete',
  refreshTick,
  onRefreshComplete
}) => {
  const { t } = useTranslation();
  const { user } = useAppUser<HowlerUser>();
  const username = user?.username;
  const { dispatchApi } = useMyApi();
  const filterId = useId();

  const [cases, setCases] = useState<Case[]>([]);
  const [taskFilter, setTaskFilter] = useState<TaskFilter>(initialTaskFilter);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  const loadCases = useCallback(async () => {
    if (!username) {
      setCases([]);
      onRefreshComplete?.();
      return;
    }

    setLoading(true);
    setError(false);

    const allCases: Case[] = [];
    let offset = 0;
    let total = 0;

    try {
      do {
        const response = await dispatchApi(
          api.v2.search.post<Case>('case', {
            query: 'case_id:*',
            filters: [`tasks.assignment:"${sanitizeLuceneQuery(username)}"`],
            rows: SEARCH_PAGE_SIZE,
            offset,
            sort: 'created desc'
          }),
          { showError: false }
        );

        if (!response) {
          break;
        }

        allCases.push(...response.items);
        total = response.total;
        offset += response.items.length;

        if (response.items.length === 0) {
          break;
        }
      } while (offset < total);

      setCases(allCases);
    } catch {
      setError(true);
      setCases([]);
    } finally {
      setLoading(false);
      onRefreshComplete?.();
    }
  }, [dispatchApi, onRefreshComplete, username]);

  useEffect(() => {
    void loadCases();
  }, [loadCases, refreshTick]);

  const visibleCases = useMemo(
    () =>
      cases
        .map(_case => ({
          case: _case,
          tasks: (_case.tasks ?? []).filter(task => {
            if (task.assignment !== username) {
              return false;
            }

            if (taskFilter === 'all') {
              return true;
            }

            return taskFilter === 'complete' ? task.complete : !task.complete;
          })
        }))
        .filter(group => group.tasks.length > 0),
    [cases, taskFilter, username]
  );

  return (
    <Card variant="outlined" sx={{ height: '100%' }}>
      <CardContent sx={{ height: '100%' }}>
        <Stack spacing={1}>
          <Stack direction="row" spacing={1} alignItems="center">
            <Typography variant="h6">{t('route.home.tasks.title')}</Typography>
            <div style={{ flex: 1 }} />
            <FormControl size="small" sx={{ minWidth: 150 }}>
              <InputLabel id={filterId}>{t('route.home.tasks.filter')}</InputLabel>
              <Select
                labelId={filterId}
                value={taskFilter}
                label={t('route.home.tasks.filter')}
                onChange={event => setTaskFilter(event.target.value as TaskFilter)}
              >
                <MenuItem value="incomplete">{t('route.home.tasks.filter.incomplete')}</MenuItem>
                <MenuItem value="complete">{t('route.home.tasks.filter.complete')}</MenuItem>
                <MenuItem value="all">{t('route.home.tasks.filter.all')}</MenuItem>
              </Select>
            </FormControl>
          </Stack>
          {error ? (
            <Alert severity="error">{t('route.home.tasks.error')}</Alert>
          ) : loading ? (
            <Stack alignItems="center" py={3}>
              <CircularProgress size={28} />
            </Stack>
          ) : visibleCases.length > 0 ? (
            visibleCases.map(({ case: _case, tasks }) => {
              const status = _case.status ?? 'open';

              return (
                <Stack key={_case.case_id} spacing={0.5}>
                  <Stack direction="row" spacing={1}>
                    <Typography
                      component={Link}
                      to={`/cases/${_case.case_id}`}
                      color="text.primary"
                      sx={{
                        alignItems: 'center',
                        display: 'flex',
                        gap: 0.5,
                        textDecoration: 'none'
                      }}
                    >
                      {_case.title ?? _case.case_id}
                      <StatusIcon status={status} />
                    </Typography>

                    <div style={{ flex: 1 }} />

                    {_case.start && _case.end && (
                      <Tooltip title={dayjs(_case.updated).toString()}>
                        <Chip
                          icon={<HourglassBottom fontSize="small" />}
                          size="small"
                          label={twitterShort(_case.start) + ' - ' + twitterShort(_case.end)}
                        />
                      </Tooltip>
                    )}

                    <Tooltip title={dayjs(_case.updated).toString()}>
                      <Chip
                        icon={<UpdateOutlined fontSize="small" />}
                        size="small"
                        label={twitterShort(_case.updated!)}
                      />
                    </Tooltip>
                  </Stack>
                  {tasks.map(task => (
                    <CaseTask key={`${_case.case_id}-${task.id ?? task.summary}`} case={_case} task={task} readOnly />
                  ))}
                </Stack>
              );
            })
          ) : (
            <AppListEmpty />
          )}
        </Stack>
      </CardContent>
    </Card>
  );
};

export default TasksPanel;
