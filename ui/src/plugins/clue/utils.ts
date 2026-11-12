import { useClueEnrichSelector } from '@cccsaurora/clue-ui';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import type { Event } from 'models/entities/generated/Event';
import type { Hit } from 'models/entities/generated/Hit';
import { useContext } from 'react';
import { isHit } from 'utils/typeUtils';

export const useType = (hit?: Hit | Event, field?: string, value?: string) => {
  const guessType = useClueEnrichSelector(ctx => ctx.guessType);

  const { config } = useContext(ApiConfigContext);

  const typeFromHit = isHit(hit) ? hit.clue?.types?.find(mapping => mapping.field === field)?.type : undefined;
  if (typeFromHit) {
    return typeFromHit;
  }

  const typeFromConfig = config.configuration?.mapping?.[field!];
  if (typeFromConfig) {
    return typeFromConfig;
  }

  if (value) {
    return guessType(value.toString());
  }

  return null;
};
