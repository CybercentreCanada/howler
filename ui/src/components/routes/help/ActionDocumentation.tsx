import { Box, Stack, Tab, Typography, useMediaQuery, useTheme } from '@mui/material';
import PageCenter from 'commons/components/pages/PageCenter';
import { useScrollRestoration } from 'components/hooks/useScrollRestoration';
import type { FC } from 'react';
import { useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router-dom';
import ActionIntroductionDocumentation from './ActionIntroductionDocumentation';
import HelpTabs from './components/HelpTabs';

const ActionDocumentation: FC = () => {
  const { t } = useTranslation();
  const theme = useTheme();
  useScrollRestoration();

  const useHorizontal = useMediaQuery(theme.breakpoints.down(1700));

  const [searchParams, setSearchParams] = useSearchParams();
  const [tab, setTab] = useState(searchParams.get('tab') ?? 'introduction');

  const onChange = useCallback(
    (_tab: string) => {
      setTab(_tab);
      searchParams.set('tab', _tab);
      setSearchParams(new URLSearchParams(searchParams));
    },
    [searchParams, setSearchParams]
  );

  return (
    <PageCenter margin={4} width="100%" maxWidth="1750px" textAlign="left">
      <Stack sx={{ flexDirection: useHorizontal ? 'column' : 'row', '& h1': { mt: 0 } }}>
        <HelpTabs value={tab}>
          <Tab
            label={<Typography variant="caption">{t('help.actions.introduction')}</Typography>}
            value="introduction"
            onClick={() => onChange('introduction')}
          />
        </HelpTabs>
        <Box>
          {{
            introduction: () => <ActionIntroductionDocumentation />
          }[tab]()}
        </Box>
      </Stack>
    </PageCenter>
  );
};

export default ActionDocumentation;
