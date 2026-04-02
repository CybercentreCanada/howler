import { Box, Skeleton, Stack, useTheme } from '@mui/material';
import api from 'api';
import { RecordContext } from 'components/app/providers/RecordProvider';
import useMyApi from 'components/hooks/useMyApi';
import type { Case } from 'models/entities/generated/Case';
import type { Item } from 'models/entities/generated/Item';
import { useCallback, useMemo, useState, type FC } from 'react';
import { useContextSelector } from 'use-context-selector';
import { ESCALATION_COLORS } from 'utils/constants';
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
  rootCaseId?: string;
  pathPrefix?: string;
  onItemUpdated?: (newCase: Case) => void;
}

const CaseFolder: FC<CaseFolderProps> = ({
  case: _case,
  folder,
  name,
  step = -1,
  rootCaseId,
  pathPrefix = '',
  onItemUpdated
}) => {
  const theme = useTheme();
  const { dispatchApi } = useMyApi();

  const [open, setOpen] = useState(true);
  const [caseStates, setCaseStates] = useState<Record<string, CaseNodeState>>({});

  const records = useContextSelector(RecordContext, ctx => ctx.records);

  const tree = useMemo(() => folder || buildTree(_case?.items), [folder, _case?.items]);
  const currentRootCaseId = rootCaseId || _case?.case_id;

  // Returns the MUI colour token for the item's escalation, or undefined if none.
  const getEscalationColor = (itemType: string | undefined, itemKey: string | undefined, leafId: string) => {
    if (itemType === 'hit' && leafId) {
      const color = ESCALATION_COLORS[records[leafId]?.howler?.escalation as keyof typeof ESCALATION_COLORS];
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
      const resolvedKey = itemKey || item.path || item.value;
      if (!resolvedKey) {
        return;
      }

      const prev = caseStates[resolvedKey] ?? { open: false, loading: false, data: null };
      const shouldOpen = !prev.open;
      const shouldFetch = shouldOpen && !!item.value && !prev.data && !prev.loading;

      setCaseStates(current => ({ ...current, [resolvedKey]: { ...prev, open: shouldOpen, loading: shouldFetch } }));

      if (!shouldFetch) return;

      dispatchApi(api.v2.case.get(item.value!), { throwError: false })
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
        <CaseFolderContextMenu _case={_case} tree={tree} onUpdate={onItemUpdated}>
          <Box
            sx={{
              transition: theme.transitions.create('background', { duration: 100 }),
              background: 'transparent',
              '&:hover': { background: theme.palette.grey[800] }
            }}
          >
            <FolderEntry
              caseId={_case.case_id === rootCaseId ? rootCaseId : null}
              path={tree.path}
              itemType="folder"
              indent={step * 1.5}
              label={name}
              chevronOpen={open}
              onClick={() => setOpen(_open => !_open)}
            />
          </Box>
        </CaseFolderContextMenu>
      )}

      {open && (
        <>
          {Object.entries(tree.folders ?? {}).map(([path, subfolder]) => {
            return (
              <CaseFolder
                key={`${_case?.case_id}-${path}`}
                name={path}
                case={_case}
                folder={subfolder}
                step={step + 1}
                rootCaseId={currentRootCaseId}
                pathPrefix={`${pathPrefix ?? ''}${pathPrefix ? '/' : ''}${name ?? ''}`}
                onItemUpdated={onItemUpdated}
              />
            );
          })}

          {tree.leaves?.map(leaf => {
            const itemType = leaf.type?.toLowerCase();
            const isCase = itemType === 'case';
            const fullRelativePath = [pathPrefix, leaf.path].filter(Boolean).join('/');
            const itemKey = fullRelativePath || leaf.value;
            const nodeState = itemKey ? caseStates[itemKey] : null;
            const isCaseOpen = !!nodeState?.open;
            const isCaseLoading = !!nodeState?.loading;
            const nestedCase = nodeState?.data ?? null;
            const itemTo =
              itemType !== 'reference'
                ? fullRelativePath
                  ? `/cases/${currentRootCaseId}/${fullRelativePath}`
                  : `/cases/${currentRootCaseId}`
                : leaf.value;

            const escalationColor = getEscalationColor(itemType, itemKey, leaf.value);
            const iconColor = escalationColor ?? ('inherit' as const);
            const leafColor = escalationColor ? `${escalationColor}.light` : 'text.secondary';

            return (
              <CaseFolderContextMenu
                key={`${_case?.case_id}-${leaf.value}-${leaf.path}`}
                _case={_case}
                leaf={leaf}
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
                      path={leaf.path}
                      indent={step * 1.5 + 1}
                      label={leaf.path?.split('/').pop() || leaf.value || ''}
                      itemType={itemType}
                      iconColor={iconColor}
                      labelColor={leafColor}
                      chevronOpen={isCaseOpen}
                      to={itemTo}
                      onClick={() => isCase && toggleCase(leaf, itemKey)}
                      item={leaf}
                    />
                  </Box>

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
                      onItemUpdated={onItemUpdated}
                    />
                  )}
                </Stack>
              </CaseFolderContextMenu>
            );
          })}
        </>
      )}
    </Stack>
  );
};

export default CaseFolder;
