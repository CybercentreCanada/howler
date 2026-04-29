import type { ChipProps, PaperProps, SxProps } from '@mui/material';
import { Chip, ClickAwayListener, Collapse, Paper, Popper } from '@mui/material';
import type { FC, ReactElement, ReactNode } from 'react';
import { memo, useState } from 'react';

interface ChipPopperProps {
  icon?: ReactElement;
  deleteIcon?: ReactElement;
  label?: ReactNode;
  children: ReactNode;
  slotProps?: {
    chip?: Partial<ChipProps>;
    paper?: PaperProps;
  };
  paperSx?: SxProps;
  minWidth?: string | number;
  placement?: 'bottom-start' | 'bottom-end' | 'bottom';
  onToggle?: (show: boolean) => void;
  onDelete?: (event?: any) => void;
  toggleOnDelete?: boolean;
  disablePortal?: boolean;
  closeOnClick?: boolean;
}

const ChipPopper: FC<ChipPopperProps> = ({
  icon,
  deleteIcon,
  label,
  children,
  minWidth,
  placement = 'bottom-start',
  onToggle,
  onDelete,
  toggleOnDelete = false,
  closeOnClick = false,
  disablePortal = true,
  slotProps = {}
}) => {
  const [show, setShow] = useState(false);
  const [anchorEl, setAnchorEl] = useState<HTMLDivElement | null>(null);

  const handleToggle = (newShow: boolean) => {
    setShow(newShow);
    onToggle?.(newShow);
  };

  return (
    <>
      <Chip
        icon={icon}
        deleteIcon={deleteIcon}
        label={label}
        onClick={e => {
          handleToggle(!show);
          e.stopPropagation();
        }}
        onDelete={onDelete ?? (toggleOnDelete ? () => handleToggle(!show) : null)}
        ref={setAnchorEl}
        sx={[
          theme => ({
            position: 'relative',
            zIndex: 1,
            transition: theme.transitions.create(['border-bottom-left-radius', 'border-bottom-right-radius'])
          }),
          show && { borderBottomLeftRadius: '0', borderBottomRightRadius: '0' },
          ...(Array.isArray(slotProps.chip?.sx) ? slotProps.chip.sx : [slotProps.chip?.sx])
        ]}
        {...(slotProps.chip ?? {})}
      />
      <Popper
        placement={placement}
        anchorEl={anchorEl}
        disablePortal={disablePortal}
        open={!!anchorEl}
        sx={{
          minWidth: Math.max(
            typeof minWidth === 'number' ? minWidth : parseInt((minWidth as string)?.replace('px', '')) || 0,
            anchorEl?.clientWidth || 0
          ),
          zIndex: 1000
        }}
      >
        <Collapse
          in={show}
          unmountOnExit
          onClick={() => {
            if (closeOnClick) {
              handleToggle(false);
            }
          }}
        >
          <ClickAwayListener
            onClickAway={() => {
              handleToggle(false);
            }}
          >
            <Paper
              sx={[
                { borderTopLeftRadius: 0, borderTopRightRadius: 0, px: 1, py: 2 },
                ...(Array.isArray(slotProps.paper?.sx) ? slotProps.paper.sx : [slotProps.paper?.sx])
              ]}
              {...(slotProps.paper ?? {})}
            >
              {children}
            </Paper>
          </ClickAwayListener>
        </Collapse>
      </Popper>
    </>
  );
};

export default memo(ChipPopper);
