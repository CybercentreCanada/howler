import { Delete, DriveFileRenameOutline, OpenInNew } from '@mui/icons-material';
import api from 'api';
import { ModalContext } from 'components/app/providers/ModalProvider';
import ContextMenu, { type ContextMenuEntry } from 'components/elements/ContextMenu';
import useMyApi from 'components/hooks/useMyApi';
import RenameItemModal from 'components/routes/cases/modals/RenameItemModal';
import type { Case } from 'models/entities/generated/Case';
import type { Item } from 'models/entities/generated/Item';
import { useContext, useMemo, type FC, type PropsWithChildren } from 'react';
import { useTranslation } from 'react-i18next';
import type { Tree } from './types';

/**
 * Recursively collects all leaf items from a folder tree.
 */
export const collectAllLeaves = (tree: Tree): Item[] => {
  const result: Item[] = [...(tree.leaves ?? [])];
  for (const subfolder of Object.values(tree.folders ?? {})) {
    result.push(...collectAllLeaves(subfolder));
  }
  return result;
};

/**
 * Returns the URL to open for a given leaf item, or null if no URL applies.
 * - reference: the item's value (an external URL)
 * - hit: /hits/<id>
 * - event: /events/<id>
 * - case: /cases/<id>
 * - table / lead: null (no dedicated detail page)
 */
export const getOpenUrl = (leaf: Item): string | null => {
  const type = leaf.type?.toLowerCase();
  if (type === 'reference') {
    return leaf.value ?? null;
  }
  if (type === 'hit') {
    return leaf.value ? `/hits/${leaf.value}` : null;
  }
  if (type === 'event') {
    return leaf.value ? `/events/${leaf.value}` : null;
  }
  if (type === 'case') {
    return leaf.value ? `/cases/${leaf.value}` : null;
  }
  if (type === 'markdown') {
    return null;
  }
  return null;
};

export interface CaseFolderContextMenuProps extends PropsWithChildren {
  /** The case that owns the item(s). */
  case: Case;
  /** Present when the context menu is for a single leaf item. */
  item?: Item;
  /** Called after item(s) have been updated (renamed, removed). */
  onUpdate?: (updatedCase: Case) => void;
}

/**
 * Wraps its children with a right-click context menu providing:
 * - **Open item** – opens the item in a new tab (only for leaf items with a navigable URL).
 * - **Remove item / Remove folder** – deletes the leaf item or all items under a folder.
 */
const CaseFolderContextMenu: FC<CaseFolderContextMenuProps> = ({ case: _case, item, onUpdate, children }) => {
  const { dispatchApi } = useMyApi();
  const { t } = useTranslation();
  const { showModal } = useContext(ModalContext);

  const items = useMemo<ContextMenuEntry[]>(() => {
    const entries: ContextMenuEntry[] = [];

    if (item) {
      const openUrl = getOpenUrl(item);
      if (openUrl) {
        entries.push({
          kind: 'item',
          id: 'open-item',
          label: t('page.cases.sidebar.item.open'),
          icon: <OpenInNew fontSize="small" />,
          onClick: () => window.open(openUrl, '_blank', 'noopener noreferrer')
        });
      }
    }

    if (entries.length > 0) {
      entries.push({ kind: 'divider', id: 'divider-remove' });
    }

    const isFolder = item.type === 'folder';
    entries.push({
      kind: 'item',
      id: 'rename-item',
      label: isFolder ? t('page.cases.sidebar.folder.rename') : t('page.cases.sidebar.item.rename'),
      icon: <DriveFileRenameOutline fontSize="small" />,
      onClick: () => showModal(<RenameItemModal _case={_case} item={item} onRenamed={onUpdate} />, { height: null })
    });

    entries.push({
      kind: 'item',
      id: 'remove-item',
      label: isFolder ? t('page.cases.sidebar.folder.remove') : t('page.cases.sidebar.item.remove'),
      icon: <Delete fontSize="small" />,
      onClick: () => {
        if (!_case.case_id) {
          return;
        }

        dispatchApi(api.v2.case.items.del(_case.case_id!, [item.id], isFolder), { throwError: false }).then(
          updatedCase => {
            if (updatedCase) {
              onUpdate?.(updatedCase);
            }
          }
        );
      }
    });

    return entries;
  }, [_case, item, dispatchApi, onUpdate, showModal, t]);

  return <ContextMenu items={items}>{children}</ContextMenu>;
};

export default CaseFolderContextMenu;
