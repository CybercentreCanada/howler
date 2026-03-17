import { CardContent } from '@mui/material';
import HowlerCard from 'components/elements/display/HowlerCard';
import type { Observable } from 'models/entities/generated/Observable';
import { memo, type FC } from 'react';
import ObservablePreview from './ObservablePreview';

const ObservableCard: FC<{ observable: Observable }> = ({ observable }) => (
  <HowlerCard sx={{ position: 'relative' }}>
    <CardContent>
      <ObservablePreview observable={observable} />
    </CardContent>
  </HowlerCard>
);

export default memo(ObservableCard);
