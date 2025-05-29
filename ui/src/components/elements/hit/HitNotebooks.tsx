import {
  Avatar,
  Backdrop,
  Box,
  Button,
  Chip,
  CircularProgress,
  ClickAwayListener,
  Fade,
  MenuItem,
  Paper,
  Popper,
  Stack,
  TextField
} from '@mui/material';
import api from 'api';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import { ModalContext } from 'components/app/providers/ModalProvider';
import useMyApi from 'components/hooks/useMyApi';
import useMySnackbar from 'components/hooks/useMySnackbar';
import type { Analytic } from 'models/entities/generated/Analytic';
import type { Hit } from 'models/entities/generated/Hit';
import type { FC } from 'react';
import { memo, useCallback, useContext, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { safeStringPropertyCompare } from 'utils/stringUtils';
import HowlerCard from '../display/HowlerCard';
import ConfirmNotebookModal from '../display/modals/ConfirmNotebookModal';

const FETCH_OPTIONS: RequestInit = {
  credentials: 'include',
  headers: {
    Accept: '*/*',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-site'
  },
  mode: 'cors'
};

type Envs = { name: string; url: string; default: boolean; user_interface: string };

const HitNotebooks: FC<{ analytic: Analytic; selectedNotebook?: string; hit?: Hit }> = ({
  analytic,
  selectedNotebook,
  hit
}) => {
  const { t } = useTranslation();
  const { config } = useContext(ApiConfigContext);
  const { showErrorMessage } = useMySnackbar();
  const { dispatchApi } = useMyApi();
  const [open, setOpen] = useState(false);
  const [envs, setEnvs] = useState<Envs[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [loadedNotebook, setLoadedNotebook] = useState<{ nb_content: any; name: string }>({
    nb_content: null,
    name: ''
  });
  const [anchorEl, setAnchorEl] = useState<HTMLDivElement | null>(null);

  const { showModal } = useContext(ModalContext);

  const handleToggle = (event: React.MouseEvent<HTMLDivElement>) => {
    setAnchorEl(event.currentTarget);
    setOpen(prev => !prev);
  };

  const goToJupyhub = useCallback(
    async (filename: string, url: string) => {
      try {
        await fetch(url, {
          ...FETCH_OPTIONS,
          method: 'post',
          body: `{"type":"notebook","content":${JSON.stringify(loadedNotebook.nb_content)}}`
        });

        window.open(`${envs[0].url}lab/tree/${filename}`, '_blank');
        setOpen(false);
      } catch (e) {
        showErrorMessage(t('hit.notebook.error.failToPost'));
      }
    },
    [envs, loadedNotebook, showErrorMessage, t]
  );

  const checkJupyhub = useCallback(async () => {
    setLoading(true);

    const nbFileName = hit ? `${loadedNotebook.name} - ${hit.howler.id}.ipynb` : `${loadedNotebook.name}.ipynb`;

    //using fetch since we are going directly to jupyterhub
    try {
      const response = await fetch(`${envs[0].url}api/contents/${nbFileName}`, FETCH_OPTIONS);
      if (response.status < 300) {
        // if it exists, we need to ask for overwrite
        showModal(
          <ConfirmNotebookModal
            onConfirm={() => {
              goToJupyhub(nbFileName, `${envs[0].url}post/${nbFileName}`);
            }}
          />
        );
      } else {
        goToJupyhub(nbFileName, `${envs[0].url}post/${nbFileName}`);
      }
    } catch (e) {
      // error means notebook doesn't exist, we can proceed with posting
      goToJupyhub(nbFileName, `${envs[0].url}post/${nbFileName}`);
    }

    setLoading(false);
  }, [envs, goToJupyhub, hit, loadedNotebook, showModal]);

  const fetchEnvs = useCallback(async () => {
    setLoading(true);
    try {
      const jhEnvs = await dispatchApi(api.notebook.environments.get(), { showError: true, throwError: false });
      setEnvs(jhEnvs.envs.map(env => ({ ...env, url: env.url.endsWith('/') ? env.url : env.url + '/' })));
    } finally {
      setLoading(false);
    }
  }, [dispatchApi]);

  // retrieve notebook json from howler-api/nbgallery
  const fetchNb = useCallback(
    async (link?: string) => {
      setLoading(true);
      try {
        const notebookResponse = await dispatchApi(
          api.notebook.post({
            link: link ?? analytic?.notebooks.find(n => n.name === selectedNotebook).value,
            analytic: analytic,
            ...(hit ? { hit: hit } : {})
          }),
          {
            showError: true,
            throwError: false
          }
        );
        setLoadedNotebook(notebookResponse);
      } finally {
        setLoading(false);
      }
    },
    [analytic, dispatchApi, hit, selectedNotebook]
  );

  useEffect(() => {
    if (open) {
      fetchEnvs(); //retrieve env info from howler-api/nbgallery
      if (selectedNotebook) {
        fetchNb();
      }
    } else {
      setLoadedNotebook({
        nb_content: null,
        name: ''
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  return (
    config.configuration.features.notebook &&
    analytic?.notebooks && (
      <ClickAwayListener onClickAway={() => setOpen(false)} mouseEvent={'onMouseUp'}>
        <div>
          <Popper open={open} anchorEl={anchorEl} placement={'bottom'} transition sx={{ zIndex: 1499 }}>
            {({ TransitionProps }) => (
              <Fade {...TransitionProps} timeout={350}>
                <Paper sx={{ maxWidth: '90%', width: '400px', p: 1, position: 'relative' }}>
                  <Backdrop open={loading} sx={{ position: 'absolute', zIndex: theme => theme.zIndex.drawer + 1 }}>
                    <Stack direction="column">
                      <div style={{ textAlign: 'center' }}>
                        <CircularProgress color="inherit" />
                      </div>
                    </Stack>
                  </Backdrop>
                  <Stack direction="column" spacing={2} sx={{ p: 1 }}>
                    <TextField
                      disabled={!!selectedNotebook}
                      label="Notebook"
                      select
                      onChange={e => {
                        fetchNb(e.target.value);
                      }}
                      SelectProps={{
                        MenuProps: {
                          style: { zIndex: 35001 }
                        }
                      }}
                      defaultValue={
                        selectedNotebook ? analytic?.notebooks.find(n => n.name === selectedNotebook).value : ''
                      }
                    >
                      <MenuItem disabled value="">
                        <em>{t('hit.notebook.select')}</em>
                      </MenuItem>
                      {analytic?.notebooks.sort(safeStringPropertyCompare('detection')).map(e => (
                        <MenuItem value={e.value} key={e.value}>
                          <Stack direction={'row'} sx={{ width: '100%' }}>
                            {e.name}
                            {e.detection && (
                              <>
                                <Box flex={1} />
                                <Chip label={e.detection} size="small"></Chip>
                              </>
                            )}
                          </Stack>
                        </MenuItem>
                      ))}
                    </TextField>
                    <Button
                      variant="outlined"
                      disabled={loadedNotebook.name === '' || envs.length === 0}
                      color="success"
                      onClick={() => checkJupyhub()}
                    >
                      {t('hit.notebook.goTo')}
                    </Button>
                  </Stack>
                </Paper>
              </Fade>
            )}
          </Popper>
          <HowlerCard
            variant="elevation"
            onClick={handleToggle}
            sx={[
              theme => ({
                cursor: 'pointer',
                backgroundColor: 'transparent',
                transition: theme.transitions.create(['border-color']),
                '&:hover': { borderColor: 'primary.main' }
              }),
              { border: 'thin solid', borderColor: 'transparent' }
            ]}
          >
            <Stack direction="row" p={1} spacing={1} alignItems="center">
              <Avatar
                variant="rounded"
                src={'/images/jupyter_notebook_file_icon.png'}
                sx={[
                  theme => ({
                    width: theme.spacing(3),
                    height: theme.spacing(3),
                    '& img': {
                      objectFit: 'contain'
                    }
                  })
                ]}
              >
                {'jupyter_notebook_file_icon.png'}
              </Avatar>
              {t('hit.notebook.tooltip')}
            </Stack>
          </HowlerCard>
        </div>
      </ClickAwayListener>
    )
  );
};

export default memo(HitNotebooks);
