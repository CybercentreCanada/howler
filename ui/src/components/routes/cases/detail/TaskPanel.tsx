import { Add, ExpandLess, ExpandMore } from '@mui/icons-material';
import { Autocomplete, Chip, Divider, Skeleton, Stack, TextField, Tooltip, Typography } from '@mui/material';
import api from 'api';
import useMyApi from 'components/hooks/useMyApi';
import type { Case } from 'models/entities/generated/Case';
import type { Task } from 'models/entities/generated/Task';
import { useEffect, useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import CaseTask from './CaseTask';

/** Maximum number of child cases auto-loaded for task aggregation. */
const MAX_CHILD_CASES = 10;

const TaskPanel: FC<{ case: Case; updateCase: (_case: Partial<Case>) => Promise<void> }> = ({
  case: _case,
  updateCase
}) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();

  const [addingTask, setAddingTask] = useState(false);
  const [childCases, setChildCases] = useState<Case[]>([]);
  const [showChildTasks, setShowChildTasks] = useState(true);
  const [selectedChildIds, setSelectedChildIds] = useState<string[] | null>(null);

  // Collect the IDs for all child case items (up to MAX_CHILD_CASES)
  const childCaseItems = useMemo(
    () => (_case?.items ?? []).filter(item => item.type === 'case' && !!item.value).slice(0, MAX_CHILD_CASES),
    [_case?.items]
  );

  // Fetch child case data whenever the parent case changes
  useEffect(() => {
    if (childCaseItems.length === 0) {
      setChildCases([]);
      setSelectedChildIds([]);
      return;
    }

    let cancelled = false;

    void dispatchApi(
      api.v2.search.post('case', { query: `case_id:(${childCaseItems.map(item => item.value).join(' OR ')})` }),
      { throwError: false }
    )
      .then(results => results.items)
      .then(results => {
        if (!cancelled) {
          setChildCases(results);
          // Default: all child cases selected
          if (selectedChildIds === null) {
            setSelectedChildIds(results.map(r => r.case_id));
          }
        }
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [childCaseItems, dispatchApi]);

  // Child cases available as filter options
  const childCaseOptions = useMemo(() => childCases.map(c => c.case_id), [childCases]);

  // Child cases whose tasks are currently visible
  const visibleChildCases = useMemo(
    () => (showChildTasks ? childCases.filter(c => (selectedChildIds ?? []).includes(c.case_id)) : []),
    [showChildTasks, childCases, selectedChildIds]
  );

  const onEdit = (task?: Task) => async (newTask: Partial<Task>) => {
    if (task) {
      await updateCase({
        tasks: _case.tasks.map(_task => {
          if (_task.id !== task.id) {
            return _task;
          }

          return {
            ..._task,
            ...newTask
          };
        })
      });
    } else {
      await updateCase({
        tasks: [..._case.tasks, newTask]
      });
    }
  };

  if (!_case) {
    return <Skeleton height={240} />;
  }

  const hasChildCases = childCases.length > 0;

  return (
    <Stack spacing={1}>
      {/* Header row */}
      <Stack direction="row" alignItems="center" spacing={1}>
        <Typography flex={1} variant="h4">
          {t('page.cases.dashboard.tasks')}
        </Typography>

        {hasChildCases && (
          <>
            {/* Per-child-case filter */}
            <Autocomplete
              multiple
              size="small"
              disableCloseOnSelect
              options={childCaseOptions}
              value={selectedChildIds ?? []}
              onChange={(_ev, val) => setSelectedChildIds(val)}
              getOptionLabel={id => childCases.find(c => c.case_id === id)?.title ?? id}
              renderTags={(vals, getTagProps) =>
                vals.map((id, index) => {
                  const { key, ...tagProps } = getTagProps({ index });
                  return (
                    <Chip
                      key={key}
                      {...tagProps}
                      size="small"
                      label={childCases.find(c => c.case_id === id)?.title ?? id}
                    />
                  );
                })
              }
              renderInput={params => (
                <TextField
                  {...params}
                  size="small"
                  placeholder={selectedChildIds?.length === 0 ? t('page.cases.dashboard.tasks.filter_cases') : ''}
                  sx={{ minWidth: 180 }}
                />
              )}
              sx={{ minWidth: 180 }}
            />

            {/* Toggle child task visibility */}
            <Tooltip
              title={t(
                showChildTasks ? 'page.cases.dashboard.tasks.hide_child' : 'page.cases.dashboard.tasks.show_child'
              )}
            >
              <Chip
                size="small"
                variant={showChildTasks ? 'filled' : 'outlined'}
                label={t('page.cases.dashboard.tasks.child_cases')}
                icon={showChildTasks ? <ExpandLess fontSize="small" /> : <ExpandMore fontSize="small" />}
                onClick={() => setShowChildTasks(v => !v)}
                clickable
              />
            </Tooltip>
          </>
        )}
      </Stack>
      <Divider />

      {/* Umbrella case tasks */}
      {_case.tasks.map(task => (
        <CaseTask
          key={task.id}
          task={task}
          case={_case}
          onEdit={onEdit(task)}
          onDelete={() => updateCase({ tasks: _case.tasks.filter(_task => _task.id !== task.id) })}
        />
      ))}
      {addingTask && (
        <CaseTask
          newTask
          case={_case}
          onEdit={async task => {
            await onEdit()(task);
            setAddingTask(false);
          }}
          onDelete={async () => setAddingTask(false)}
        />
      )}
      <Stack
        onClick={() => setAddingTask(true)}
        direction="row"
        spacing={2}
        sx={theme => ({
          borderStyle: 'dashed',
          borderColor: theme.palette.text.secondary,
          borderWidth: '0.15rem',
          borderRadius: '0.15rem',
          opacity: 0.3,
          justifyContent: 'center',
          alignItems: 'center',
          padding: 1,
          transition: theme.transitions.create('opacity'),
          '&:hover': {
            opacity: 1,
            cursor: 'pointer'
          }
        })}
      >
        <Add />
        <Typography>{t('page.cases.dashboard.tasks.add')}</Typography>
      </Stack>

      {/* Child case tasks */}
      {visibleChildCases.map(child => (
        <Stack key={child.case_id} spacing={1}>
          <Divider>
            <Chip
              component={Link}
              to={`/cases/${child.case_id}`}
              clickable
              size="small"
              label={child.title}
              variant="outlined"
            />
          </Divider>
          {child.tasks.length === 0 ? (
            <Typography variant="caption" color="textSecondary" sx={{ pl: 1 }}>
              {t('page.cases.dashboard.tasks.child.empty')}
            </Typography>
          ) : (
            child.tasks.map(task => <CaseTask key={task.id} task={task} case={child} readOnly />)
          )}
        </Stack>
      ))}
    </Stack>
  );
};

export default TaskPanel;
