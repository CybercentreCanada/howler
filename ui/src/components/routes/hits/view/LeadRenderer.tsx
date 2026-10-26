import { Box, Divider, Stack, Typography } from '@mui/material';
import AiTriageMarkdown from 'components/elements/display/AiTriageMarkdown';
import HandlebarsMarkdown from 'components/elements/display/HandlebarsMarkdown';
import type { Hit } from 'models/entities/generated/Hit';
import type { Lead } from 'models/entities/generated/Lead';
import { memo, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { usePluginStore } from 'react-pluggable';

const LeadRenderer: FC<{ lead: Lead; hit?: Hit }> = ({ lead, hit }) => {
  const { t } = useTranslation();
  const pluginStore = usePluginStore();

  const isAiTriageLead = (() => {
    try {
      const metadata = JSON.parse(lead.metadata ?? '{}') as { owner?: string };
      return metadata.owner === 'howler.ai_triage';
    } catch {
      return false;
    }
  })();

  if (lead.format === 'markdown' && isAiTriageLead) {
    return (
      <Box sx={{ mt: -2 }}>
        <AiTriageMarkdown md={lead.content ?? ''} />
      </Box>
    );
  }

  if (lead.format === 'markdown') {
    return (
      <Box
        sx={{
          mt: -2
        }}
      >
        <HandlebarsMarkdown disableLinks md={lead.content!} object={hit ?? lead} />
      </Box>
    );
  }

  const pluginLead = pluginStore.executeFunction(`lead.${lead.format}`, lead.content, lead.metadata, hit);

  if (pluginLead) {
    return pluginLead;
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
