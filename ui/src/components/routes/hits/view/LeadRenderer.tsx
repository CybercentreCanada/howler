import { Box, Divider, Stack, Typography } from '@mui/material';
import HandlebarsMarkdown from 'components/elements/display/HandlebarsMarkdown';
import type { Hit } from 'models/entities/generated/Hit';
import type { Lead } from 'models/entities/generated/Lead';
import { memo, type FC } from 'react';
import { useTranslation } from 'react-i18next';

const LeadRenderer: FC<{ lead: Lead; hit?: Hit }> = ({ lead, hit }) => {
  const { t } = useTranslation();

  if (lead.format === 'markdown') {
    return (
      <Box
        sx={{
          mt: -2
        }}
      >
        <HandlebarsMarkdown disableLinks md={lead.content} object={hit ?? lead} />
      </Box>
    );
  }

  return (
    <Stack p={3} direction="column" spacing={2} alignItems="center">
      <Typography variant="h3" color="error.light">
        {t('lead.invalid')}
      </Typography>
      <Divider flexItem />
      <Typography variant="body1">{t('lead.invalid.description')}</Typography>
    </Stack>
  );
};

export default memo(LeadRenderer);
