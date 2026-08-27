import { useAppRouter } from '@tui/core';
import { capitalize } from 'lodash-es';
import { useCallback, useContext, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation, useParams, useSearchParams } from 'react-router';
import { useContextSelector } from 'use-context-selector';
import { AnalyticContext } from '../providers/AnalyticProvider';
import { RecordContext } from '../providers/RecordProvider';

const useTitle = () => {
  const { t } = useTranslation();
  const location = useLocation();
  const params = useParams();
  const searchParams = useSearchParams()[0];
  const { breadcrumbs } = useAppRouter();

  const { getAnalyticFromId } = useContext(AnalyticContext) ?? {};

  const hits = useContextSelector(RecordContext, ctx => ctx.records);
  const getHit = useContextSelector(RecordContext, ctx => ctx.getRecord);

  const setTitle = useCallback((title: string) => {
    document.querySelector('title').innerHTML = title;
  }, []);

  const runChecks = useCallback(async () => {
    const searchType = location.pathname.replace(/^\/(\w+)(\/.+)?$/, '$1').replace(/s$/, '');

    if (searchType === 'analytic') {
      if (params.id && getAnalyticFromId) {
        const analytic = await getAnalyticFromId(params.id);

        if (analytic) {
          setTitle(`${t('route.analytics.view')} - ${analytic.name}`);
        } else {
          setTitle(`${t('route.analytics.view')}`);
        }
      } else {
        setTitle(`Howler - ${t('route.analytics')}`);
      }
    } else if (searchType === 'hit' && params.id) {
      const hit = hits[params.id] ?? (await getHit(params.id));
      if (!hit) {
        return;
      }

      let newTitle = `${capitalize(hit.howler.escalation)} - ${hit.howler.analytic}`;
      if (hit.howler.detection) {
        newTitle += `: ${hit.howler.detection}`;
      }

      setTitle(newTitle);
    } else if (searchType === 'template' && location.pathname.endsWith('view') && searchParams.has('analytic')) {
      let title = t('route.templates.view');

      if (searchParams.has('analytic')) {
        title += ` - ${searchParams.get('analytic')}`;
      } else if (!searchParams.has('detection')) {
        title = `Howler - ${title}`;
      }

      if (searchParams.has('detection')) {
        title += `: ${searchParams.get('detection')}`;
      }

      setTitle(title);
    } else {
      const items = breadcrumbs();
      const currentCrumb = items[items.length - 1];

      if (currentCrumb) {
        setTitle(`Howler - ${currentCrumb.i18nKey ? t(currentCrumb.i18nKey) : currentCrumb.title}`);
      }
    }
  }, [location.pathname, params.id, searchParams, getAnalyticFromId, setTitle, t, hits, getHit, breadcrumbs]);

  useEffect(() => {
    void runChecks();
  }, [runChecks]);
};

export default useTitle;
