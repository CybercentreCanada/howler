import type { Hit } from 'models/entities/generated/Hit';
import type { DossierPivot, MenuPathNode } from 'components/routes/dossiers/utils';
import type { ReactNode } from 'react';

export interface PivotSharedProps {
  hit?: Hit;
  onNavigate?: () => void;
}

export interface PivotFolderMenuProps extends PivotSharedProps {
  node: MenuPathNode;
}

export interface PivotSubMenuItemProps extends PivotFolderMenuProps {
  renderContent: (node: MenuPathNode, onNavigate?: () => void) => ReactNode;
}

export interface PivotFlyoutContentProps extends PivotSharedProps {
  pivots: DossierPivot[];
  groups: MenuPathNode[];
  renderGroup: (node: MenuPathNode) => ReactNode;
}
