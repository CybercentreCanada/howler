import { Icon } from '@iconify/react';
import { ClickAwayListener, IconButton, MenuItem, MenuList, Paper, Popper, Typography } from '@mui/material';
import type { FC } from 'react';
import { useState } from 'react';
import type { PivotSubMenuItemProps } from './types';
import { useHoverMenu } from './utils';

const PivotSubMenuItem: FC<PivotSubMenuItemProps> = ({ node, onNavigate, renderContent }) => {
  const { isOpen, openMenu, cancelClose, scheduleClose, closeMenu } = useHoverMenu();
  const [rowElement, setRowElement] = useState<HTMLLIElement | null>(null);

  return (
    <MenuItem ref={setRowElement} sx={{ justifyContent: 'space-between', gap: 2 }}>
      <Typography variant="body2" noWrap>
        {node.path}
      </Typography>
      <IconButton size="small" onMouseEnter={openMenu} onMouseLeave={scheduleClose} onClick={openMenu}>
        <Icon icon="mdi:chevron-right" />
      </IconButton>
      <Popper
        open={isOpen}
        anchorEl={rowElement}
        placement="right-start"
        modifiers={[
          { name: 'flip', enabled: false },
          { name: 'offset', options: { offset: [0, 0] } }
        ]}
        sx={{ zIndex: theme => theme.zIndex.modal + 1 }}
      >
        <ClickAwayListener onClickAway={closeMenu}>
          <Paper elevation={4} onMouseEnter={cancelClose} onMouseLeave={scheduleClose} sx={{ width: 'max-content' }}>
            <MenuList>{renderContent(node, onNavigate)}</MenuList>
          </Paper>
        </ClickAwayListener>
      </Popper>
    </MenuItem>
  );
};

export default PivotSubMenuItem;
