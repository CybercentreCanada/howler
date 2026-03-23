import { KeyboardArrowRight } from '@mui/icons-material';
import {
  Box,
  Divider,
  Fade,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  MenuList,
  Paper,
  useTheme,
  type SxProps
} from '@mui/material';
import type { ElementType, FC, MouseEventHandler, PropsWithChildren, ReactNode } from 'react';
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

/**
 * The margin at the bottom of the screen by which a submenu should be inverted.
 * If hovering within this many pixels of the bottom, the submenu renders upward.
 */
const CONTEXTMENU_MARGIN = 350;

export type ContextMenuDivider = {
  kind: 'divider';
  id: string;
  sx?: SxProps;
};

export type ContextMenuLeafItem = {
  kind: 'item';
  id: string;
  icon?: ReactNode;
  label: ReactNode;
  disabled?: boolean;
  onClick?: () => void;
  /** When provided the item renders as a router Link instead of a button. */
  to?: string;
};

export type ContextMenuSubItem = {
  key: string;
  label: ReactNode;
  disabled?: boolean;
  onClick?: () => void;
};

export type ContextMenuSubmenuItem = {
  kind: 'submenu';
  /**
   * Identifier for this submenu. Used to derive:
   *  - the MenuItem's DOM id (`${id}-menu-item`)
   *  - the submenu Paper's DOM id (`${id}-submenu`)
   */
  id: string;
  icon?: ReactNode;
  label: ReactNode;
  disabled?: boolean;
  items: ContextMenuSubItem[];
};

export type ContextMenuEntry = ContextMenuDivider | ContextMenuLeafItem | ContextMenuSubmenuItem;

interface ContextMenuProps {
  items: ContextMenuEntry[];
  /** Called after the menu opens, with the triggering event. */
  onOpen?: MouseEventHandler<HTMLElement>;
  /** Called when the menu closes. */
  onClose?: () => void;
  /** Wraps children + menu in this element. Defaults to Box. */
  Component?: ElementType;
  /** id applied to the wrapper element */
  id?: string;
}

/**
 * Generic context menu component that renders a MUI Menu from a declarative
 * items structure supporting leaf items, dividers, and single-level submenus.
 *
 * Submenus appear on hover and are positioned to avoid screen overflow.
 */
const ContextMenu: FC<PropsWithChildren<ContextMenuProps>> = ({
  items,
  onOpen,
  onClose,
  Component = Box,
  id,
  children
}) => {
  const theme = useTheme();
  const [show, setShow] = useState<Record<string, EventTarget & HTMLElement>>({});
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
  const [transformProps, setTransformProps] = useState<SxProps>({});

  const handleClose = useCallback(() => {
    setAnchorEl(null);
    onClose?.();
  }, [onClose]);

  const handleContextMenu: MouseEventHandler<HTMLElement> = useCallback(
    event => {
      if (anchorEl) {
        event.preventDefault();
        handleClose();
        return;
      }
      event.preventDefault();

      if (window.innerHeight - event.clientY < 300) {
        setTransformProps({
          position: 'fixed',
          bottom: `${window.innerHeight - event.clientY}px !important`,
          top: 'unset !important',
          left: `${event.clientX}px !important`
        });
      } else {
        setTransformProps({
          position: 'fixed',
          top: `${event.clientY}px !important`,
          left: `${event.clientX}px !important`
        });
      }

      setAnchorEl(event.target as HTMLElement);
      onOpen?.(event);
    },
    [anchorEl, handleClose, onOpen]
  );

  /**
   * Calculates positioning styles for a submenu based on the parent element's
   * position relative to the viewport bottom.
   */
  const calculateSubMenuStyles = useCallback((parent: HTMLElement): SxProps => {
    const baseStyles = { position: 'absolute', maxHeight: '300px', overflow: 'auto' } as const;
    const defaultStyles = { ...baseStyles, top: 0, left: '100%' };

    if (!parent) {
      return defaultStyles;
    }

    const parentBounds = parent.getBoundingClientRect();

    if (window.innerHeight - parentBounds.y < CONTEXTMENU_MARGIN) {
      return { ...baseStyles, bottom: 0, left: '100%' };
    }

    return defaultStyles;
  }, []);

  // Reset submenu visibility whenever the menu is closed
  useEffect(() => {
    if (!anchorEl) {
      setShow({});
    }
  }, [anchorEl]);

  return (
    <Component id={id} onContextMenu={handleContextMenu}>
      {children}
      <Menu
        id="record-menu"
        open={!!anchorEl}
        anchorEl={anchorEl}
        onClose={handleClose}
        slotProps={{
          paper: {
            sx: {
              ...transformProps,
              overflow: 'visible !important'
            },
            elevation: 2
          }
        }}
        MenuListProps={{
          dense: true,
          sx: {
            minWidth: '250px',
            paddingY: '0 !important',
            '& > :first-child': {
              borderTopLeftRadius: theme.shape.borderRadius,
              borderTopRightRadius: theme.shape.borderRadius
            },
            '& > :last-child': {
              borderBottomLeftRadius: theme.shape.borderRadius,
              borderBottomRightRadius: theme.shape.borderRadius
            }
          }
        }}
        anchorOrigin={{ vertical: 'top', horizontal: 'left' }}
        onClick={handleClose}
      >
        {items.map(entry => {
          if (entry.kind === 'divider') {
            return <Divider key={entry.id} sx={{ my: '0 !important' }} />;
          }

          if (entry.kind === 'item') {
            if (entry.to) {
              return (
                <MenuItem key={entry.id} component={Link} to={entry.to} disabled={entry.disabled}>
                  {entry.icon && <ListItemIcon>{entry.icon}</ListItemIcon>}
                  <ListItemText>{entry.label}</ListItemText>
                </MenuItem>
              );
            }

            return (
              <MenuItem key={entry.id} disabled={entry.disabled} onClick={entry.onClick}>
                {entry.icon && <ListItemIcon>{entry.icon}</ListItemIcon>}
                <ListItemText>{entry.label}</ListItemText>
              </MenuItem>
            );
          }

          const { id: entryId, icon, label, disabled, items: subItems } = entry;
          return (
            <MenuItem
              key={entryId}
              id={`${entryId}-menu-item`}
              sx={{ position: 'relative' }}
              onMouseEnter={ev => setShow(_show => ({ ..._show, [entryId]: ev.target as EventTarget & HTMLElement }))}
              onMouseLeave={() => setShow(_show => ({ ..._show, [entryId]: null }))}
              disabled={disabled}
            >
              {icon && <ListItemIcon>{icon}</ListItemIcon>}
              <ListItemText sx={{ flex: 1 }}>{label}</ListItemText>
              {!disabled && <KeyboardArrowRight fontSize="small" sx={{ color: 'text.secondary', mr: -1 }} />}
              <Fade in={!!show[entryId]} unmountOnExit>
                <Paper id={`${entryId}-submenu`} sx={calculateSubMenuStyles(show[entryId])} elevation={2}>
                  <MenuList sx={{ p: 0, borderTopLeftRadius: 0 }} dense role="group">
                    {subItems.map(subItem => (
                      <MenuItem key={subItem.key} onClick={subItem.onClick} disabled={subItem.disabled}>
                        <ListItemText>{subItem.label}</ListItemText>
                      </MenuItem>
                    ))}
                  </MenuList>
                </Paper>
              </Fade>
            </MenuItem>
          );
        })}
      </Menu>
    </Component>
  );
};

export default ContextMenu;
