import { useDndContext, useDroppable } from '@dnd-kit/core';
import { Inbox } from '@mui/icons-material';
import { alpha, Box, Typography } from '@mui/material';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';

const RootDropZone: FC<{ caseId: string }> = ({ caseId }) => {
  const { t } = useTranslation();
  const { active } = useDndContext();
  const { setNodeRef, isOver } = useDroppable({
    id: `${caseId}:folder:__root__`,
    data: { path: '', caseId }
  });

  if (!active) {
    return null;
  }

  return (
    <Box
      ref={setNodeRef}
      sx={theme => ({
        minHeight: '250px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 1,
        border: '2px dashed',
        borderColor: isOver ? theme.palette.primary.main : theme.palette.divider,
        borderRadius: 1,
        mx: 1,
        mt: 1,
        transition: theme.transitions.create(['border-color', 'background-color']),
        bgcolor: isOver ? alpha(theme.palette.primary.main, 0.08) : 'transparent',
        color: isOver ? theme.palette.primary.main : theme.palette.text.secondary
      })}
    >
      <Inbox fontSize="large" sx={{ opacity: 0.6 }} />
      <Typography variant="caption">{t('page.cases.folder.drop.root')}</Typography>
    </Box>
  );
};

export default RootDropZone;
