import { KeyboardArrowRight } from '@mui/icons-material';
import { MenuItem, MenuList } from '@mui/material';
import PivotLink from 'components/elements/hit/related/pivots/PivotLink';
import { getDossierPivotKey } from 'components/routes/dossiers/utils';
import { useId, useState, type FC, type KeyboardEvent } from 'react';
import PivotFlyout from './PivotFlyout';
import type { PivotFlyoutContentProps, PivotFolderMenuProps } from './types';
import { useHoverMenu } from './utils';

const PivotSubMenuItem: FC<
  PivotFolderMenuProps & {
    onClose: () => void;
    onOpen: () => void;
    open: boolean;
  }
> = ({ node, hit, onClose, onMenuEnter, onNavigate, onOpen, open }) => {
  const { isOpen, shouldFocusMenu, openMenu, cancelClose, scheduleClose, closeMenu } = useHoverMenu();
  const [rowElement, setRowElement] = useState<HTMLLIElement | null>(null);
  const menuId = useId();

  const openSubmenu = (focusMenu = false) => {
    onOpen();
    openMenu(focusMenu);
  };

  const closeSubmenu = () => {
    closeMenu();
    onClose();
    rowElement?.focus();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLLIElement>) => {
    if (event.key === 'Escape' || event.key === 'ArrowLeft') {
      event.preventDefault();
      closeSubmenu();
      return;
    }

    if (event.key === 'ArrowRight') {
      event.preventDefault();
      openSubmenu(true);
    }
  };

  return (
    <>
      <MenuItem
        ref={setRowElement}
        aria-haspopup="menu"
        aria-controls={isOpen && open ? menuId : undefined}
        aria-expanded={isOpen && open}
        onMouseEnter={() => openSubmenu()}
        onMouseLeave={() => scheduleClose()}
        onClick={event => openSubmenu(event.detail === 0)}
        onKeyDown={onKeyDown}
        sx={{ justifyContent: 'space-between', gap: 2 }}
      >
        {node.path}
        <KeyboardArrowRight fontSize="small" />
      </MenuItem>

      <PivotFlyout
        id={menuId}
        anchorEl={rowElement}
        focusOnOpen={shouldFocusMenu}
        open={isOpen && open}
        onClose={closeSubmenu}
        onMouseEnter={() => {
          cancelClose();
          onMenuEnter?.();
        }}
        onMouseLeave={() => scheduleClose()}
      >
        <PivotFlyoutContent
          pivots={node.pivots ?? []}
          groups={node.children ?? []}
          hit={hit}
          onMenuEnter={cancelClose}
          onNavigate={onNavigate}
        />
      </PivotFlyout>
    </>
  );
};

const PivotFlyoutContent: FC<PivotFlyoutContentProps> = ({ pivots, groups, hit, onMenuEnter, onNavigate }) => {
  const [openGroup, setOpenGroup] = useState<string>();

  return (
    <MenuList disablePadding>
      {groups.map(group => (
        <PivotSubMenuItem
          key={group.path}
          node={group}
          hit={hit}
          open={openGroup === group.path}
          onOpen={() => setOpenGroup(group.path)}
          onClose={() => setOpenGroup(undefined)}
          onMenuEnter={onMenuEnter}
          onNavigate={onNavigate}
        />
      ))}
      {pivots.map(({ pivot, dossier }) => (
        <PivotLink
          key={getDossierPivotKey(dossier, pivot)}
          pivot={pivot}
          hit={hit}
          dossier={dossier}
          variant="menu-item"
          onNavigate={onNavigate}
        />
      ))}
    </MenuList>
  );
};

export default PivotFlyoutContent;
