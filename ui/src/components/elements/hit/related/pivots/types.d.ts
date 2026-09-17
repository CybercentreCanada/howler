import type { DossierPivot, MenuPathNode } from 'components/routes/dossiers/utils';
import type { Hit } from 'models/entities/generated/Hit';

/** Shared props for pivot navigation components. */
export interface PivotSharedProps {
  /** Hit whose data may be used by pivot links. */
  hit?: Hit;

  /** Keeps a parent menu open while the pointer is inside it. */
  onMenuEnter?: () => void;

  /** Called when navigating to a pivot. */
  onNavigate?: () => void;
}

/** Props for the root pivot folder menu. */
export interface PivotFolderMenuProps extends PivotSharedProps {
  /** Folder node represented by the menu. */
  node: MenuPathNode;
}

/** Props for the contents of a pivot flyout menu. */
export interface PivotFlyoutContentProps extends PivotSharedProps {
  /** Pivots rendered at the current menu level. */
  pivots: DossierPivot[];

  /** Child folder groups rendered as nested menus. */
  groups: MenuPathNode[];
}
