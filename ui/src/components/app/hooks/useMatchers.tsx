/* eslint-disable no-console */
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
      if (!hit) {
        return null;
      }

      if (has(hit, '__template')) {
        return hit.__template;
      }

      // This is a fallback in case metadata is not included. In most cases templates are shown, the template metadata
      // should also exist
      try {
        return (await getHit(hit.howler.id, true)).__template;
      } catch (e) {
        console.warn(e);
        return null;
      }
    },
    [getHit]
  );

  const getMatchingOverview = useCallback(
    async (hit: WithMetadata<Hit>) => {
      if (!hit) {
        return null;
      }

      if (has(hit, '__overview')) {
        return hit.__overview;
      }

      // This is a fallback in case metadata is not included. In most cases templates are shown, the template metadata
      // should also exist
      try {
        return (await getHit(hit.howler.id, true)).__overview;
      } catch (e) {
        console.warn(e);
        return null;
      }
    },
    [getHit]
  );

  const getMatchingDossiers = useCallback(
    async (hit: WithMetadata<Hit>) => {
      if (!hit) {
        return null;
      }

      if (has(hit, '__dossiers')) {
        return hit.__dossiers;
      }

      // This is a fallback in case metadata is not included. In most cases templates are shown, the template metadata
      // should also exist
      try {
        return (await getHit(hit.howler.id, true)).__dossiers ?? [];
      } catch (e) {
        console.warn(e);
        return [];
      }
    },
    [getHit]
  );

  const getMatchingAnalytic = useCallback(
    async (hit: WithMetadata<Hit>) => {
      if (!hit) {
        return null;
      }

      if (has(hit, '__analytic')) {
        return hit.__analytic;
      }

      // This is a fallback in case metadata is not included.
      try {
        return (await getHit(hit.howler.id, true)).__analytic;
      } catch (e) {
        console.warn(e);
        return null;
      }
    },
    [getHit]
  );

  return {
    getMatchingDossiers,
    getMatchingOverview,
    getMatchingTemplate,
    getMatchingAnalytic
  };
};

export default useMatchers;
