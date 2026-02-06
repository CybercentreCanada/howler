import { useClueEnrichSelector } from '@cccsaurora/clue-ui';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import type { Hit } from 'models/entities/generated/Hit';
import { useContext } from 'react';

export const useType = (hit?: Hit, field?: string, value?: string) => {
  const guessType = useClueEnrichSelector(ctx => ctx.guessType);

  const { config } = useContext(ApiConfigContext);

  const typeFromHit = hit?.clue?.types?.find(mapping => mapping.field === field)?.type;
  if (typeFromHit) {
    return typeFromHit;
  }

  const typeFromConfig = config.configuration?.mapping?.[field];
  if (typeFromConfig) {
    return typeFromConfig;
  }

  if (value) {
    return guessType(value.toString());
  }

  return null;
};
