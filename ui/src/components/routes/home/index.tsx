import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent
} from '@dnd-kit/core';
import { SortableContext, arrayMove, sortableKeyboardCoordinates } from '@dnd-kit/sortable';
import { Cancel, Check, Close, Edit, OpenInNew } from '@mui/icons-material';
import { Alert, AlertTitle, CircularProgress, Grid, IconButton, Stack, Typography } from '@mui/material';
import api from 'api';
import { AppBrand } from 'branding/AppBrand';
import { useAppUser } from 'commons/components/app/hooks';
import PageCenter from 'commons/components/pages/PageCenter';
import CustomButton from 'components/elements/addons/buttons/CustomButton';
import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import useMyUserFunctions from 'components/hooks/useMyUserFunctions';
import isEqual from 'lodash-es/isEqual';
import type { HowlerUser } from 'models/entities/HowlerUser';
import moment from 'moment';
import { useCallback, useEffect, useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { StorageKey } from 'utils/constants';
import AddNewCard from './AddNewCard';
import AnalyticCard, { type AnalyticSettings } from './AnalyticCard';
import EntryWrapper from './EntryWrapper';
import ViewCard, { type ViewSettings } from './ViewCard';

const LUCENE_DATE_FMT = 'YYYY-MM-DD[T]HH:mm:ss';

const Home: FC = () => {
  const { t } = useTranslation();
  const { user, setUser } = useAppUser<HowlerUser>();
  const { setDashboard } = useMyUserFunctions();
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const [lastViewed, setLastViewed] = useMyLocalStorageItem(
    StorageKey.LAST_VIEW,
    moment().utc().format(LUCENE_DATE_FMT)
  );

  const [loading, setLoading] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [updatedHitTotal, setUpdatedHitTotal] = useState(0);
  const [dashboard, setStateDashboard] = useState(user.dashboard ?? []);

  const updateQuery = useMemo(
    () =>
      `(howler.log.user:${user.username} OR howler.assignment:${user.username}) AND howler.log.timestamp:{${lastViewed} TO now} AND -howler.status:resolved`,
    [lastViewed, user.username]
  );

  const getIdFromEntry = useCallback((entry: HowlerUser['dashboard'][0]) => {
    const settings = JSON.parse(entry.config);

    if (entry.type === 'analytic') {
      return `${settings.analyticId}-${settings.type}`;
    } else if (entry.type === 'view') {
      return settings.viewId;
    } else {
      return 'unknown';
    }
  }, []);

  const setLocalDashboard = useCallback((_dashboard: HowlerUser['dashboard']) => {
    setStateDashboard(_dashboard);
  }, []);

  const saveChanges = useCallback(async () => {
    setLoading(true);

    try {
      setUser({
        ...user,
        dashboard
      });
      await setDashboard(dashboard ?? []);

      setIsEditing(false);
    } finally {
      setLoading(false);
    }
  }, [dashboard, setDashboard, setUser, user]);

  const discardChanges = useCallback(() => {
    setStateDashboard(user.dashboard);
    setIsEditing(false);
  }, [user.dashboard]);

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event;

      if (active.id !== over.id) {
        const oldIndex = (dashboard ?? []).findIndex(entry => getIdFromEntry(entry) === active.id);
        const newIndex = (dashboard ?? []).findIndex(entry => getIdFromEntry(entry) === over.id);

        setLocalDashboard(arrayMove(dashboard, oldIndex, newIndex));
      }
    },
    [dashboard, getIdFromEntry, setLocalDashboard]
  );

  useEffect(() => {
    api.search.hit
      .post({
        query: updateQuery,
        rows: 5
      })
      .then(result => setUpdatedHitTotal(result.total));
  }, [updateQuery]);

  return (
    <PageCenter maxWidth="1800px" textAlign="left" height="100%">
      <Stack direction="column" spacing={1} sx={{ height: '100%' }}>
        <Stack direction="row" justifyContent="end" spacing={1}>
          {isEditing && (
            <CustomButton variant="outlined" size="small" color="error" startIcon={<Cancel />} onClick={discardChanges}>
              {t('cancel')}
            </CustomButton>
          )}
          <CustomButton
            variant="outlined"
            size="small"
            disabled={isEditing && isEqual(dashboard, user.dashboard)}
            color={isEditing ? 'success' : 'primary'}
            startIcon={isEditing ? loading ? <CircularProgress size={20} /> : <Check /> : <Edit />}
            onClick={() => (!isEditing ? setIsEditing(true) : saveChanges())}
          >
            {t(isEditing ? 'save' : 'edit')}
          </CustomButton>
        </Stack>
        {updatedHitTotal > 0 && (
          <Alert
            severity="info"
            variant="outlined"
            action={
              <Stack spacing={1} direction="row">
                <IconButton
                  color="info"
                  component={Link}
                  to={`/hits?query=${encodeURIComponent(updateQuery)}`}
                  onClick={() => setLastViewed(moment().utc().format(LUCENE_DATE_FMT))}
                >
                  <OpenInNew />
                </IconButton>
                <IconButton
                  color="info"
                  onClick={() => {
                    setLastViewed(moment().utc().format(LUCENE_DATE_FMT));
                    setUpdatedHitTotal(0);
                  }}
                >
                  <Close />
                </IconButton>
              </Stack>
            }
          >
            <AlertTitle>{t('route.home.alert.updated.title')}</AlertTitle>
            {t('route.home.alert.updated.description', { count: updatedHitTotal })}
          </Alert>
        )}
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={(dashboard ?? []).map(entry => getIdFromEntry(entry))}>
            <Grid
              container
              spacing={1}
              alignItems="stretch"
              sx={[
                theme => ({
                  marginLeft: `${theme.spacing(-1)} !important`
                }),
                !dashboard?.length &&
                  !isEditing && {
                    height: '100%',
                    display: 'flex',
                    alignItems: 'center'
                  }
              ]}
            >
              {(dashboard ?? []).map(entry => {
                if (entry.type === 'view') {
                  const settings: ViewSettings = JSON.parse(entry.config);

                  return (
                    <EntryWrapper
                      key={entry.entry_id}
                      editing={isEditing}
                      id={settings.viewId}
                      onDelete={() =>
                        setLocalDashboard((dashboard ?? []).filter(_entry => _entry.entry_id !== getIdFromEntry(entry)))
                      }
                    >
                      <ViewCard key={entry.config} {...settings} />
                    </EntryWrapper>
                  );
                } else if (entry.type === 'analytic') {
                  const settings: AnalyticSettings = JSON.parse(entry.config);

                  return (
                    <EntryWrapper
                      key={entry.entry_id}
                      editing={isEditing}
                      id={getIdFromEntry(entry)}
                      onDelete={() =>
                        setLocalDashboard((dashboard ?? []).filter(_entry => _entry.entry_id !== getIdFromEntry(entry)))
                      }
                    >
                      <AnalyticCard key={entry.config} {...settings} />
                    </EntryWrapper>
                  );
                } else {
                  return null;
                }
              })}
              {isEditing && (
                <AddNewCard
                  dashboard={dashboard}
                  addCard={newCard => setStateDashboard(_dashboard => [...(_dashboard ?? []), newCard])}
                />
              )}
              {!dashboard?.length && !isEditing && (
                <Grid item xs={12}>
                  <Stack
                    direction="column"
                    spacing={2}
                    sx={theme => ({
                      height: '60vh',
                      borderStyle: 'dashed',
                      borderColor: theme.palette.text.secondary,
                      borderWidth: '1rem',
                      borderRadius: '1rem',
                      opacity: 0.3,
                      justifyContent: 'center',
                      alignItems: 'center',
                      padding: 3
                    })}
                  >
                    <Typography variant="h1" sx={{ display: 'flex', alignItems: 'center' }}>
                      <Stack direction="row" spacing={2.5}>
                        <AppBrand application="howler" variant="logo" size="large" />
                        <span>{t('route.home.title')}</span>
                      </Stack>
                    </Typography>
                    <Typography variant="h4" sx={{ textAlign: 'center' }}>
                      {t('route.home.description')}
                    </Typography>
                  </Stack>
                </Grid>
              )}
            </Grid>
          </SortableContext>
        </DndContext>
      </Stack>
    </PageCenter>
  );
};

export default Home;
