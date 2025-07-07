import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { DragIndicator, Remove } from '@mui/icons-material';
import { Box, IconButton, Stack, TableCell, Tooltip, useTheme } from '@mui/material';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import FlexOne from 'components/elements/addons/layout/FlexOne';
import { useContext, type FC, type SetStateAction } from 'react';

const ColumnHeader: FC<{
  width: string;
  col: string;
  setColumns: (val: SetStateAction<string[]>) => void;
  onMouseDown: (col: string, event: React.MouseEvent<HTMLElement, MouseEvent>) => void;
}> = ({ col, width, setColumns, onMouseDown }) => {
  const theme = useTheme();
  const { config } = useContext(ApiConfigContext);
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id: col });

  return (
    <TableCell
      ref={setNodeRef}
      sx={{
        borderRight: 'thin solid',
        borderRightColor: 'divider',
        py: 0.5,
        position: 'relative'
      }}
      style={{ transform: CSS.Translate.toString(transform), transition }}
    >
      <Stack
        className={`col-${col.replaceAll('.', '-')}`}
        direction="row"
        spacing={1}
        alignItems="center"
        sx={[{ minWidth: '220px' }, !!width ? { width, maxWidth: width } : { maxWidth: '300px' }]}
      >
        <Tooltip title={config.indexes.hit[col].description}>
          <span>{col}</span>
        </Tooltip>
        <FlexOne />
        <IconButton
          size="small"
          sx={{ fontSize: '1rem' }}
          onClick={() => setColumns(_columns => _columns.filter(_col => _col !== col))}
        >
          <Remove fontSize="inherit" />
        </IconButton>

        <DragIndicator fontSize="small" sx={{ cursor: 'grab' }} {...attributes} {...listeners} />

        <Box
          sx={{
            position: 'absolute',
            top: theme.spacing(0.75),
            bottom: theme.spacing(0.75),
            right: -3,
            width: '5px',
            borderRight: 'thin solid',
            borderLeft: 'thin solid',
            borderColor: 'divider',
            cursor: 'col-resize'
          }}
          onMouseDown={e => onMouseDown(col, e)}
        />
      </Stack>
    </TableCell>
  );
};

export default ColumnHeader;
