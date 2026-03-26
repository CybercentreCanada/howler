import { Card, CardContent, Chip, Stack, Typography } from '@mui/material';
import type { Case } from 'models/entities/generated/Case';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

export type AssetType = 'hash' | 'hosts' | 'ip' | 'user' | 'ids' | 'id' | 'uri' | 'signature';

export interface AssetEntry {
  type: AssetType;
  value: string;
  /** IDs of the hits/observables this asset was seen in */
  seenIn: string[];
}

const Asset: FC<{ asset: AssetEntry; case: Case }> = ({ asset, case: _case }) => {
  const { t } = useTranslation();

  return (
    <Card sx={{ height: '100%' }}>
      <CardContent>
        <Stack spacing={1}>
          <Stack direction="row" alignItems="center" spacing={1}>
            <Chip size="small" label={t(`page.cases.assets.type.${asset.type}`)} color="primary" variant="outlined" />
            <Typography variant="body2" sx={{ wordBreak: 'break-all', fontFamily: 'monospace' }}>
              {asset.value}
            </Typography>
          </Stack>

          {asset.seenIn.length > 0 && (
            <Stack spacing={0.5}>
              <Typography variant="caption" color="text.secondary">
                {t('page.cases.assets.seen_in')}
              </Typography>
              <Stack direction="row" flexWrap="wrap" gap={0.5}>
                {asset.seenIn.map(id => {
                  const entry = _case.items.find(item => item.value === id);

                  return (
                    <Chip
                      key={id}
                      clickable
                      size="small"
                      label={entry.path}
                      variant="outlined"
                      component={Link}
                      to={`/cases/${_case.case_id}/${entry.path}`}
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

export default Asset;
