import {
  Article,
  BookRounded,
  CheckCircle,
  ChevronRight,
  Folder as FolderIcon,
  Lightbulb,
  Link as LinkIcon,
  TableChart,
  Visibility
} from '@mui/icons-material';
import type { SvgIconProps } from '@mui/material';
import { Skeleton, Stack, Typography, useTheme } from '@mui/material';
import api from 'api';
import useMyApi from 'components/hooks/useMyApi';
import { omit } from 'lodash-es';
import type { Case } from 'models/entities/generated/Case';
import type { Hit } from 'models/entities/generated/Hit';
import type { Item } from 'models/entities/generated/Item';
import { useCallback, useEffect, useMemo, useState, type ComponentType, type FC } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ESCALATION_COLORS } from 'utils/constants';
import type { Tree } from './types';
import { buildTree } from './utils';

// Static map: item type → MUI icon component (avoids re-creating closures on each render)
const ICON_FOR_TYPE: Record<string, ComponentType<SvgIconProps>> = {
  case: BookRounded,
  observable: Visibility,
  hit: CheckCircle,
  table: TableChart,
  lead: Lightbulb,
  reference: LinkIcon
};

type CaseNodeState = { open: boolean; loading: boolean; data: Case | null };

interface CaseFolderProps {
  case: Case;
  folder?: Tree;
  name?: string;
  step?: number;
  rootCaseId?: string;
  pathPrefix?: string;
}

