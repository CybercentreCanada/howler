import { Box, Divider, Stack, Typography } from '@mui/material';
import HandlebarsMarkdown from 'components/elements/display/HandlebarsMarkdown';
import Markdown from 'components/elements/display/Markdown';
import type { Hit } from 'models/entities/generated/Hit';
import type { Lead } from 'models/entities/generated/Lead';
import { memo, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { usePluginStore } from 'react-pluggable';

const LeadRenderer: FC<{ lead: Lead; hit?: Hit }> = ({ lead, hit }) => {
  const { t } = useTranslation();
  const pluginStore = usePluginStore();

  if (lead.format === 'markdown') {
    let isAiTriageLead = false;
    try {
      isAiTriageLead = (JSON.parse(lead.metadata ?? '{}') as { owner?: string }).owner === 'howler.ai_triage';
    } catch {
      // Invalid metadata is treated as a regular, trusted lead.
    }

    return (
      <Box
        sx={{
          mt: -2
        }}
      >
        {isAiTriageLead ? (
          <Markdown md={lead.content!} disableLinks untrusted />
        ) : (
          <HandlebarsMarkdown disableLinks md={lead.content!} object={hit ?? lead} />
        )}
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
