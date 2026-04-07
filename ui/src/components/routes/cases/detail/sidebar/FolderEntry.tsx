import { useDraggable, useDroppable } from '@dnd-kit/core';
import { CSS } from '@dnd-kit/utilities';
import {
  BookRounded,
  CheckCircle,
  ChevronRight,
  Folder,
  Lightbulb,
  Link as LinkIcon,
  TableChart,
  Visibility
} from '@mui/icons-material';
import type { SvgIconProps } from '@mui/material';
import { alpha, Box, Stack, Typography, useTheme } from '@mui/material';
import type { Item } from 'models/entities/generated/Item';
import { type ComponentType, type FC } from 'react';
import { Link, useLocation } from 'react-router-dom';

// Static map: item type → MUI icon component (avoids re-creating closures on each render)
const ICON_FOR_TYPE: Record<string, ComponentType<SvgIconProps>> = {
  folder: Folder,
  case: BookRounded,
  observable: Visibility,
  hit: CheckCircle,
  table: TableChart,
  lead: Lightbulb,
  reference: LinkIcon
};

interface FolderEntryProps {
  caseId?: string | null;
  path: string;
  /** MUI `pl` value for indentation */
  indent: number;
  /** Text displayed as the entry label */
  label: string;
  /** MUI icon color token applied to the entry icon (default: 'inherit') */
  iconColor?: SvgIconProps['color'];
  /** MUI color token for the label Typography (default: 'text.secondary') */
  labelColor?: string;
  /** Whether the chevron is rotated 90° (expanded state) */
  chevronOpen?: boolean;
  /** When provided the entry renders as a react-router Link */
  to?: string;
  onClick?: () => void;
  itemType: string;
  item?: Item;
}

const FolderEntry: FC<FolderEntryProps> = ({
  caseId,
  path,
  indent,
  label,
  itemType,
  iconColor = 'disabled',
  labelColor = 'text.secondary',
  chevronOpen = false,
  to,
  onClick,
  item
}) => {
  const location = useLocation();
  const theme = useTheme();

  const isCase = itemType === 'case';
  const isFolder = itemType === 'folder';

  const dndId = `${caseId ?? ''}:${itemType}:${path}`;

  const {
    attributes,
    listeners,
    setNodeRef: setDraggableNodeRef,
    transform,
    isDragging,
    active: activeDragSubject
  } = useDraggable({
    id: dndId,
    data: {
      item,
      caseId
    },
    disabled: !caseId || isFolder
  });
  const { setNodeRef: setDroppableNodeRef, isOver } = useDroppable({
    id: dndId,
    disabled: !isFolder || isDragging || activeDragSubject?.data.current.caseId !== caseId,
    data: {
      path,
      caseId
    }
  });

  const isLink = to != null && !isDragging;
  const active = decodeURIComponent(location.pathname) === to;
  const Icon = ICON_FOR_TYPE[itemType] ?? Folder;

  return (
    <Stack
      ref={el => {
        setDroppableNodeRef(el);
        setDraggableNodeRef(el);
      }}
      direction="row"
      pl={indent}
      style={{ transform: CSS.Transform.toString(transform) }}
      sx={[
        {
          cursor: 'pointer',
          overflow: 'visible',
          color: `${theme.palette.text.secondary} !important`,
          textDecoration: 'none',
          background: 'transparent',
          position: 'relative',
          ...(isLink && { borderRight: '3px solid transparent' })
        },
        isLink &&
          active && {
            background: alpha(theme.palette.grey[600], 0.15),
            borderRightColor: theme.palette.primary.main
          }
      ]}
      onClick={onClick}
      {...attributes}
      {...listeners}
      {...(isLink && {
        component: Link,
        to,
        target: itemType === 'reference' ? '_blank' : undefined,
        rel: itemType === 'reference' ? 'noopener noreferrer' : undefined
      })}
    >
      <Box
        sx={[
          {
            position: 'absolute',
            top: 0,
            bottom: 0,
            left: 0,
            right: 0,
            border: '2px solid transparent',
            borderRadius: '5px',
            transition: theme.transitions.create('border-color')
          },
          isOver && activeDragSubject?.data.current.caseId === caseId && { borderColor: theme.palette.primary.main }
        ]}
      />
      <ChevronRight
        fontSize="small"
        color="disabled"
        sx={[
          !(isCase || isFolder) && { opacity: 0 },
          {
            transition: theme.transitions.create('transform', { duration: 100 }),
            transform: chevronOpen ? 'rotate(90deg)' : 'rotate(0deg)'
          }
        ]}
      />
      <Icon fontSize="small" color={iconColor} />
      <Typography variant="caption" color={labelColor} sx={{ userSelect: 'none', pl: 0.5, textWrap: 'nowrap' }}>
        {label}
      </Typography>
    </Stack>
  );
};

export default FolderEntry;
