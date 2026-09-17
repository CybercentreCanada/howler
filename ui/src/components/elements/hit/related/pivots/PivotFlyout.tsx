import { ClickAwayListener, Paper, Popper, type PopperProps } from '@mui/material';
import type { FC, KeyboardEvent, ReactNode } from 'react';
import { useEffect, useRef } from 'react';

/** Props for the floating menu container used by pivot navigation. */
interface PivotFlyoutProps {
  /** Element that anchors the flyout position. */
  anchorEl: HTMLElement | null;
  /** Whether to focus the first menu item when the flyout opens. */
  focusOnOpen: boolean;
  /** Menu content rendered inside the flyout. */
  children: ReactNode;
  /** DOM id assigned to the flyout menu container. */
  id: string;
  /** Position of the flyout relative to its anchor. */
  placement?: PopperProps['placement'];
  /** Closes the flyout. */
  onClose: () => void;
  /** Handles pointer entry into the flyout. */
  onMouseEnter: () => void;
  /** Handles pointer exit from the flyout. */
  onMouseLeave: () => void;
  /** Whether the flyout is visible. */
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
