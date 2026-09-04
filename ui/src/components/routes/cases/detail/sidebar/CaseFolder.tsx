import { Box, Skeleton, Stack, useTheme } from '@mui/material';
import api from 'api';
import { RecordContext } from 'components/app/providers/RecordProvider';
import useMyApi from 'components/hooks/useMyApi';
import type { Case } from 'models/entities/generated/Case';
import type { Item } from 'models/entities/generated/Item';
import { useCallback, useEffect, useMemo, useState, type FC } from 'react';
import { useParams } from 'react-router';
import { useContextSelector } from 'use-context-selector';
import { ESCALATION_COLORS } from 'utils/constants';
import { buildPathFromID } from '../../utils';
import CaseFolderContextMenu from './CaseFolderContextMenu';
import FolderEntry from './FolderEntry';
import type { Tree } from './types';
import { buildTree } from './utils';

type CaseNodeState = { open: boolean; loading: boolean; data: Case | null };

interface CaseFolderProps {
  case: Case;
  folder?: Tree;
  name?: string;
  step?: number;

  /**
   * The chain of case item IDs traversed from the root case to reach this
   * nested case. Empty at the top level.
   */
  parentCaseNames?: string[];

  /**
   * Increment this value to collapse all named sub-folders. The root folder
   * (no `name` prop) is never collapsed so items remain visible.
   */
  collapseKey?: number;

  onItemUpdated?: (newCase: Case) => void;
}