const CaseFolder: FC<CaseFolderProps> = ({ case: _case, folder, name, step = -1, rootCaseId, pathPrefix = '' }) => {
  const theme = useTheme();
  const location = useLocation();
  const { dispatchApi } = useMyApi();

  const [open, setOpen] = useState(true);
  const [caseStates, setCaseStates] = useState<Record<string, CaseNodeState>>({});
  const [hitMetadata, setHitMetadata] = useState<{ [id: string]: Hit['howler'] }>({});

  const tree = useMemo(() => folder || buildTree(_case?.items), [folder, _case?.items]);
  const currentRootCaseId = rootCaseId || _case?.case_id;

  // Stable string key so the effect only re-runs when the actual hit IDs change,
  // not on every array reference change.
  const hitIds = useMemo(
    () =>
      tree.leaves
        ?.filter(l => l.type?.toLowerCase() === 'hit')
        .map(l => l.id)
        .filter(id => !!id) ?? [],
    [tree.leaves]
  );

  useEffect(() => {
    if (hitIds.length < 1) {
      return;
    }

    dispatchApi(api.search.hit.post({ query: `howler.id:(${hitIds.join(' OR ')})` }), { throwError: false }).then(
      result => {
        if ((result?.items?.length ?? 0) < 1) return;
        setHitMetadata(Object.fromEntries(result.items.map(hit => [hit.howler.id, hit.howler])));
      }
    );
  }, [hitIds, dispatchApi]);

  // Returns the MUI colour token for the item's escalation, or undefined if none.
  const getEscalationColor = (itemType: string | undefined, itemKey: string | undefined, leafId: string) => {
    if (itemType === 'hit' && leafId) {
      const color = ESCALATION_COLORS[hitMetadata[leafId]?.escalation as keyof typeof ESCALATION_COLORS];
      if (color) return color;
    }
    if (itemType === 'case' && itemKey) {
      const color = ESCALATION_COLORS[caseStates[itemKey]?.data?.escalation as keyof typeof ESCALATION_COLORS];
      if (color) return color;
    }
    return undefined;
  };

  const toggleCase = useCallback(
    (item: Item, itemKey?: string) => {
      const resolvedKey = itemKey || item.path || item.id;
      if (!resolvedKey) return;

      const prev = caseStates[resolvedKey] ?? { open: false, loading: false, data: null };
      const shouldOpen = !prev.open;

      setCaseStates(current => ({ ...current, [resolvedKey]: { ...prev, open: shouldOpen } }));

      if (!shouldOpen || !item.id || prev.data || prev.loading) return;

      setCaseStates(current => ({
        ...current,
        [resolvedKey]: { ...(current[resolvedKey] ?? prev), loading: true }
      }));

      dispatchApi(api.v2.case.get(item.id), { throwError: false })
        .then(caseResponse => {
          if (!caseResponse) return;
          setCaseStates(current => ({ ...current, [resolvedKey]: { ...current[resolvedKey], data: caseResponse } }));
        })
        .finally(() => {
          setCaseStates(current => ({ ...current, [resolvedKey]: { ...current[resolvedKey], loading: false } }));
        });
    },
    [caseStates, dispatchApi]
  );

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
          {Object.entries(omit(tree, 'leaves')).map(([path, subfolder]) => (
            <CaseFolder
              key={`${_case?.case_id}-${path}`}
              name={path}
              case={_case}
              folder={subfolder as Tree}
              step={step + 1}
              rootCaseId={currentRootCaseId}
              pathPrefix={pathPrefix}
            />
          ))}

          {tree.leaves?.map(leaf => {
            const itemType = leaf.type?.toLowerCase();
            const isCase = itemType === 'case';
            const fullRelativePath = [pathPrefix, leaf.path].filter(Boolean).join('/');
            const itemKey = fullRelativePath || leaf.id;
            const nodeState = itemKey ? caseStates[itemKey] : null;
            const isCaseOpen = !!nodeState?.open;
            const isCaseLoading = !!nodeState?.loading;
            const nestedCase = nodeState?.data ?? null;
            const itemPath =
              itemType !== 'reference'
                ? fullRelativePath
                  ? `/cases/${currentRootCaseId}/${fullRelativePath}`
                  : `/cases/${currentRootCaseId}`
                : leaf.value;

            const escalationColor = getEscalationColor(itemType, itemKey, leaf.id);
            const iconColor = escalationColor ?? ('inherit' as const);
            const leafColor = escalationColor ? `${escalationColor}.light` : 'text.secondary';
            const Icon = ICON_FOR_TYPE[itemType ?? ''] ?? Article;

            return (
              <Stack key={`${_case?.case_id}-${leaf.id}-${leaf.path}`}>
                <Stack
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
                    decodeURIComponent(location.pathname) === itemPath && {
                      background: theme.palette.grey[800]
                    }
                  ]}
                  onClick={() => isCase && toggleCase(leaf, itemKey)}
                  component={Link}
                  to={itemPath}
                  target={itemType === 'reference' ? '_blank' : undefined}
                  rel={itemType === 'reference' ? 'noopener noreferrer' : undefined}
                >
                  <ChevronRight
                    fontSize="small"
                    sx={[
                      !isCase && { opacity: 0 },
                      isCase && {
                        transition: theme.transitions.create('transform', { duration: 100 }),
                        transform: isCaseOpen ? 'rotate(90deg)' : 'rotate(0deg)'
                      }
                    ]}
                  />

                  <Icon fontSize="small" color={iconColor} />

                  <Typography
                    variant="caption"
                    color={leafColor}
                    sx={{ userSelect: 'none', pl: 0.5, textWrap: 'nowrap' }}
                  >
                    {leaf.path?.split('/').pop() || leaf.id}
                  </Typography>
                </Stack>

                {isCase && isCaseOpen && isCaseLoading && (
                  <Stack pl={step * 1.5 + 4} py={0.25}>
                    <Skeleton width={140} height={16} />
                  </Stack>
                )}

                {isCase && isCaseOpen && nestedCase && (
                  <CaseFolder
                    case={nestedCase}
                    step={step + 1}
                    rootCaseId={currentRootCaseId}
                    pathPrefix={fullRelativePath}
                  />
                )}
              </Stack>
            );
          })}
        </>
      )}
    </Stack>
  );
};

export default CaseFolder;
