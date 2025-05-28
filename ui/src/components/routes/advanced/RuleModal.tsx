import {
  Box,
  Button,
  Card,
  CardHeader,
  CircularProgress,
  Divider,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography,
  useTheme
} from '@mui/material';
import api from 'api';
import { parseEvent } from 'commons/components/utils/keyboard';
import { ModalContext } from 'components/app/providers/ModalProvider';
import CustomButton from 'components/elements/addons/buttons/CustomButton';
import Markdown from 'components/elements/display/Markdown';
import ThemedEditor from 'components/elements/ThemedEditor';
import useMyApi from 'components/hooks/useMyApi';
import useMySnackbar from 'components/hooks/useMySnackbar';
import type { Analytic } from 'models/entities/generated/Analytic';
import type { FC } from 'react';
import { useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate } from 'react-router-dom';
import { RULE_INTERVALS } from 'utils/constants';

const RuleModal: FC<{ onSubmit: () => void; fileData: string; type: 'eql' | 'lucene' | 'yaml' }> = ({
  onSubmit,
  fileData,
  type
}) => {
  const { t } = useTranslation();
  const theme = useTheme();
  const { close } = useContext(ModalContext);
  const { dispatchApi } = useMyApi();
  const { showSuccessMessage } = useMySnackbar();
  const navigate = useNavigate();
  const location = useLocation();

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [crontab, setCrontab] = useState<string>(RULE_INTERVALS[3].crontab);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<'query' | 'description'>('description');

  const badAnalyticName = useMemo(() => !/^([A-Z][a-z]* ?)*$/.test(name), [name]);

  const handleSubmit = useCallback(async () => {
    try {
      setLoading(true);

      const newAnalytic = await dispatchApi(
        api.analytic.rules.post({
          name,
          description,
          // Converting the language name to the query type - they all match except sigma
          rule_type: type.replace('yaml', 'sigma') as Analytic['rule_type'],
          rule: fileData,
          rule_crontab: crontab
        })
      );

      showSuccessMessage(t('modal.rule.success'), 5000, {
        action: () => (
          <Button color="inherit" onClick={() => navigate(`/analytics/${newAnalytic.analytic_id}`)}>
            {t('open')}
          </Button>
        )
      });

      onSubmit();
      close();
    } finally {
      setLoading(false);
    }
  }, [dispatchApi, name, description, type, fileData, crontab, showSuccessMessage, t, onSubmit, close, navigate]);

  const handleKeydown = useCallback(
    e => {
      const parsedEvent = parseEvent(e);

      if (parsedEvent.isCtrl && parsedEvent.isEnter) {
        e.stopPropagation();
        e.preventDefault();
        handleSubmit();
      } else if (parsedEvent.isEscape) {
        e.stopPropagation();
        e.preventDefault();
        close();
      }
    },
    [close, handleSubmit]
  );

  useEffect(() => {
    if (location.pathname !== '/advanced') {
      close();
    }
  }, [close, location.pathname]);

  return (
    <Stack spacing={2} p={2} alignItems="start" sx={{ minWidth: '60vw', height: '80vh', overflow: 'hidden' }}>
      <Typography variant="h4">{t('modal.rule.title')}</Typography>
      <Typography>{t('modal.rule.description')}</Typography>
      <Stack direction="row" spacing={1} sx={{ width: '100%' }}>
        <TextField
          label={t('modal.rule.name') + (badAnalyticName ? ` - ${t('modal.rule.name.warn')}` : '')}
          value={name}
          fullWidth
          color={badAnalyticName ? 'warning' : null}
          multiline
          maxRows={6}
          onChange={e => setName(e.target.value)}
          onKeyDown={handleKeydown}
        />
        {/* TODO: allow custom crontabs ala spellbook */}
        <FormControl sx={{ minWidth: '250px' }}>
          <InputLabel>{t('rule.interval')}</InputLabel>
          <Select
            label={t('rule.interval')}
            onChange={event => setCrontab(event.target.value)}
            value={crontab}
            MenuProps={{ style: { zIndex: 1500 } }}
          >
            {RULE_INTERVALS.map(interval => (
              <MenuItem key={interval.key} value={interval.crontab}>
                {t(interval.key)}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Stack>
      <Tabs value={tab} onChange={(__, value) => setTab(value)}>
        <Tab label={t('description')} value="description" />
        <Tab label={t('query')} value="query" />
      </Tabs>
      {tab === 'description' && (
        <Box
          display="grid"
          alignSelf="stretch"
          sx={{ pt: 1, flex: 1, overflow: 'hidden', gridTemplateColumns: '1fr 1fr', gap: theme.spacing(1) }}
          justifyContent="stretch"
        >
          <Card variant="outlined" sx={{ p: 1 }}>
            <CardHeader sx={{ py: 1, px: 0 }} title={t('modal.rule.description.title')} />
            <Divider />
            <ThemedEditor
              height="90%"
              width="100%"
              theme="howler"
              language="markdown"
              value={description}
              onChange={value => setDescription(value)}
              options={{
                minimap: { enabled: false },
                overviewRulerBorder: false,
                renderLineHighlight: 'gutter',
                fontSize: 16,
                autoClosingBrackets: 'always'
              }}
            />
          </Card>
          <Card variant="outlined" sx={{ p: 1 }}>
            <CardHeader sx={{ py: 1, px: 0 }} title={t('modal.rule.markdown.title')} />
            <Divider />
            <Markdown md={description || t('modal.rule.markdown.placeholder')} />
          </Card>
        </Box>
      )}
      {tab === 'query' && (
        <Card variant="outlined" sx={{ p: 1, overflow: 'auto', width: '100%', height: '100%' }}>
          <CardHeader sx={{ py: 1, px: 0 }} title={t('modal.rule.file.title')} />
          <Divider />
          <ThemedEditor
            height="90%"
            width="100%"
            theme="howler"
            language={type}
            value={fileData}
            options={{
              minimap: { enabled: false },
              readOnly: true,
              overviewRulerBorder: false,
              renderLineHighlight: 'gutter',
              fontSize: 16,
              autoClosingBrackets: 'always'
            }}
          />
        </Card>
      )}
      <Stack direction="row" spacing={1} alignSelf="end">
        <Button color="error" variant="outlined" onClick={close}>
          {t('cancel')}
        </Button>
        <CustomButton
          startIcon={loading && <CircularProgress color="success" size={18} />}
          color="success"
          variant="outlined"
          onClick={handleSubmit}
          disabled={!name || !description || !crontab}
          tooltip={(!name || !description) && t(`modal.rule.disabled.${!name ? 'analytic' : 'description'}`)}
        >
          {t('submit')}
        </CustomButton>
      </Stack>
    </Stack>
  );
};

export default RuleModal;
