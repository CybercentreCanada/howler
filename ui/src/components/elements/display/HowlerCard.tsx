import type { CardProps } from '@mui/material';
import { Card } from '@mui/material';
import { forwardRef, memo } from 'react';

const HowlerCard = forwardRef<HTMLDivElement, CardProps>((props, ref) => (
  <Card ref={ref} elevation={props.variant !== 'outlined' ? 1 : 0} {...props} />
));

export default memo(HowlerCard);
