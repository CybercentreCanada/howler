import type { CardProps } from '@mui/material';
import { Card } from '@mui/material';
import type { FC } from 'react';
import { memo } from 'react';

const HowlerCard: FC<CardProps> = props => (
  <Card style={{ outline: 'none' }} elevation={props.variant !== 'outlined' ? 4 : 0} {...props} />
);

export default memo(HowlerCard);
