import { has } from 'lodash-es';
import type { Hit } from 'models/entities/generated/Hit';
import type { WithMetadata } from 'models/WithMetadata';
import { useCallback } from 'react';
import { useContextSelector } from 'use-context-selector';
import { HitContext } from '../providers/HitProvider';

const useMatchers = () => {
  const getHit = useContextSelector(HitContext, ctx => ctx.getHit);

  const getMatchingTemplate = useCallback(
    async (hit: WithMetadata<Hit>) => {
      if (has(hit, '__template')) {
        return hit.__template;
      }

      console.log('miss', hit.howler.id);

      // This is a fallback in case metadata is not included. In most cases templates are shown, the template metadata
      // should also exist
      return (await getHit(hit.howler.id, true)).__template;
    },
    [getHit]
  );

  const getMatchingOverview = useCallback(
    async (hit: WithMetadata<Hit>) => {
      if (has(hit, '__overview')) {
        return hit.__overview;
      }

      // This is a fallback in case metadata is not included. In most cases templates are shown, the template metadata
      // should also exist
      return (await getHit(hit.howler.id, true)).__overview;
    },
    [getHit]
  );

  return {
    getMatchingOverview,
    getMatchingTemplate
  };
};

export default useMatchers;
