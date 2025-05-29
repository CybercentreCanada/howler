import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { Delete } from '@mui/icons-material';
import { Box, Grid, IconButton } from '@mui/material';
import type { FC, PropsWithChildren } from 'react';

const EntryWrapper: FC<PropsWithChildren<{ editing: boolean; id: string; onDelete?: () => void }>> = ({
  editing,
  id,
  children,
  onDelete
}) => {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id, disabled: !editing });

  return (
    <Grid
      item
      ref={setNodeRef}
      xs={12}
      md={6}
      sx={{ position: 'relative' }}
      style={{ transform: CSS.Translate.toString(transform), transition }}
    >
      {editing && (
        <>
          <IconButton
            color="error"
            sx={theme => ({ position: 'absolute', top: theme.spacing(2), right: theme.spacing(1), zIndex: 10 })}
            onClick={onDelete}
          >
            <Delete fontSize="small" />
          </IconButton>
          <Box
            {...attributes}
            {...listeners}
            sx={{
              zIndex: 9,
              position: 'absolute',
              backgroundColor: 'background.paper',
              opacity: 0.5,
              top: 0,
              bottom: 0,
              left: 0,
              right: 0
            }}
          />
        </>
      )}
      {children}
    </Grid>
  );
};

export default EntryWrapper;
