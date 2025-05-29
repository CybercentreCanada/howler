import { Add, Delete, Label, LinkRounded, Plagiarism } from '@mui/icons-material';
import {
  Box,
  Card,
  CircularProgress,
  Divider,
  FormControl,
  Grid,
  IconButton,
  InputAdornment,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Tooltip,
  Typography
} from '@mui/material';
import api from 'api';
import { useAppUser } from 'commons/components/app/hooks';
import FlexOne from 'components/elements/addons/layout/FlexOne';
import HowlerAvatar from 'components/elements/display/HowlerAvatar';
import HitNotebooks from 'components/elements/hit/HitNotebooks';
import useMyApi from 'components/hooks/useMyApi';
import type { HowlerUser } from 'models/entities/HowlerUser';
import type { Analytic } from 'models/entities/generated/Analytic';
import { useCallback, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { safeStringPropertyCompare } from 'utils/stringUtils';

const AnalyticNotebooks: FC<{ analytic: Analytic; setAnalytic: (a: Analytic) => void }> = ({
  analytic,
  setAnalytic
}) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const { user } = useAppUser<HowlerUser>();
  const [loading, setLoading] = useState(false);
  const [formState, setFormState] = useState<{ name: string; link: string; detection: string }>({
    name: '',
    link: '',
    detection: ''
  });

  const onSubmit = useCallback(async () => {
    setLoading(true);
    try {
      const result = await dispatchApi(
        api.analytic.notebooks.post(analytic.analytic_id, { ...formState, value: formState.link }),
        {
          showError: true,
          throwError: false,
          logError: false
        }
      );

      if (result) {
        setFormState({
          name: '',
          link: '',
          detection: ''
        });

        setAnalytic(result);
      }
    } finally {
      setLoading(false);
    }
  }, [analytic, dispatchApi, formState, setAnalytic]);

  const onDelete = useCallback(
    async (id: string) => {
      await dispatchApi(api.analytic.notebooks.del(analytic.analytic_id, [id]));

      setAnalytic({ ...analytic, notebooks: analytic.notebooks.filter(n => n.id !== id) });
    },
    [analytic, dispatchApi, setAnalytic]
  );

  return (
    <Stack direction="column" py={2} spacing={1}>
      <Box sx={{ flexGrow: 1 }}>
        <Grid container spacing={1}>
          <Grid item xs={6} md={2}>
            <FormControl fullWidth>
              <InputLabel id="select-label">{'Detection'}</InputLabel>
              <Select
                labelId="select-label"
                label="Detection"
                value={formState.detection}
                onChange={ev => {
                  setFormState({ ...formState, detection: ev.target.value });
                }}
                startAdornment={
                  <InputAdornment position="start">
                    <Plagiarism />
                  </InputAdornment>
                }
              >
                <MenuItem value="">{t('analytic.notebook.dropdown.none')}</MenuItem>
                {analytic?.detections?.map(d => (
                  <MenuItem value={d} key={d}>
                    {d}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={6} md={2}>
            <TextField
              fullWidth
              label={t('analytic.notebook.name')}
              value={formState.name}
              onChange={ev => {
                setFormState({ ...formState, name: ev.currentTarget.value });
              }}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <Label />
                  </InputAdornment>
                )
              }}
            />
          </Grid>

          <Grid item xs={12} md={8}>
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <TextField
                fullWidth
                label={t('analytic.notebook.link')}
                value={formState.link}
                onChange={ev => {
                  setFormState({ ...formState, link: ev.currentTarget.value });
                }}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <LinkRounded />
                    </InputAdornment>
                  )
                }}
              />
              <IconButton disabled={!formState.link || !formState.name} onClick={() => !loading && onSubmit()}>
                {loading ? <CircularProgress /> : <Add />}
              </IconButton>
            </Box>
          </Grid>
        </Grid>
      </Box>
      <Divider orientation="horizontal" flexItem />
      {analytic?.notebooks?.sort(safeStringPropertyCompare('detection')).map(n => (
        <Card variant="outlined" sx={{ p: 1, mb: 1 }} key={n.id}>
          <Stack direction="row" alignItems="center" spacing={1}>
            <HowlerAvatar
              sx={{ width: 24, height: 24, marginRight: '8px !important', marginLeft: '8px !important' }}
              userId={n.user}
            />
            <Stack>
              <Stack direction="row" alignItems="center" spacing={1}>
                <Typography variant="body1">{n.name}</Typography>
              </Stack>
              <Typography variant="caption">
                <code>{n.value}</code>
              </Typography>
            </Stack>
            <FlexOne />
            <Typography variant="caption">{n.detection ?? ''}</Typography>
            <HitNotebooks analytic={analytic} selectedNotebook={n.name} />
            {(n?.user === user.username || user.roles?.includes('admin')) && (
              <Tooltip title={'Remove'}>
                <IconButton onClick={() => onDelete(n.id)}>
                  <Delete />
                </IconButton>
              </Tooltip>
            )}
          </Stack>
        </Card>
      ))}
    </Stack>
  );
};

export default AnalyticNotebooks;
