import type { DossierPivot, MenuPathNode } from 'components/routes/dossiers/utils';
import type { Hit } from 'models/entities/generated/Hit';

export interface PivotSharedProps {
  hit?: Hit;
  onMenuEnter?: () => void;
  onNavigate?: () => void;
}

export interface PivotFolderMenuProps extends PivotSharedProps {
  node: MenuPathNode;
}

export interface PivotFlyoutContentProps extends PivotSharedProps {
  pivots: DossierPivot[];
  groups: MenuPathNode[];
}
