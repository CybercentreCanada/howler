import { Article, ChevronRight, Circle, Dashboard, Folder as FolderIcon } from '@mui/icons-material';
import { Box, Card, Chip, Divider, Skeleton, Stack, Typography, useTheme } from '@mui/material';
import dayjs from 'dayjs';
import { get, isEmpty, last, omit, set } from 'lodash-es';
import type { Case } from 'models/entities/generated/Case';
import type { Item } from 'models/entities/generated/Item';
import { useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation } from 'react-router-dom';
import { ESCALATION_COLOR_MAP } from '../constants';

type Tree = { leaves?: Item[]; [folder: string]: Tree | Item[] };

const Folder: FC<{ folder: Tree; name?: string; step?: number }> = ({ folder, name, step = -1 }) => {
  const theme = useTheme();
  const location = useLocation();

  const [open, setOpen] = useState(true);

  return (
    <Stack sx={{ overflow: 'visible' }}>
      {name && (
        <Stack
          direction="row"
          pl={step * 1.5}
          py={0.25}
          sx={{
            cursor: 'pointer',
            transition: theme.transitions.create('background', { duration: 50 }),
            background: 'transparent',
            '&:hover': {
              background: theme.palette.grey[800]
            }
          }}
          onClick={() => setOpen(_open => !_open)}
        >
          <ChevronRight
            fontSize="small"
            color="disabled"
            sx={[
              { transition: theme.transitions.create('transform', { duration: 100 }), transform: 'rotate(0deg)' },
              open && { transform: 'rotate(90deg)' }
            ]}
          />
          <FolderIcon fontSize="small" color="disabled" />
          <Typography variant="caption" color="textSecondary" sx={{ userSelect: 'none', pl: 0.5, textWrap: 'nowrap' }}>
            {name}
          </Typography>
        </Stack>
      )}
      {open && (
        <>
          {Object.entries(omit(folder, 'leaves')).map(([path, subfolder]) => (
            <Folder key={path} name={path} folder={subfolder as Tree} step={step + 1} />
          ))}
          {folder.leaves?.map(leaf => (
            <Stack
              key={leaf.id}
              direction="row"
              pl={step * 1.5 + 1}
              py={0.25}
              sx={[
                {
                  cursor: 'pointer',
                  overflow: 'visible',
                  color: `${theme.palette.text.secondary} !important`,
                  textDecoration: 'none',
                  transition: theme.transitions.create('background', { duration: 100 }),
                  background: 'transparent',
                  '&:hover': {
                    background: theme.palette.grey[800]
                  }
                },
                decodeURIComponent(location.pathname).endsWith(leaf.path) && {
                  background: theme.palette.grey[800]
                }
              ]}
              component={Link}
              to={leaf.path}
            >
              <ChevronRight fontSize="small" sx={{ opacity: 0 }} />
              <Article fontSize="small" />
              <Typography
                variant="caption"
                color="textSecondary"
                sx={{ userSelect: 'none', pl: 0.5, textWrap: 'nowrap' }}
              >
                {last(leaf.path.split('/'))}
              </Typography>
            </Stack>
          ))}
        </>
      )}
    </Stack>
  );
};

const CaseSidebar: FC<{ case: Case }> = ({ case: _case }) => {
  const { t } = useTranslation();
  const theme = useTheme();

  const tree: Tree = useMemo(() => {
    if (!_case) {
      return {};
    }

    const _tree: Tree = { leaves: [] };

    _case.items.forEach(item => {
      const parts = item.path.split('/');
      // Remove the name
      parts.pop();

      if (parts.length > 0) {
        const key = [...parts].join('.');

        const size = (get(_tree, key) as Tree)?.leaves?.length || 0;

        set(_tree, `${key}.leaves.${size}`, item);
      } else {
        _tree.leaves.push(item);
      }
    });

    return _tree;
  }, [_case]);

  return (
    <Box
      sx={{
        width: '350px',
        maxHeight: 'calc(100vh - 64px)',
        display: 'flex',
        flexDirection: 'column'
      }}
    >
      <Card sx={{ borderRadius: 0, px: 2, py: 1 }}>
        {_case?.title ? <Typography variant="body1">{_case.title}</Typography> : <Skeleton height={24} />}
        <Stack
          direction="row"
          spacing={1}
          alignItems="center"
          divider={<Circle color="disabled" sx={{ fontSize: '8px' }} />}
        >
          <Typography variant="caption" color="textSecondary">
            {t('started')}: {_case?.created ? dayjs(_case.created).toString() : <Skeleton height={14} />}
          </Typography>
          {_case?.escalation ? (
            <Chip size="small" color={ESCALATION_COLOR_MAP[_case.escalation]} label={t(_case.escalation)} />
          ) : (
            <Skeleton height={24} />
          )}
        </Stack>
      </Card>

      <Stack
        direction="row"
        alignItems="center"
        sx={{
          cursor: 'pointer',
          px: 1,
          py: 1,
          transition: theme.transitions.create('background', { duration: 100 }),
          color: `${theme.palette.text.primary} !important`,
          textDecoration: 'none',
          background: 'transparent',
          borderRight: `thin solid ${theme.palette.divider}`,
          '&:hover': {
            background: theme.palette.grey[800]
          }
        }}
        component={Link}
        to={`/cases/${_case?.case_id}`}
      >
        <Dashboard />
        <Typography sx={{ userSelect: 'none', pl: 0.5, textWrap: 'nowrap' }}>{t('page.cases.dashboard')}</Typography>
      </Stack>

      <Divider />

      {!isEmpty(tree) && (
        <Box
          flex={1}
          overflow="auto"
          width="100%"
          sx={{
            position: 'relative',
            borderRight: `thin solid ${theme.palette.divider}`
          }}
        >
          <Box position="absolute" sx={{ left: 0 }}>
            <Folder folder={tree} />
          </Box>
        </Box>
      )}
    </Box>
  );
};

export default CaseSidebar;
