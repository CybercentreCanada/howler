import { HourglassBottom, UpdateOutlined } from '@mui/icons-material';
import {
  Alert,
  Button,
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
import type { TaskSearchFilter, TaskSearchItem } from 'api/v2/task';
import StatusIcon from 'components/elements/case/StatusIcon';
import useMyApi from 'components/hooks/useMyApi';
import CaseTask from 'components/routes/cases/detail/CaseTask';
import dayjs from 'dayjs';
import type { Case } from 'models/entities/generated/Case';
import type { HowlerUser } from 'models/entities/HowlerUser';
import type { Task } from 'models/entities/generated/Task';
import { useEffect, useId, useMemo, useRef, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import { twitterShort } from 'utils/utils';

const TASKS_PER_PAGE = 25;
type TaskFilter = TaskSearchFilter;

const API_FILTER: Record<TaskFilter, TaskSearchFilter> = {
  all: 'all',
  complete: 'complete',
  incomplete: 'incomplete'
};

export interface TasksSettings {
  taskFilter?: TaskFilter;
}

interface TasksPanelProps extends TasksSettings {
  panelId?: string;
  refreshTick?: symbol;
  onRefreshComplete?: (panelId: string, refreshTick: symbol) => void;
}

const groupTasksByCase = (items: TaskSearchItem[]) => {
  const groups: { case: Case; tasks: Task[] }[] = [];
  const groupsByCaseId = new Map<string, { case: Case; tasks: Task[] }>();

  items.forEach(({ task, case: _case }, index) => {
    const caseId = _case.case_id ?? `missing-case-id-${index}`;
    let group = groupsByCaseId.get(caseId);

    if (!group) {
      group = { case: _case, tasks: [] };
      groupsByCaseId.set(caseId, group);
      groups.push(group);
    }

    group.tasks.push(task);
  });

  return groups;
};

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

  const [items, setItems] = useState<TaskSearchItem[]>([]);
  const [taskFilter, setTaskFilter] = useState<TaskFilter>(initialTaskFilter);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const activeRefreshTick = useRef<symbol | undefined>(undefined);
  const lastReceivedRefreshTick = useRef<symbol | undefined>(undefined);

  useEffect(() => {
    const controller = new AbortController();
    let refreshComplete = false;
    let retryingPreviousPage = false;

    if (refreshTick && lastReceivedRefreshTick.current !== refreshTick) {
      activeRefreshTick.current = refreshTick;
      lastReceivedRefreshTick.current = refreshTick;
    }

    const completeRefresh = () => {
      if (refreshTick && !refreshComplete && activeRefreshTick.current === refreshTick) {
        refreshComplete = true;
        activeRefreshTick.current = undefined;
        onRefreshComplete?.(panelId, refreshTick);
      }
    };

    if (!username) {
      completeRefresh();
      return;
    }

    setLoading(true);
    setError(false);

    const loadTasks = async () => {
      try {
        const response = await dispatchApi(
          api.v2.task.search(
            {
              offset,
              rows: TASKS_PER_PAGE,
              filter: API_FILTER[taskFilter]
            },
            controller.signal
          ),
          { showError: false }
        );

        if (controller.signal.aborted) {
          return;
        }

        if (offset > 0 && (response?.items.length ?? 0) === 0) {
          retryingPreviousPage = true;
          setOffset(currentOffset => Math.max(0, currentOffset - TASKS_PER_PAGE));
          return;
        }

        setItems(response?.items ?? []);
        setHasMore(response?.has_more ?? false);
      } catch {
        if (!controller.signal.aborted) {
          setError(true);
          setItems([]);
          setHasMore(false);
        }
      } finally {
        if (!controller.signal.aborted && !retryingPreviousPage) {
          setLoading(false);
          completeRefresh();
        }
      }
    };

    void loadTasks();

    return () => {
      controller.abort();
    };
  }, [dispatchApi, offset, onRefreshComplete, panelId, refreshTick, taskFilter, username]);

  useEffect(
    () => () => {
      if (activeRefreshTick.current) {
        const pendingRefreshTick = activeRefreshTick.current;
        activeRefreshTick.current = undefined;
        onRefreshComplete?.(panelId, pendingRefreshTick);
      }
    },
    [onRefreshComplete, panelId]
  );

  const groupedTasks = useMemo(() => (username ? groupTasksByCase(items) : []), [items, username]);
  const isLoading = Boolean(username) && loading;

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
                onChange={event => {
                  setTaskFilter(event.target.value as TaskFilter);
                  setOffset(0);
                }}
              >
                <MenuItem value="incomplete">{t('route.home.tasks.filter.incomplete')}</MenuItem>
                <MenuItem value="complete">{t('route.home.tasks.filter.complete')}</MenuItem>
                <MenuItem value="all">{t('route.home.tasks.filter.all')}</MenuItem>
              </Select>
            </FormControl>
          </Stack>
          {!username ? (
            <AppListEmpty />
          ) : error ? (
            <Alert severity="error">{t('route.home.tasks.error')}</Alert>
          ) : isLoading ? (
            <Stack alignItems="center" py={3}>
              <CircularProgress size={28} />
            </Stack>
          ) : groupedTasks.length > 0 ? (
            groupedTasks.map(({ case: _case, tasks }) => {
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
          <Stack direction="row" justifyContent="space-between">
            <Button
              disabled={!username || isLoading || offset === 0}
              onClick={() => setOffset(currentOffset => Math.max(0, currentOffset - TASKS_PER_PAGE))}
            >
              {t('route.home.tasks.previous')}
            </Button>
            <Button
              disabled={!username || isLoading || !hasMore}
              onClick={() => setOffset(currentOffset => currentOffset + TASKS_PER_PAGE)}
            >
              {t('route.home.tasks.next')}
            </Button>
          </Stack>
        </Stack>
      </CardContent>
    </Card>
  );
};

export default TasksPanel;
