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
import { useEffect, useId, useMemo, useRef, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import { sanitizeLuceneQuery } from 'utils/stringUtils';
import { twitterShort } from 'utils/utils';

const SEARCH_PAGE_SIZE = 150;
const MAX_SEARCH_PAGES = 3;
type TaskFilter = 'all' | 'complete' | 'incomplete';

export interface TasksSettings {
  taskFilter?: TaskFilter;
}

interface TasksPanelProps extends TasksSettings {
  panelId?: string;
  refreshTick?: symbol;
  onRefreshComplete?: (panelId: string, refreshTick: symbol) => void;
}

const TasksPanel: FC<TasksPanelProps> = ({
  taskFilter: initialTaskFilter = 'incomplete',
  panelId = 'tasks-panel',
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
  const activeRefreshTick = useRef<symbol | undefined>(undefined);
  useEffect(() => {
    const controller = new AbortController();
    let refreshComplete = false;
    const completeRefresh = () => {
      if (refreshTick && !refreshComplete) {
        refreshComplete = true;
        if (activeRefreshTick.current === refreshTick) {
          activeRefreshTick.current = undefined;
        }
        onRefreshComplete?.(panelId, refreshTick);
      }
    };

    if (refreshTick) {
      activeRefreshTick.current = refreshTick;
    }

    if (!username) {
      setCases([]);
      setLoading(false);
      completeRefresh();
      return;
    }

    setLoading(true);
    setError(false);

    const loadCases = async () => {
      const allCases: Case[] = [];
      let offset = 0;
      let total = 0;
      let page = 0;

      try {
        do {
          const response = await dispatchApi(
            api.v2.search.post<Case>(
              'case',
              {
                query: 'case_id:*',
                filters: [`tasks.assignment:"${sanitizeLuceneQuery(username)}"`],
                rows: SEARCH_PAGE_SIZE,
                offset,
                sort: 'created desc'
              },
              controller.signal
            ),
            { showError: false }
          );

          if (controller.signal.aborted) {
            return;
          }

          if (!response) {
            break;
          }

          allCases.push(...response.items);
          total = response.total;
          offset += response.items.length;
          page += 1;

          if (response.items.length === 0) {
            break;
          }
        } while (offset < total && page < MAX_SEARCH_PAGES);

        if (!controller.signal.aborted) {
          setCases(allCases);
        }
      } catch {
        if (!controller.signal.aborted) {
          setError(true);
          setCases([]);
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
          completeRefresh();
        }
      }
    };

    void loadCases();

    return () => {
      controller.abort();
    };
  }, [dispatchApi, onRefreshComplete, panelId, refreshTick, username]);

  useEffect(
    () => () => {
      if (activeRefreshTick.current) {
        onRefreshComplete?.(panelId, activeRefreshTick.current);
        activeRefreshTick.current = undefined;
      }
    },
    [onRefreshComplete, panelId]
  );

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
