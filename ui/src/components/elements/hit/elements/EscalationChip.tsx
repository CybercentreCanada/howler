import { Chip, Tooltip } from '@mui/material';
import type { Hit } from 'models/entities/generated/Hit';
import type { FC } from 'react';
import { getEscalationColor } from 'utils/utils';
import { HitLayout } from '../HitLayout';

const EscalationChip: FC<{ hit: Hit; layout: HitLayout; hideLabel?: boolean }> = ({
  hit,
  layout,
  hideLabel = false
}) => {
  const label = ['evidence', 'miss'].includes(hit.howler.escalation!) ? hit.howler.assessment : hit.howler.escalation;

  const component = (
    <Chip
      sx={[{ width: 'fit-content', display: 'inline-flex' }, HitLayout.DENSE && { minWidth: '20px' }]}
      label={hideLabel ? ' ' : label}
      size={layout !== HitLayout.COMFY ? 'small' : 'medium'}
      color={getEscalationColor(hit.howler.escalation)}
    />
  );

  return hideLabel ? <Tooltip title={label}>{component}</Tooltip> : component;
};

export default EscalationChip;
