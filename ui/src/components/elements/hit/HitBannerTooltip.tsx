import { Tooltip } from '@mui/material';
import type { Hit } from 'models/entities/generated/Hit';
import type { FC, PropsWithChildren, ReactElement } from 'react';
import { memo } from 'react';
import { useTranslation } from 'react-i18next';

const HitBannerTooltip: FC<
  PropsWithChildren<{
    hit: Hit;
  }>
> = ({ hit, children }) => {
  const { t } = useTranslation();

  return (
    <Tooltip
      placement="top"
      title={
        <div>
          <div>{hit.event?.provider ?? t('unknown')}</div>
          <div>
            {hit.organization?.name ?? t('unknown')} - {hit.organization?.id ?? t('unknown')}
          </div>
          {hit.threat?.tactic && (
            <div>
              {hit.threat.tactic.id} ({hit.threat.tactic.name})
            </div>
          )}
          {hit.threat?.technique && (
            <div>
              {hit.threat.technique.id} ({hit.threat.technique.name})
            </div>
          )}
        </div>
      }
    >
      {children as ReactElement}
    </Tooltip>
  );
};

export default memo(HitBannerTooltip);
