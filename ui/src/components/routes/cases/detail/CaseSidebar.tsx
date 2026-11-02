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
import { Circle } from '@mui/icons-material';
import { Box, Card, Chip, LinearProgress, Skeleton, Stack, Typography, useTheme } from '@mui/material';
import api from 'api';
import { ModalContext } from 'components/app/providers/ModalProvider';
import useMyApi from 'components/hooks/useMyApi';
import AddEventModal from 'components/routes/cases/modals/AddEventModal';
import AddToCaseModal from 'components/routes/cases/modals/AddToCaseModal';
import dayjs from 'dayjs';
import type { Case } from 'models/entities/generated/Case';
import type { Item } from 'models/entities/generated/Item';
import { useCallback, useContext, useReducer, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { ESCALATION_COLOR_MAP } from '../constants';
import CaseSidebarActions from './CaseSidebarActions';
import CaseSidebarNavigation from './CaseSidebarNavigation';
import CaseFolder from './sidebar/CaseFolder';
import FolderEntry from './sidebar/FolderEntry';
import RootDropZone from './sidebar/RootDropZone';

interface CaseSidebarProps {
  case: Case;
  update: (newCase: Case) => void;
}

const CaseSidebar: FC<CaseSidebarProps> = ({ case: _case, update }) => {
  const { dispatchApi } = useMyApi();
  const { t } = useTranslation();
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
    setActiveDragData({ type: data!.type, label: data!.label ?? '' });
  }, []);

  const handleDragEnd = useCallback(
    async (event: DragEndEvent) => {
      setActiveDragData(null);

      if (!_case?.case_id) {
        return;
      }

      const caseId = _case.case_id;
      const { active, over } = event;

      if (!over?.data.current || !active?.data.current) {
        return;
      }

      const movingEntry: Item = active.data.current.entry;
      const targetFolderId = over.data.current.folderId ?? null;

      if (!movingEntry.id) {
        return;
      }

      if (movingEntry.parent === targetFolderId) {
        return;
      }

      try {
        setLoading(true);
        const updatedCase = await dispatchApi(
          api.v2.case.items.put(caseId, movingEntry.id!, { parent: targetFolderId })
        );
        if (updatedCase) {
          update(updatedCase);
        }
      } finally {
        setLoading(false);
      }
    },
    [_case, dispatchApi, update]
  );

  const handleAddEvent = useCallback(() => {
    showModal(<AddEventModal case={_case} onUpdated={update} />, { maxHeight: '90vh', height: 'unset' });
  }, [_case, showModal, update]);

  const handleAddItem = useCallback(() => {
    showModal(<AddToCaseModal case={_case} onUpdated={update} />, { maxHeight: '90vh', height: 'unset' });
  }, [_case, showModal, update]);

  const handleAddFolder = useCallback(async () => {
    if (!_case?.case_id) {
      return;
    }

    try {
      setLoading(true);
      const updatedCase = await dispatchApi(
        api.v2.case.items.post(_case.case_id, {
          type: 'folder',
          name: t('page.cases.sidebar.new_folder'),
          value: t('page.cases.sidebar.new_folder')
        })
      );
      if (updatedCase) {
        update(updatedCase);
      }
    } finally {
      setLoading(false);
    }
  }, [_case, dispatchApi, t, update]);

  const handleRefresh = useCallback(async () => {
    if (!_case?.case_id) {
      return;
    }

    try {
      setLoading(true);
      const refreshedCase = await dispatchApi(api.v2.case.get(_case.case_id));
      if (refreshedCase) {
        update(refreshedCase);
      }
    } finally {
      setLoading(false);
    }
  }, [_case, dispatchApi, update]);

  if (!_case) {
    return null;
  }

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
            <Chip
              color={ESCALATION_COLOR_MAP[_case.escalation as keyof typeof ESCALATION_COLOR_MAP]}
              label={t(_case.escalation)}
            />
          ) : (
            <Skeleton height={24} />
          )}
        </Stack>
      </Card>

      {_case ? (
        <>
          <CaseSidebarNavigation caseId={_case.case_id!} />
        </>
      ) : (
        <>
          <Skeleton height={28} />
          <Skeleton height={28} />
          <Skeleton height={28} />
          <Skeleton height={28} />
          <Skeleton height={28} />
        </>
      )}

      <CaseSidebarActions
        onAddEvent={handleAddEvent}
        onAddItem={handleAddItem}
        onAddFolder={handleAddFolder}
        onRefresh={handleRefresh}
        onCollapseAll={collapse}
      />

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
              <RootDropZone caseId={_case.case_id!} />
              <DragOverlay dropAnimation={null}>
                {activeDragData && (
                  <FolderEntry caseId={_case.case_id!} indent={0} label={activeDragData.label} entry={undefined} />
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
