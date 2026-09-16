import { ClickAwayListener, Paper, Popper, type PopperProps } from '@mui/material';
import type { FC, KeyboardEvent, ReactNode } from 'react';
import { useEffect, useRef } from 'react';

interface PivotFlyoutProps {
  anchorEl: HTMLElement | null;
  focusOnOpen: boolean;
  children: ReactNode;
  id: string;
  placement?: PopperProps['placement'];
  onClose: () => void;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
  open: boolean;
}

const PivotFlyout: FC<PivotFlyoutProps> = ({
  anchorEl,
  focusOnOpen,
  children,
  id,
  placement,
  onClose,
  onMouseEnter,
  onMouseLeave,
  open
}) => {
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open && focusOnOpen) {
      menuRef.current?.querySelector<HTMLElement>('[role="menuitem"]')?.focus();
    }
  }, [focusOnOpen, open]);

  useEffect(() => {
    if (!open && document.activeElement && menuRef.current?.contains(document.activeElement)) {
      anchorEl?.focus();
    }
  }, [anchorEl, open]);

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'Escape') {
      return;
    }

    event.preventDefault();
    event.stopPropagation();
    onClose();
  };

  return (
    <Popper
      open={open}
      anchorEl={anchorEl}
      placement={placement ?? 'right-start'}
      keepMounted={false}
      sx={{ zIndex: theme => theme.zIndex.modal + 1 }}
    >
      <ClickAwayListener onClickAway={() => onClose()} mouseEvent="onMouseDown" touchEvent="onTouchStart">
        <Paper elevation={4} onMouseEnter={onMouseEnter} onMouseLeave={onMouseLeave} onKeyDown={onKeyDown}>
          <div id={id} ref={menuRef}>
            {children}
          </div>
        </Paper>
      </ClickAwayListener>
    </Popper>
  );
};

export default PivotFlyout;
