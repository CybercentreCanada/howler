import { Icon } from '@iconify/react';
import {
  Box,
  ClickAwayListener,
  Divider,
  IconButton,
  MenuItem,
  MenuList,
  Paper,
  Popper,
  Typography
} from '@mui/material';
import HowlerCard from 'components/elements/display/HowlerCard';
import PivotLink from 'components/elements/hit/related/PivotLink';
import ResolvePivotUrl from 'components/elements/hit/ResolvePivotUrl';
import type { Hit } from 'models/entities/generated/Hit';
import type { FC, MouseEvent } from 'react';
import { useCallback, useEffect, useRef, useState } from 'react';
import type { dossierPivot, menuPathNode } from 'utils/pivotForest';

// close delay in MS
const CLOSE_DELAY = 200;

interface PivotSharedProps {
  hit?: Hit;
  onNavigate?: () => void;
}

interface PivotSubMenuItemProps extends PivotSharedProps {
  node: menuPathNode;
}

interface PivotFlyoutContentProps extends PivotSharedProps {
  pivots: dossierPivot[];
  groups: menuPathNode[];
}

// Popper (no modal/backdrop/focus-trap) is used instead of Menu so nested flyouts never fight each other for focus
const useHoverMenu = () => {
  const [isOpen, setIsOpen] = useState(false);
  const closeTimer = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => () => clearTimeout(closeTimer.current), []);

  const openMenu = useCallback((event: MouseEvent<HTMLElement>) => {
    // stop the chevron's click from bubbling into an ancestor row's onClick (which would navigate/close instead of opening)
    event.stopPropagation();
    clearTimeout(closeTimer.current);
    setIsOpen(true);
  }, []);

  const cancelClose = useCallback(() => clearTimeout(closeTimer.current), []);

  const scheduleClose = useCallback(() => {
    clearTimeout(closeTimer.current);
    closeTimer.current = setTimeout(() => setIsOpen(false), CLOSE_DELAY);
  }, []);

  const closeMenu = useCallback(() => {
    clearTimeout(closeTimer.current);
    setIsOpen(false);
  }, []);

  return { isOpen, openMenu, cancelClose, scheduleClose, closeMenu };
};

// The first pivot (already alphabetically sorted) represents the whole tree; only the root button hoists it out
const splitMainPivot = (node: menuPathNode): { main?: dossierPivot; rest: dossierPivot[] } => {
  const [main, ...rest] = node.pivots ?? [];
  return { main, rest };
};

// Total pivots anywhere in this subtree; a lone unbranched chain (e.g. parent/child with nothing else under either)
// only ever has one, and should collapse straight to it instead of forcing a hover through empty folders
const countPivots = (node: menuPathNode): number =>
  (node.pivots?.length ?? 0) + (node.children ?? []).reduce((sum, child) => sum + countPivots(child), 0);

// only call once countPivots(node) === 1 has confirmed exactly one pivot exists somewhere in this subtree
const findOnlyPivot = (node: menuPathNode): dossierPivot | undefined => {
  if (node.pivots?.length) {
    return node.pivots[0];
  }

  for (const child of node.children ?? []) {
    const found = findOnlyPivot(child);
    if (found) {
      return found;
    }
  }

  return undefined;
};

const resolvePivotUrl = (item: dossierPivot, hit?: Hit) => {
  return (
    (item.pivot.format === 'link' ? ResolvePivotUrl(item.pivot, hit) : undefined) ||
    `/dossier/${item.dossier.dossier_id}`
  );
};

// Renders a group's own pivots as rows, followed by every sub-group as its own expandable submenu row
const PivotFlyoutContent: FC<PivotFlyoutContentProps> = ({ pivots, groups, hit, onNavigate }) => (
  <>
    {pivots.map(({ pivot, dossier }) => (
      <MenuItem key={`${dossier.dossier_id}-${pivot.value}`} onClick={() => onNavigate?.()} sx={{ p: 0 }}>
        <PivotLink
          pivot={pivot}
          hit={hit}
          dossier={dossier}
          resolvedUrl={resolvePivotUrl({ pivot, dossier }, hit)}
          dense
        />
      </MenuItem>
    ))}
    {groups.map(child => (
      <PivotSubMenuItem key={child.path} node={child} hit={hit} onNavigate={onNavigate} />
    ))}
  </>
);

// A group row inside an open menu; the chevron always opens the flyout for its own pivots and further sub-groups
const PivotSubMenuItem: FC<PivotSubMenuItemProps> = ({ node, hit, onNavigate }) => {
  const { isOpen, openMenu, cancelClose, scheduleClose, closeMenu } = useHoverMenu();
  const rowRef = useRef<HTMLLIElement>(null);

  return (
    <MenuItem ref={rowRef} sx={{ justifyContent: 'space-between', gap: 2 }}>
      <Typography variant="body2" noWrap>
        {node.path}
      </Typography>
      <IconButton size="small" onMouseEnter={openMenu} onMouseLeave={scheduleClose} onClick={openMenu}>
        <Icon icon="mdi:chevron-right" />
      </IconButton>
      <Popper
        open={isOpen}
        anchorEl={rowRef.current}
        placement="right-start"
        modifiers={[
          { name: 'flip', enabled: false },
          { name: 'offset', options: { offset: [0, 0] } }
        ]}
        sx={{ zIndex: theme => theme.zIndex.modal + 1 }}
      >
        <ClickAwayListener onClickAway={closeMenu}>
          <Paper elevation={4} onMouseEnter={cancelClose} onMouseLeave={scheduleClose} sx={{ width: 'max-content' }}>
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

// The always-visible entry point for a top-level group; a tree with a single pivot collapses straight to it,
// otherwise it's a pivot like any other and the chevron opens the rest
const PivotFolderTrigger: FC<PivotSubMenuItemProps> = ({ node, hit }) => {
  const { isOpen, openMenu, cancelClose, scheduleClose, closeMenu } = useHoverMenu();
  const rowRef = useRef<HTMLDivElement>(null);

  if (countPivots(node) === 1) {
    const only = findOnlyPivot(node);
    return (
      <PivotLink
        pivot={only.pivot}
        hit={hit}
        dossier={only.dossier}
        resolvedUrl={resolvePivotUrl(only, hit)}
        compact
        card
      />
    );
  }

  const { main, rest } = splitMainPivot(node);
  const hasMore = rest.length > 0 || (node.children?.length ?? 0) > 0;

  return (
    <HowlerCard
      ref={rowRef}
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
          anchorEl={rowRef.current}
          placement="bottom-start"
          sx={{ zIndex: theme => theme.zIndex.modal + 1 }}
        >
          <ClickAwayListener onClickAway={closeMenu}>
            <Paper elevation={4} onMouseEnter={cancelClose} onMouseLeave={scheduleClose} sx={{ width: 'max-content' }}>
              <MenuList>
                <PivotFlyoutContent pivots={rest} groups={node.children ?? []} hit={hit} onNavigate={closeMenu} />
              </MenuList>
            </Paper>
          </ClickAwayListener>
        </Popper>
      )}
    </HowlerCard>
  );
};

export default PivotFolderTrigger;
