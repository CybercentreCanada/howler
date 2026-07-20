import { Card, CardContent, Chip, Stack, Typography } from '@mui/material';
import type { Case } from 'models/entities/generated/Case';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { buildPathFromID } from '../../utils';
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

          {observable.seenIn.length > 0 && (
            <Stack spacing={0.5}>
              <Typography variant="caption" color="text.secondary">
                {t('page.cases.observables.seen_in')}
              </Typography>
              <Stack direction="row" flexWrap="wrap" gap={0.5}>
                {observable.seenIn.map(id => {
                  const entry = _case.items.find(item => item.value === id);

                  return (
                    <Chip
                      key={id}
                      clickable
                      size="small"
                      label={entry.name}
                      variant="outlined"
                      component={Link}
                      to={`/cases/${_case.case_id}/${buildPathFromID(_case, entry.id)}`}
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
