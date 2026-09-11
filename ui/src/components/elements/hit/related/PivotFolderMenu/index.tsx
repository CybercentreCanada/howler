import { Icon } from '@iconify/react';
import { Box, ClickAwayListener, Divider, IconButton, MenuList, Paper, Popper, Typography } from '@mui/material';
import HowlerCard from 'components/elements/display/HowlerCard';
import PivotLink from 'components/elements/hit/related/PivotLink';
import type { FC } from 'react';
import { useState } from 'react';
import type { menuPathNode } from 'utils/pivotForest';
import PivotFlyoutContent from './PivotFlyoutContent';
import PivotSubMenuItem from './PivotSubMenuItem';
import type { PivotFolderMenuProps } from './types';
import { countPivots, findOnlyPivot, resolvePivotUrl, splitMainPivot, useHoverMenu } from './utils';

const PivotFolderMenu: FC<PivotFolderMenuProps> = ({ node, hit }) => {
  const { isOpen, openMenu, cancelClose, scheduleClose, closeMenu } = useHoverMenu();
  const [rowElement, setRowElement] = useState<HTMLDivElement | null>(null);

  const renderSubMenuItem = (child: menuPathNode, onNavigate?: () => void) => (
    <PivotSubMenuItem
      key={child.path}
      node={child}
      hit={hit}
      onNavigate={onNavigate}
      renderContent={(contentNode, navigate) => (
        <PivotFlyoutContent
          pivots={contentNode.pivots ?? []}
          groups={contentNode.children ?? []}
          hit={hit}
          onNavigate={navigate}
          renderGroup={grandchild => renderSubMenuItem(grandchild, navigate)}
        />
      )}
    />
  );

  if (countPivots(node) === 1) {
    const only = findOnlyPivot(node);
    if (only) {
      return (
        <PivotLink
          pivot={only.pivot}
          hit={hit}
          dossier={only.dossier}
          resolvedUrl={resolvePivotUrl(only, hit)}
          compact
          withCard
        />
      );
    }
  }

  const { main, rest } = splitMainPivot(node);
  const hasMore = rest.length > 0 || (node.children?.length ?? 0) > 0;

  return (
    <HowlerCard
      ref={setRowElement}
      variant="outlined"
      sx={theme => ({
        display: 'flex',
        alignItems: 'stretch',
        backgroundColor: 'transparent',
        transition: theme.transitions.create(['border-color']),
        '&:hover': { borderColor: 'primary.main', '& a': { textDecoration: 'underline' } }
      })}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', pl: main ? 0 : 1, '& a': { color: 'text.primary' } }}>
        {main ? (
          <PivotLink
            pivot={main.pivot}
            hit={hit}
            dossier={main.dossier}
            resolvedUrl={resolvePivotUrl(main, hit)}
            compact
          />
        ) : (
          <Typography variant="body2" noWrap>
            {node.path}
          </Typography>
        )}
      </Box>
      {hasMore && (
        <>
          <Divider orientation="vertical" flexItem sx={{ my: 0.75 }} />
          <IconButton
            size="small"
            onMouseEnter={openMenu}
            onMouseLeave={scheduleClose}
            onClick={openMenu}
            sx={theme => ({
              borderRadius: 0,
              transition: theme.transitions.create(['color']),
              '&:hover': { color: 'primary.main' }
            })}
          >
            <Icon icon="mdi:chevron-right" />
          </IconButton>
        </>
      )}
      {hasMore && (
        <Popper
          open={isOpen}
          anchorEl={rowElement}
          placement="bottom-start"
          sx={{ zIndex: theme => theme.zIndex.modal + 1 }}
        >
          <ClickAwayListener onClickAway={closeMenu}>
            <Paper elevation={4} onMouseEnter={cancelClose} onMouseLeave={scheduleClose} sx={{ width: 'max-content' }}>
              <MenuList>
                <PivotFlyoutContent
                  pivots={rest}
                  groups={node.children ?? []}
                  hit={hit}
                  onNavigate={closeMenu}
                  renderGroup={child => renderSubMenuItem(child, closeMenu)}
                />
              </MenuList>
            </Paper>
          </ClickAwayListener>
        </Popper>
      )}
    </HowlerCard>
  );
};

export default PivotFolderMenu;
