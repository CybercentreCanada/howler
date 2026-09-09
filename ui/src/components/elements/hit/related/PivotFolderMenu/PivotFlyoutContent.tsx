import { MenuItem } from '@mui/material';
import PivotLink from 'components/elements/hit/related/PivotLink';
import type { FC } from 'react';
import { getDossierPivotKey } from 'utils/pivotForest';
import type { PivotFlyoutContentProps } from './types';
import { resolvePivotUrl } from './utils';

const PivotFlyoutContent: FC<PivotFlyoutContentProps> = ({ pivots, groups, hit, onNavigate, renderGroup }) => (
  <>
    {pivots.map(({ pivot, dossier }) => (
      <MenuItem key={getDossierPivotKey({ pivot, dossier })} onClick={onNavigate} sx={{ p: 0 }}>
        <PivotLink
          pivot={pivot}
          hit={hit}
          dossier={dossier}
          resolvedUrl={resolvePivotUrl({ pivot, dossier }, hit)}
          dense
        />
      </MenuItem>
    ))}
    {groups.map(renderGroup)}
  </>
);

export default PivotFlyoutContent;
