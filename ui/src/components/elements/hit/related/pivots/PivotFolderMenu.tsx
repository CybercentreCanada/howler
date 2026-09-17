import { Folder, KeyboardArrowDown } from '@mui/icons-material';
import { Button } from '@mui/material';
import { useId, useState, type FC, type KeyboardEvent } from 'react';
import PivotFlyout from './PivotFlyout';
import PivotFlyoutContent from './PivotFlyoutContent';
import type { PivotFolderMenuProps } from './types';
import { useHoverMenu } from './utils';

const PivotFolderMenu: FC<PivotFolderMenuProps> = ({ node, hit }) => {
  const { isOpen, shouldFocusMenu, openMenu, cancelClose, scheduleClose, closeMenu } = useHoverMenu();
  const menuId = useId();
  const [rowElement, setRowElement] = useState<HTMLButtonElement | null>(null);

  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === 'Escape') {
      closeMenu();
      return;
    }

    if (event.key === 'ArrowDown' || event.key === 'ArrowRight') {
      event.preventDefault();
      openMenu(true);
    }
  };

  return (
    <>
      <Button
        ref={setRowElement}
        variant="outlined"
        startIcon={<Folder />}
        endIcon={<KeyboardArrowDown />}
        aria-haspopup="menu"
        aria-controls={isOpen ? menuId : undefined}
        aria-expanded={isOpen}
        onClick={event => openMenu(event.detail === 0)}
        onKeyDown={onKeyDown}
        onMouseEnter={() => openMenu()}
        onMouseLeave={() => scheduleClose()}
        sx={theme => ({
          color: 'text.primary',
          textTransform: 'none',
          backgroundColor: 'transparent',
          borderColor: 'divider',
          transition: theme.transitions.create(['border-color', 'color']),
          '&:hover': {
            borderColor: 'primary.main',
            color: 'primary.main'
          }
        })}
      >
        {node.path}
      </Button>

      <PivotFlyout
        id={menuId}
        anchorEl={rowElement}
        focusOnOpen={shouldFocusMenu}
        open={isOpen}
        placement="bottom-start"
        onClose={() => {
          closeMenu();
          rowElement?.focus();
        }}
        onMouseEnter={cancelClose}
        onMouseLeave={() => scheduleClose()}
      >
        <PivotFlyoutContent
          pivots={node.pivots ?? []}
          groups={node.children ?? []}
          hit={hit}
          onMenuEnter={cancelClose}
          onNavigate={closeMenu}
        />
      </PivotFlyout>
    </>
  );
};

export default PivotFolderMenu;
