import type { Hit } from 'models/entities/generated/Hit';
import type { ReactNode } from 'react';
import type { dossierPivot, menuPathNode } from 'utils/pivotForest';

export interface PivotSharedProps {
  hit?: Hit;
  onNavigate?: () => void;
}

export interface PivotFolderMenuProps extends PivotSharedProps {
  node: menuPathNode;
}

export interface PivotSubMenuItemProps extends PivotFolderMenuProps {
  renderContent: (node: menuPathNode, onNavigate?: () => void) => ReactNode;
}

export interface PivotFlyoutContentProps extends PivotSharedProps {
  pivots: dossierPivot[];
  groups: menuPathNode[];
  renderGroup: (node: menuPathNode) => ReactNode;
}
