import ResolvePivotUrl from 'components/elements/hit/ResolvePivotUrl';
import type { Hit } from 'models/entities/generated/Hit';
import { useCallback, useEffect, useRef, useState, type MouseEvent } from 'react';
import type { dossierPivot, menuPathNode } from 'utils/pivotForest';

const CLOSE_DELAY = 200;

export const useHoverMenu = () => {
  const [isOpen, setIsOpen] = useState(false);
  const closeTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => () => clearTimeout(closeTimer.current), []);

  const openMenu = useCallback((event: MouseEvent<HTMLElement>) => {
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

export const splitMainPivot = (node: menuPathNode): { main?: dossierPivot; rest: dossierPivot[] } => {
  const [main, ...rest] = node.pivots ?? [];
  return { main, rest };
};

export const countPivots = (node: menuPathNode): number =>
  (node.pivots?.length ?? 0) + (node.children ?? []).reduce((sum, child) => sum + countPivots(child), 0);

export const findOnlyPivot = (node: menuPathNode): dossierPivot | undefined => {
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

export const resolvePivotUrl = (item: dossierPivot, hit?: Hit) => {
  return (
    (item.pivot.format === 'link' ? ResolvePivotUrl(item.pivot, hit) : undefined) ||
    `/dossier/${item.dossier.dossier_id}`
  );
};
