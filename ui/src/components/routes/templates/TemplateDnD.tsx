import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { Delete, DragHandle } from '@mui/icons-material';
import { IconButton, Stack, Tooltip, Typography } from '@mui/material';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';

const TemplateDnD: FC<{ field?: any; data?: any; onRemove: (field: string) => void; tooltipTitle: any }> = ({
  field,
  data,
  onRemove,
  tooltipTitle
}) => {
  const { t } = useTranslation();

  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id: field });

  return (
    <Stack
      direction="row"
      spacing={1}
      ref={setNodeRef}
      style={{ transition, transform: CSS.Transform.toString(transform) }}
    >
      <Tooltip title={t('button.drag')} {...attributes} {...listeners}>
        <IconButton size="medium" onClick={() => onRemove(field)}>
          <DragHandle fontSize="medium" />
        </IconButton>
      </Tooltip>
      <Tooltip title={tooltipTitle} sx={{ alignContent: 'center' }}>
        <Typography variant="body1" fontWeight="bold">
          {field}:
        </Typography>
      </Tooltip>
      <Typography
        variant="body1"
        whiteSpace="normal"
        sx={{ width: '100%', wordBreak: 'break-all', alignContent: 'center' }}
      >
        {data}
      </Typography>
      <Tooltip title={t('button.delete')}>
        <IconButton size="medium" onClick={() => onRemove(field)} sx={{ marginLeft: 'auto' }}>
          <Delete fontSize="medium" />
        </IconButton>
      </Tooltip>
    </Stack>
  );
};

export default TemplateDnD;
