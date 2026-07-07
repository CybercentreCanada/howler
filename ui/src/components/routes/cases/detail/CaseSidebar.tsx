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
import {
  AddCircle,
  CalendarMonth,
  Circle,
  Dashboard,
  Dataset,
  Description,
  Folder,
  Refresh,
  Rule,
  Search,
  UnfoldLess
} from '@mui/icons-material';
import {
  alpha,
  Box,
  Card,
  Chip,
  IconButton,
  LinearProgress,
  Skeleton,
  Stack,
  Typography,
  useTheme
} from '@mui/material';
import api from 'api';
import { ModalContext } from 'components/app/providers/ModalProvider';
import useMyApi from 'components/hooks/useMyApi';
import AddItemToCaseModal from 'components/routes/cases/modals/AddItemToCaseModal';
import dayjs from 'dayjs';
import type { Case } from 'models/entities/generated/Case';
import type { Item } from 'models/entities/generated/Item';
import { useCallback, useContext, useReducer, useState, type FC } from 'react';
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
  const { showModal } = useContext(ModalContext);

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
  const [collapseKey, collapse] = useReducer(x => x + 1, 0);

  const handleDragStart = useCallback((event: DragStartEvent) => {
    const data = event.active.data.current;
    setActiveDragData({ type: data.type, label: data.label ?? '' });
  }, []);

  const navItemSx = useCallback(
    (isActive: boolean) => [
      {
        cursor: 'pointer',
        px: 0.5,
        py: 0.5,
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
      const movingId = (movingEntry as Item).id ?? (movingEntry as Tree).id;
      const targetFolderId = over.data.current.folderId ?? null;

      if (!movingId) {
        return;
      }

      const currentParent = (movingEntry as Item).parent ?? (movingEntry as Tree).parentId ?? null;
      if (currentParent === targetFolderId) {
        return;
      }

      try {
        setLoading(true);
        const updatedCase = await dispatchApi(api.v2.case.items.move(_case.case_id, movingId, targetFolderId));
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
        sx={navItemSx(location.pathname.endsWith(_case?.case_id))}
        component={Link}
        to={`/cases/${_case?.case_id}`}
      >
        <Dashboard fontSize="small" />
        <Typography variant="body2" sx={{ pl: 1, textWrap: 'nowrap' }}>
          {t('page.cases.dashboard')}
        </Typography>
      </Stack>

      <Stack
        direction="row"
        alignItems="center"
        sx={navItemSx(location.pathname.endsWith('search'))}
        component={Link}
        to={`/cases/${_case?.case_id}/search`}
      >
        <Search fontSize="small" />
        <Typography variant="body2" sx={{ userSelect: 'none', pl: 1, textWrap: 'nowrap' }}>
          {t('page.cases.search')}
        </Typography>
      </Stack>

      <Stack
        direction="row"
        alignItems="center"
        sx={navItemSx(location.pathname.endsWith('observables'))}
        component={Link}
        to={`/cases/${_case?.case_id}/observables`}
      >
        <Dataset fontSize="small" />
        <Typography variant="body2" sx={{ userSelect: 'none', pl: 1, textWrap: 'nowrap' }}>
          {t('page.cases.observables')}
        </Typography>
      </Stack>

      <Stack
        direction="row"
        alignItems="center"
        sx={navItemSx(location.pathname.endsWith('timeline'))}
        component={Link}
        to={`/cases/${_case?.case_id}/timeline`}
      >
        <CalendarMonth fontSize="small" />
        <Typography variant="body2" sx={{ userSelect: 'none', pl: 1, textWrap: 'nowrap' }}>
          {t('page.cases.timeline')}
        </Typography>
      </Stack>

      <Stack
        direction="row"
        alignItems="center"
        sx={navItemSx(location.pathname.endsWith('rules'))}
        component={Link}
        to={`/cases/${_case?.case_id}/rules`}
      >
        <Rule />
        <Typography variant="body2" sx={{ userSelect: 'none', pl: 1, textWrap: 'nowrap' }}>
          {t('page.cases.rules')}
        </Typography>
      </Stack>

      <Card sx={{ borderRadius: 0, p: 0.25 }}>
        <Stack direction="row" spacing={0.25}>
          <div style={{ flex: 1 }} />

          <IconButton
            size="small"
            sx={{ position: 'relative' }}
            onClick={() => {
              if (_case) {
                showModal(<AddItemToCaseModal caseData={_case} onUpdated={update} />);
              }
            }}
          >
            <Description sx={{ fontSize: '18px' }} />
            <AddCircle
              sx={{
                fontSize: '12px',
                position: 'absolute',
                bottom: 2,
                right: 2,
                backgroundColor: theme.palette.background.paper,
                borderRadius: '100%'
              }}
              htmlColor="grey"
            />
          </IconButton>

          <IconButton
            size="small"
            sx={{ position: 'relative' }}
            onClick={async () => {
              if (_case?.case_id) {
                try {
                  setLoading(true);
                  const updatedCase = await dispatchApi(
                    api.v2.case.items.post(_case.case_id, {
                      type: 'folder',
                      value: t('page.cases.sidebar.new_folder')
                    })
                  );
                  update(updatedCase);
                } finally {
                  setLoading(false);
                }
              }
            }}
          >
            <Folder sx={{ fontSize: '18px' }} />
            <AddCircle
              sx={{
                fontSize: '12px',
                position: 'absolute',
                bottom: 2,
                right: 2,
                backgroundColor: theme.palette.background.paper,
                borderRadius: '100%'
              }}
              htmlColor="grey"
            />
          </IconButton>

          <IconButton
            size="small"
            onClick={async () => {
              if (_case?.case_id) {
                try {
                  setLoading(true);
                  const refreshedCase = await dispatchApi(api.v2.case.get(_case.case_id));
                  if (refreshedCase) {
                    update(refreshedCase);
                  }
                } finally {
                  setLoading(false);
                }
              }
            }}
          >
            <Refresh sx={{ fontSize: '18px' }} />
          </IconButton>

          <IconButton size="small" onClick={collapse}>
            <UnfoldLess sx={{ fontSize: '18px' }} />
          </IconButton>
        </Stack>
      </Card>

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
              <CaseFolder case={_case} onItemUpdated={update} collapseKey={collapseKey} />
              <RootDropZone caseId={_case.case_id} />
              <DragOverlay dropAnimation={null}>
                {activeDragData && (
                  <FolderEntry caseId={null} indent={0} label={activeDragData.label} itemType={activeDragData.type} />
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
