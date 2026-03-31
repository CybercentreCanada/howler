import {
  DndContext,
  MouseSensor,
  pointerWithin,
  TouchSensor,
  useSensor,
  useSensors,
  type DragEndEvent
} from '@dnd-kit/core';
import { CalendarMonth, Circle, Dashboard, Dataset } from '@mui/icons-material';
import { alpha, Box, Card, Chip, Divider, Skeleton, Stack, Typography, useTheme } from '@mui/material';
import dayjs from 'dayjs';
import type { Case } from 'models/entities/generated/Case';
import { useCallback, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation } from 'react-router-dom';
import { ESCALATION_COLOR_MAP } from '../constants';
import CaseFolder from './sidebar/CaseFolder';

interface CaseSidebarProps {
  case: Case;
  update: (newCase: Case) => void;
}

const CaseSidebar: FC<CaseSidebarProps> = ({ case: _case, update }) => {
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
    (event: DragEndEvent) => {
      const { active, over } = event;

      if (!over) {
        return;
      }

      const movingItem = active.data.current.item;
      const newPath = `${over.data.current.path}/${movingItem.path.split('/').pop()}`;

      update({
        items: _case.items.map(_item => (_item.path === movingItem.path ? { ...movingItem, path: newPath } : _item))
      });
    },
    [_case.items, update]
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
            <DndContext sensors={sensors} collisionDetection={pointerWithin} onDragEnd={handleDragEnd}>
              <CaseFolder case={_case} onItemUpdated={update} />
            </DndContext>
          </Box>
        </Box>
      )}
    </Box>
  );
};

export default CaseSidebar;
