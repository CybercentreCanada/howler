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
import { Skeleton, Stack, Typography, useTheme } from '@mui/material';
import api from 'api';
import useMyApi from 'components/hooks/useMyApi';
import { get, last, omit, set } from 'lodash-es';
import type { Case } from 'models/entities/generated/Case';
import type { Hit } from 'models/entities/generated/Hit';
import type { Item } from 'models/entities/generated/Item';
import { useEffect, useMemo, useState, type FC } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ESCALATION_COLORS } from 'utils/constants';
import type { Tree } from './types';

const buildTree = (items: Item[] = []): Tree => {
  // Root tree node stores direct children in `leaves` and nested folders as object keys.
  const tree: Tree = { leaves: [] };

  items.forEach(item => {
    // Ignore items that cannot be placed in the folder structure.
    if (!item?.path) {
      return;
    }

    // Split path into folder segments + item name, then remove the item name.
    const parts = item.path.split('/');
    parts.pop();

    if (parts.length > 0) {
      // Use dot notation so lodash `get/set` can address nested folder objects.
      const key = parts.join('.');
      const size = (get(tree, key) as Tree)?.leaves?.length || 0;

      // Append this item to the folder's `leaves` array.
      set(tree, `${key}.leaves.${size}`, item);
      return;
    }

    // Items without parent folders are top-level leaves.
    tree.leaves.push(item);
  });

  return tree;
};

const CaseFolder: FC<{
  case: Case;
  folder?: Tree;
  name?: string;
  step?: number;
  rootCaseId?: string;
  pathPrefix?: string;
}> = ({ case: _case, folder, name, step = -1, rootCaseId, pathPrefix = '' }) => {
  const theme = useTheme();
  const location = useLocation();
  const { dispatchApi } = useMyApi();

  const [open, setOpen] = useState(true);
  const [openCases, setOpenCases] = useState<Record<string, boolean>>({});
  const [loadingCases, setLoadingCases] = useState<Record<string, boolean>>({});
  const [nestedCases, setNestedCases] = useState<Record<string, Case>>({});
  const [hitMetadata, setHitMetadata] = useState({});

  const tree = useMemo(() => folder || buildTree(_case?.items), [folder, _case?.items]);
  const currentRootCaseId = rootCaseId || _case?.case_id;

  // Metadata for hit-type items
  useEffect(() => {
    tree.leaves
      ?.filter(leaf => leaf.type?.toLowerCase() === 'hit')
      .forEach(leaf => {
        dispatchApi(api.hit.get<Hit>(leaf.id), { throwError: false }).then(hit => {
          if (!hit) return;
          setHitMetadata(prev => ({
            ...prev,
            [leaf.id]: {
              status: hit.howler?.status,
              escalation: hit.howler?.escalation,
              assessment: hit.howler?.assessment
            }
          }));
        });
      });
  }, [tree.leaves, dispatchApi]);

  const getIconColor = (itemType: string | undefined, itemKey: string | undefined, leafId: string) => {
    if (itemType === 'hit' && leafId) {
      const meta = hitMetadata[leafId];
      if (meta?.escalation && ESCALATION_COLORS[meta.escalation]) {
        return ESCALATION_COLORS[meta.escalation];
      }
    }

    if (itemType === 'case' && itemKey) {
      const caseData = nestedCases[itemKey];
      if (caseData?.escalation && ESCALATION_COLORS[caseData.escalation]) {
        return ESCALATION_COLORS[caseData.escalation];
      }
    }

    return 'default' as const;
  };

  const getItemColor = (itemType: string | undefined, itemKey: string | undefined, leafId: string): string => {
    if (itemType === 'hit' && leafId) {
      const meta = hitMetadata[leafId];
      if (meta?.escalation && ESCALATION_COLORS[meta.escalation]) {
        return `${ESCALATION_COLORS[meta.escalation]}.light`;
      }
    }

    if (itemType === 'case' && itemKey) {
      const caseData = nestedCases[itemKey];
      if (caseData?.escalation && ESCALATION_COLORS[caseData.escalation]) {
        return `${ESCALATION_COLORS[caseData.escalation]}.light`;
      }
    }

    return 'text.secondary';
  };

  const toggleCase = (item: Item, itemKey?: string) => {
    // Use the fully-qualified path key when available so nested case toggles are unique.
    const resolvedItemKey = itemKey || item.path || item.id;

    if (!resolvedItemKey) {
      return;
    }

    // Toggle expand/collapse state for this case node.
    const shouldOpen = !openCases[resolvedItemKey];

    setOpenCases(current => ({ ...current, [resolvedItemKey]: shouldOpen }));

    // Only fetch when opening, with a valid case id, and when no fetch/data is already in-flight/cached.
    if (!shouldOpen || !item.id || nestedCases[resolvedItemKey] || loadingCases[resolvedItemKey]) {
      return;
    }

    setLoadingCases(current => ({ ...current, [resolvedItemKey]: true }));

    // Lazy-load the nested case content and cache it by the same unique key.
    dispatchApi(api.v2.case.get(item.id), { throwError: false })
      .then(caseResponse => {
        if (!caseResponse) {
          return;
        }

        setNestedCases(current => ({ ...current, [resolvedItemKey]: caseResponse }));
      })
      .finally(() => {
        setLoadingCases(current => ({ ...current, [resolvedItemKey]: false }));
      });
  };

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
            const isCaseOpen = !!(itemKey && openCases[itemKey]);
            const isCaseLoading = !!(itemKey && loadingCases[itemKey]);
            const nestedCase = itemKey ? nestedCases[itemKey] : null;
            const itemPath = fullRelativePath
              ? `/cases/${currentRootCaseId}/${fullRelativePath}`
              : `/cases/${currentRootCaseId}`;

            const getIconForType = () => {
              const iconColor = getIconColor(itemType, itemKey, leaf.id);

              switch (itemType) {
                case 'case':
                  return <BookRounded fontSize="small" color={iconColor} />;
                case 'observable':
                  return <Visibility fontSize="small" color={iconColor} />;
                case 'hit':
                  return <CheckCircle fontSize="small" color={iconColor} />;
                case 'table':
                  return <TableChart fontSize="small" color={iconColor} />;
                case 'lead':
                  return <Lightbulb fontSize="small" color={iconColor} />;
                case 'reference':
                  return <LinkIcon fontSize="small" color={iconColor} />;
                default:
                  return <Article fontSize="small" color={iconColor} />;
              }
            };

            const leafColor = getItemColor(itemType, itemKey, leaf.id);

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

                  {getIconForType()}

                  <Typography
                    variant="caption"
                    color={leafColor}
                    sx={{ userSelect: 'none', pl: 0.5, textWrap: 'nowrap' }}
                  >
                    {last(leaf.path?.split('/') || [])}
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