const CaseFolder: FC<CaseFolderProps> = ({
  case: _case,
  folder,
  name,
  step = -1,
  parentCaseNames = [],
  collapseKey,
  onItemUpdated
}) => {
  const theme = useTheme();
  const { dispatchApi } = useMyApi();
  const params = useParams();

  const [open, setOpen] = useState(!name || !collapseKey);
  const [caseStates, setCaseStates] = useState<Record<string, CaseNodeState>>({});

  // Collapse this folder (and clear nested case expansions) when the parent
  // signals collapse-all. Only named folders (not the invisible root) respond.
  useEffect(() => {
    if (!collapseKey) {
      return;
    }

    setCaseStates(_states =>
      Object.fromEntries(Object.entries(_states).map(([id, entry]) => [id, { ...entry, open: false }]))
    );

    if (name) {
      setOpen(false);
    }
  }, [collapseKey, name]);

  const records = useContextSelector(RecordContext, ctx => ctx.records);

  const tree = useMemo(() => folder || buildTree(_case?.items), [folder, _case?.items]);
  const rootCaseId = params.id;

  // Returns the MUI colour token for the item's escalation, or undefined if none.
  const getEscalationColor = (itemType: string, leaf: Item) => {
    if (itemType === 'hit' && leaf.value) {
      const color = ESCALATION_COLORS[records[leaf.value]?.howler?.escalation as keyof typeof ESCALATION_COLORS];
      if (color) {
        return color;
      }
    }

    if (itemType === 'case' && leaf.value) {
      const color = ESCALATION_COLORS[caseStates[leaf.value]?.data?.escalation as keyof typeof ESCALATION_COLORS];
      if (color) {
        return color;
      }
    }

    return null;
  };

  const toggleCase = useCallback(
    (item: Item) => {
      const prev = caseStates[item.value!] ?? { open: false, loading: false, data: null };
      const shouldOpen = !prev.open;
      const shouldFetch = shouldOpen && !!item.value && !prev.data && !prev.loading;

      setCaseStates(current => ({ ...current, [item.value!]: { ...prev, open: shouldOpen, loading: shouldFetch } }));

      if (!shouldFetch) {
        return;
      }

      void dispatchApi(api.v2.case.get(item.value!), { throwError: false })
        .then(caseResponse => {
          if (!caseResponse) {
            return;
          }
          setCaseStates(current => ({ ...current, [item.value!]: { ...current[item.value!], data: caseResponse } }));
        })
        .finally(() => {
          setCaseStates(current => ({ ...current, [item.value!]: { ...current[item.value!], loading: false } }));
        });
    },
    [caseStates, dispatchApi]
  );

  return (
    <Stack sx={{ overflow: 'visible' }}>
      {name && folder?.item && (
        <CaseFolderContextMenu case={_case} item={folder.item} onUpdate={onItemUpdated}>
          <Box
            sx={{
              transition: theme.transitions.create('background', { duration: 100 }),
              background: 'transparent',
              '&:hover': { background: theme.palette.grey[800] }
            }}
          >
            <FolderEntry
              caseId={_case.case_id === rootCaseId ? rootCaseId : null}
              indent={step * 1.5}
              label={name}
              chevronOpen={open}
              onClick={() => setOpen(_open => !_open)}
              entry={folder.item}
            />
          </Box>
        </CaseFolderContextMenu>
      )}

      {open && (
        <>
          {/* Case-type leaves always listed first, above folders */}
          {tree.leaves
            ?.filter(leaf => leaf.type?.toLowerCase() === 'case')
            .map(leaf => {
              const itemType = leaf.type?.toLowerCase();
              const nodeState = leaf.value ? caseStates[leaf.value] : null;
              const isCaseOpen = !!nodeState?.open;
              const isCaseLoading = !!nodeState?.loading;
              const nestedCase = nodeState?.data ?? null;
              const fullItemPath = [...parentCaseNames, leaf.name].filter(Boolean).join('/');
              const itemTo = `/cases/${rootCaseId}${fullItemPath ? `/${fullItemPath}` : ''}`;

              const escalationColor = getEscalationColor(itemType!, leaf);
              const iconColor = escalationColor ?? ('inherit' as const);
              const leafColor = escalationColor ? `${escalationColor}.light` : 'text.secondary';

              return (
                <CaseFolderContextMenu
                  key={`${_case?.case_id}-${leaf.id}-${leaf.value}`}
                  case={_case}
                  item={leaf}
                  onUpdate={onItemUpdated}
                >
                  <Stack>
                    <Box
                      sx={{
                        transition: theme.transitions.create('background', { duration: 100 }),
                        background: 'transparent',
                        '&:hover': { background: theme.palette.grey[800] }
                      }}
                    >
                      <FolderEntry
                        caseId={_case.case_id === rootCaseId ? rootCaseId : null}
                        indent={step * 1.5 + 1}
                        label={leaf.name ?? leaf.value ?? ''}
                        iconColor={iconColor}
                        labelColor={leafColor}
                        chevronOpen={isCaseOpen}
                        to={itemTo}
                        onClick={() => toggleCase(leaf)}
                        entry={leaf}
                      />
                    </Box>

                    {isCaseOpen && isCaseLoading && (
                      <Stack pl={step * 1.5 + 4} py={0.25}>
                        <Skeleton width={140} height={16} />
                      </Stack>
                    )}

                    {isCaseOpen && nestedCase && (
                      <CaseFolder
                        case={nestedCase}
                        step={step + 1}
                        parentCaseNames={[...parentCaseNames, leaf.name].filter((_name): _name is string => !!_name)}
                        onItemUpdated={onItemUpdated}
                        collapseKey={collapseKey}
                      />
                    )}
                  </Stack>
                </CaseFolderContextMenu>
              );
            })}

          {/* Folders listed after child cases */}
          {Object.entries(tree.folders ?? {}).map(([folderName, subfolder]) => {
            return (
              <CaseFolder
                key={subfolder.item?.id ?? folderName}
                name={folderName}
                case={_case}
                folder={subfolder}
                step={step + 1}
                parentCaseNames={parentCaseNames}
                onItemUpdated={onItemUpdated}
                collapseKey={collapseKey}
              />
            );
          })}

          {/* Non-case leaves listed last */}
          {tree.leaves
            ?.filter(leaf => leaf.type?.toLowerCase() !== 'case')
            .map(leaf => {
              const itemType = leaf.type?.toLowerCase();
              const fullItemPath = [...parentCaseNames, buildPathFromID(_case, leaf.id!)].filter(Boolean).join('/');
              const itemTo =
                itemType !== 'reference'
                  ? `/cases/${rootCaseId}${fullItemPath ? `/${fullItemPath}` : ''}`
                  : (leaf.value ?? '');

              const escalationColor = getEscalationColor(itemType!, leaf);
              const iconColor = escalationColor ?? ('inherit' as const);
              const leafColor = escalationColor ? `${escalationColor}.light` : 'text.secondary';

              return (
                <CaseFolderContextMenu
                  key={`${_case?.case_id}-${leaf.id}-${leaf.value}`}
                  case={_case}
                  item={leaf}
                  onUpdate={onItemUpdated}
                >
                  <Box
                    sx={{
                      transition: theme.transitions.create('background', { duration: 100 }),
                      background: 'transparent',
                      '&:hover': { background: theme.palette.grey[800] }
                    }}
                  >
                    <FolderEntry
                      caseId={_case.case_id === rootCaseId ? rootCaseId : null}
                      indent={step * 1.5 + 1}
                      label={leaf.name ?? leaf.value ?? ''}
                      iconColor={iconColor}
                      labelColor={leafColor}
                      to={itemTo}
                      entry={leaf}
                    />
                  </Box>
                </CaseFolderContextMenu>
              );
            })}
        </>
      )}
    </Stack>
  );
};

export default CaseFolder;
