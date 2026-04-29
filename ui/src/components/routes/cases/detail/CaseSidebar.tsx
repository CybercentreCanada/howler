import {
  DndContext,
  DragOverlay,
  MouseSensor,
  pointerWithin,
  TouchSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent
} from '@dnd-kit/core';
import { CalendarMonth, Circle, Dashboard, Dataset, Rule } from '@mui/icons-material';
import { alpha, Box, Card, Chip, Divider, LinearProgress, Skeleton, Stack, Typography, useTheme } from '@mui/material';
import api from 'api';
import useMyApi from 'components/hooks/useMyApi';
import dayjs from 'dayjs';
import type { Case } from 'models/entities/generated/Case';
import type { Item } from 'models/entities/generated/Item';
import { useCallback, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation } from 'react-router-dom';
import { ESCALATION_COLOR_MAP } from '../constants';
import CaseFolder from './sidebar/CaseFolder';
import FolderEntry from './sidebar/FolderEntry';
import RootDropZone from './sidebar/RootDropZone';
import type { Tree } from './sidebar/types';

interface CaseSidebarProps {
  case: Case;
  update: (newCase: Case) => void;
}

const CaseSidebar: FC<CaseSidebarProps> = ({ case: _case, update }) => {
  const { dispatchApi } = useMyApi();
  const { t } = useTranslation();
  const location = useLocation();
  const theme = useTheme();

  const sensors = useSensors(
    useSensor(MouseSensor, {
      activationConstraint: {
        distance: 5
      }
    }),
    useSensor(TouchSensor, {
      activationConstraint: {
        distance: 5
      }
    })
  );

  const [loading, setLoading] = useState(false);
  const [activeDragData, setActiveDragData] = useState<{ type: string; label: string } | null>(null);

  const handleDragStart = useCallback((event: DragStartEvent) => {
    const data = event.active.data.current;
    setActiveDragData({ type: data.type, label: data.label ?? '' });
  }, []);

  const navItemSx = useCallback(
    (isActive: boolean) => [
      {
        cursor: 'pointer',
        px: 1,
        py: 1,
        transition: theme.transitions.create('background', { duration: 100 }),
        color: `${theme.palette.text.primary} !important`,
        textDecoration: 'none',
        background: 'transparent',
        borderRight: `thin solid ${theme.palette.divider}`,
        '&:hover': {
          background: alpha(theme.palette.grey[600], 0.25)
        }
      },
      isActive && {
        background: alpha(theme.palette.grey[600], 0.15),
        borderRight: `3px solid ${theme.palette.primary.main}`
      }
    ],
    [
      theme.palette.divider,
      theme.palette.grey,
      theme.palette.primary.main,
      theme.palette.text.primary,
      theme.transitions
    ]
  );

  const handleDragEnd = useCallback(
    async (event: DragEndEvent) => {
      setActiveDragData(null);

      if (!_case) {
        return;
      }

      const { active, over } = event;

      if (!over?.data.current || !active?.data.current) {
        return;
      }

      const movingEntry: Item | Tree = active.data.current.entry;
      const movingType = active.data.current.type;

      if (!movingEntry?.path) {
        return;
      }

      const filename = movingEntry.path.split('/').pop();
      const targetPath = over.data.current.path ? `${over.data.current.path}/${filename}` : filename;

      if (!targetPath) {
        return;
      }

      if (targetPath === movingEntry.path) {
        return;
      }

      const items = _case.items.map(_item =>
        (
          movingType === 'folder'
            ? _item.path.startsWith(movingEntry.path)
            : _item.value === (movingEntry as Item).value
        )
          ? { ..._item, path: _item.path.replace(movingEntry.path, targetPath) }
          : _item
      );

      try {
        setLoading(true);

        const updatedCase = await dispatchApi(api.v2.case.put(_case.case_id, { items }));

        update(updatedCase);
      } finally {
        setLoading(false);
      }
    },
    [_case, dispatchApi, update]
  );

  return (
    <Box
      sx={{
        flex: 1,
        maxWidth: '350px',
        maxHeight: 'calc(100vh - 64px)',
        display: 'flex',
        flexDirection: 'column'
      }}
    >
      <Card sx={{ borderRadius: 0, px: 2, py: 1 }}>
        {_case?.title ? <Typography variant="body1">{_case.title}</Typography> : <Skeleton height={24} />}
        <Stack
          direction="row"
          spacing={1}
          alignItems="center"
          divider={<Circle color="disabled" sx={{ fontSize: '8px' }} />}
        >
          <Typography variant="caption" color="textSecondary">
            {t('started')}: {_case?.created ? dayjs(_case.created).toString() : <Skeleton height={14} />}
          </Typography>
          {_case?.escalation ? (
            <Chip color={ESCALATION_COLOR_MAP[_case.escalation]} label={t(_case.escalation)} />
          ) : (
            <Skeleton height={24} />
          )}
        </Stack>
      </Card>

      <Stack
        direction="row"
        alignItems="center"
        sx={navItemSx(location.pathname === `/cases/${_case?.case_id}`)}
        component={Link}
        to={`/cases/${_case?.case_id}`}
      >
        <Dashboard />
        <Typography sx={{ userSelect: 'none', pl: 0.5, textWrap: 'nowrap' }}>{t('page.cases.dashboard')}</Typography>
      </Stack>

      <Stack
        direction="row"
        alignItems="center"
        sx={navItemSx(location.pathname === `/cases/${_case?.case_id}/assets`)}
        component={Link}
        to={`/cases/${_case?.case_id}/assets`}
      >
        <Dataset />
        <Typography sx={{ userSelect: 'none', pl: 0.5, textWrap: 'nowrap' }}>{t('page.cases.assets')}</Typography>
      </Stack>

      <Stack
        direction="row"
        alignItems="center"
        sx={navItemSx(location.pathname === `/cases/${_case?.case_id}/timeline`)}
        component={Link}
        to={`/cases/${_case?.case_id}/timeline`}
      >
        <CalendarMonth />
        <Typography sx={{ userSelect: 'none', pl: 0.5, textWrap: 'nowrap' }}>{t('page.cases.timeline')}</Typography>
      </Stack>

      <Stack
        direction="row"
        alignItems="center"
        sx={navItemSx(location.pathname === `/cases/${_case?.case_id}/rules`)}
        component={Link}
        to={`/cases/${_case?.case_id}/rules`}
      >
        <Rule />
        <Typography sx={{ userSelect: 'none', pl: 0.5, textWrap: 'nowrap' }}>{t('page.cases.rules')}</Typography>
      </Stack>

      <Divider />

      {_case && (
        <Box
          flex={1}
          overflow="auto"
          width="100%"
          sx={{
            position: 'relative',
            borderRight: `thin solid ${theme.palette.divider}`
          }}
        >
          <Box position="absolute" sx={{ left: 0, right: 0 }}>
            <LinearProgress sx={{ mb: 0.5, opacity: +loading }} />
            <DndContext
              sensors={sensors}
              collisionDetection={pointerWithin}
              onDragStart={handleDragStart}
              onDragEnd={handleDragEnd}
            >
              <CaseFolder case={_case} onItemUpdated={update} />
              <RootDropZone caseId={_case.case_id} />
              <DragOverlay dropAnimation={null}>
                {activeDragData && (
                  <FolderEntry
                    caseId={null}
                    path=""
                    indent={0}
                    label={activeDragData.label}
                    itemType={activeDragData.type}
                  />
                )}
              </DragOverlay>
            </DndContext>
          </Box>
        </Box>
      )}
    </Box>
  );
};

export default CaseSidebar;
