import { Card, CardContent, Chip, Stack, Typography } from '@mui/material';
import type { Case } from 'models/entities/generated/Case';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import type { ObservableEntry } from '../types';

const Observable: FC<{ observable: ObservableEntry; case: Case }> = ({ observable, case: _case }) => {
  const { t } = useTranslation();

  return (
    <Card sx={{ height: '100%' }}>
      <CardContent>
        <Stack spacing={1}>
          <Stack direction="row" alignItems="center" spacing={1}>
            <Chip
              size="small"
              label={t(`page.cases.observables.type.${observable.type}`)}
              color="primary"
              variant="outlined"
            />
            <Typography variant="body2" sx={{ wordBreak: 'break-all', fontFamily: 'monospace' }}>
              {observable.value}
            </Typography>
          </Stack>

          {(observable.sources?.length ?? 0) > 0 && (
            <Stack spacing={0.5}>
              <Typography variant="caption" color="text.secondary">
                {t('page.cases.observables.seen_in')}
              </Typography>
              <Stack direction="row" flexWrap="wrap" gap={0.5}>
                {observable.sources?.map(source => {
                  if (!source.path) {
                    return <Chip key={source.id} size="small" label={source.label ?? source.id} variant="outlined" />;
                  }

                  return (
                    <Chip
                      key={source.id}
                      clickable
                      size="small"
                      label={source.label ?? source.id}
                      variant="outlined"
                      component={Link}
                      to={`/cases/${_case.case_id}/${source.path}`}
                    />
                  );
                })}
              </Stack>
            </Stack>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
};

export default Observable;
