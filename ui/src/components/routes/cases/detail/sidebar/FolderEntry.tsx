import { useDraggable, useDroppable } from '@dnd-kit/core';
import { CSS } from '@dnd-kit/utilities';
import {
  BookRounded,
  CheckCircle,
  ChevronRight,
  Description,
  Folder,
  Lightbulb,
  Link as LinkIcon,
  TableChart,
  Visibility
} from '@mui/icons-material';
import type { SvgIconProps } from '@mui/material';
import { alpha, Box, Stack, Typography, useTheme } from '@mui/material';
import type { Item } from 'models/entities/generated/Item';
import type { ComponentType, FC } from 'react';
import { Link, useLocation } from 'react-router';

// Static map: item type → MUI icon component (avoids re-creating closures on each render)
const ICON_FOR_TYPE: Record<string, ComponentType<SvgIconProps>> = {
  folder: Folder,
  case: BookRounded,
  event: Visibility,
  hit: CheckCircle,
  table: TableChart,
  lead: Lightbulb,
  reference: LinkIcon,
  markdown: Description
};

interface FolderEntryProps {
  /** The corresponding case ID for this entry */
  caseId?: string | null;

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

  /** Callback fired when the entry is clicked */
  onClick?: () => void;

  /** The item entity associated with this entry */
  entry?: Item;
}

const FolderEntry: FC<FolderEntryProps> = ({
  caseId,
  indent,
  label,
  iconColor = 'disabled',
  labelColor = 'text.secondary',
  chevronOpen = false,
  to,
  onClick,
  entry
}) => {
  const location = useLocation();
  const theme = useTheme();

  const isCase = entry?.type === 'case';
  const isFolder = entry?.type === 'folder';

  const entryId = entry?.id;
  const dndId = `${caseId ?? ''}:${entry?.type}:${entryId}`;

  const {
    attributes,
    listeners,
    setNodeRef: setDraggableNodeRef,
    transform,
    isDragging
  } = useDraggable({
    id: dndId,
    data: {
      type: entry?.type,
      label,
      entry,
      caseId
    },
    disabled: !caseId
  });

  const { setNodeRef: setDroppableNodeRef, isOver } = useDroppable({
    id: dndId,
    disabled: !isFolder || isDragging || !caseId,
    data: {
      caseId,
      folderId: entry?.id ?? null
    }
  });

  const isLink = to != null && !isDragging;
  const active = decodeURIComponent(location.pathname) === to;
  const Icon = entry?.type ? (ICON_FOR_TYPE[entry.type] ?? Folder) : Folder;

  return (
    <Stack
      ref={el => {
        setDroppableNodeRef(el);
        setDraggableNodeRef(el);
      }}
      direction="row"
      pl={indent}
      style={{ transform: CSS.Transform.toString(transform), opacity: isDragging ? 0 : undefined }}
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
        target: entry?.type === 'reference' ? '_blank' : undefined,
        rel: entry?.type === 'reference' ? 'noopener noreferrer' : undefined
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
            border: '2px dashed transparent',
            borderRadius: '5px',
            transition: theme.transitions.create('border-color')
          },
          isOver && !!caseId && { borderColor: theme.palette.primary.main }
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
