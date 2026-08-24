import { Icon } from '@iconify/react';
import { ClickAwayListener, IconButton, MenuItem, MenuList, Paper, Popper, Stack, Typography } from '@mui/material';
import PivotLink from 'components/elements/hit/related/PivotLink';
import ResolvePivotUrl from 'components/elements/hit/ResolvePivotUrl';
import type { Hit } from 'models/entities/generated/Hit';
import type { FC, MouseEvent } from 'react';
import { useCallback, useEffect, useRef, useState } from 'react';
import type { menuPathNode } from 'utils/pivotForest';

type DossierPivot = NonNullable<menuPathNode['pivots']>[number];

const CLOSE_DELAY = 200;

// Popper (no modal/backdrop/focus-trap) is used instead of Menu so nested flyouts never fight each other for focus
const useHoverMenu = () => {
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
  const closeTimer = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => () => clearTimeout(closeTimer.current), []);

  const openMenu = useCallback((event: MouseEvent<HTMLElement>) => {
    // stop the chevron's click from bubbling into an ancestor row's onClick (which would navigate/close instead of opening)
    event.stopPropagation();
    clearTimeout(closeTimer.current);
    setAnchorEl(event.currentTarget);
  }, []);

  const cancelClose = useCallback(() => clearTimeout(closeTimer.current), []);

  const scheduleClose = useCallback(() => {
    clearTimeout(closeTimer.current);
    closeTimer.current = setTimeout(() => setAnchorEl(null), CLOSE_DELAY);
  }, []);

  const closeMenu = useCallback(() => {
    clearTimeout(closeTimer.current);
    setAnchorEl(null);
  }, []);

  return { anchorEl, isOpen: Boolean(anchorEl), openMenu, cancelClose, scheduleClose, closeMenu };
};

// The first pivot (already alphabetically sorted) represents the whole tree; only the root button hoists it out
const splitMainPivot = (node: menuPathNode): { main?: DossierPivot; rest: DossierPivot[] } => {
  const [main, ...rest] = node.pivots ?? [];
  return { main, rest };
};

const resolvePivotUrl = (item: DossierPivot, hit?: Hit) => {
  const pivotUrl = item.pivot.format === 'link' ? ResolvePivotUrl(item.pivot, hit) : undefined;
  return pivotUrl || `/dossier/${item.dossier.dossier_id}`;
};

interface PivotFlyoutContentProps {
  pivots: DossierPivot[];
  groups: menuPathNode[];
  hit?: Hit;
  onNavigate: () => void;
}

// Renders a group's own pivots as rows, followed by every sub-group as its own expandable submenu row
const PivotFlyoutContent: FC<PivotFlyoutContentProps> = ({ pivots, groups, hit, onNavigate }) => (
  <>
    {pivots.map(({ pivot, dossier }) => (
      <MenuItem key={`${dossier.dossier_id}-${pivot.value}`} onClick={onNavigate} sx={{ p: 0.5 }}>
        <PivotLink
          pivot={pivot}
          hit={hit}
          dossier={dossier}
          resolvedUrl={resolvePivotUrl({ pivot, dossier }, hit)}
          compact
        />
      </MenuItem>
    ))}
    {groups.map(child => (
      <PivotSubMenuItem key={child.path} node={child} hit={hit} onNavigate={onNavigate} />
    ))}
  </>
);

interface PivotSubMenuItemProps {
  node: menuPathNode;
  hit?: Hit;
  onNavigate: () => void;
}

// A group row inside an open menu; the chevron always opens the flyout for its own pivots and further sub-groups
const PivotSubMenuItem: FC<PivotSubMenuItemProps> = ({ node, hit, onNavigate }) => {
  const { anchorEl, isOpen, openMenu, cancelClose, scheduleClose, closeMenu } = useHoverMenu();
  const folderName = node.path.split('/').pop();

  return (
    <MenuItem sx={{ justifyContent: 'space-between', gap: 2 }}>
      <Typography variant="body2" noWrap>
        {folderName}
      </Typography>
      <IconButton size="small" onMouseEnter={openMenu} onMouseLeave={scheduleClose} onClick={openMenu}>
        <Icon icon="mdi:chevron-right" />
      </IconButton>
      <Popper
        open={isOpen}
        anchorEl={anchorEl}
        placement="right-start"
        sx={{ zIndex: theme => theme.zIndex.modal + 1 }}
      >
        <ClickAwayListener onClickAway={closeMenu}>
          <Paper elevation={4} onMouseEnter={cancelClose} onMouseLeave={scheduleClose}>
            <MenuList>
              <PivotFlyoutContent
                pivots={node.pivots ?? []}
                groups={node.children ?? []}
                hit={hit}
                onNavigate={onNavigate}
              />
            </MenuList>
          </Paper>
        </ClickAwayListener>
      </Popper>
    </MenuItem>
  );
};

interface PivotFolderTriggerProps {
  node: menuPathNode;
  hit?: Hit;
}

// The always-visible entry point for a top-level group; it's a pivot like any other, the chevron opens the rest
const PivotFolderTrigger: FC<PivotFolderTriggerProps> = ({ node, hit }) => {
  const { anchorEl, isOpen, openMenu, cancelClose, scheduleClose, closeMenu } = useHoverMenu();
  const { main, rest } = splitMainPivot(node);
  const hasMore = rest.length > 0 || (node.children?.length ?? 0) > 0;

  return (
    <Stack direction="row" spacing={0.5} alignItems="center">
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
          {node.path.split('/').pop()}
        </Typography>
      )}
      {hasMore && (
        <IconButton
          size="small"
          onMouseEnter={openMenu}
          onMouseLeave={scheduleClose}
          onClick={openMenu}
          sx={theme => ({
            transition: theme.transitions.create(['color']),
            '&:hover': { color: 'primary.main' }
          })}
        >
          <Icon icon="mdi:chevron-right" />
        </IconButton>
      )}
      {hasMore && (
        <Popper
          open={isOpen}
          anchorEl={anchorEl}
          placement="bottom-start"
          sx={{ zIndex: theme => theme.zIndex.modal + 1 }}
        >
          <ClickAwayListener onClickAway={closeMenu}>
            <Paper elevation={4} onMouseEnter={cancelClose} onMouseLeave={scheduleClose}>
              <MenuList>
                <PivotFlyoutContent pivots={rest} groups={node.children ?? []} hit={hit} onNavigate={closeMenu} />
              </MenuList>
            </Paper>
          </ClickAwayListener>
        </Popper>
      )}
    </Stack>
  );
};

export default PivotFolderTrigger;
