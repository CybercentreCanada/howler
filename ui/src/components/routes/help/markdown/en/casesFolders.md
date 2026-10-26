# Folder structure

Folders keep related case items together. Use the add-folder control in the sidebar to create one, then drag items into it. Dragging an item to the bottom root drop zone returns it to the case root.

## Organize the investigation

Folders can be nested to reflect an investigation's workstreams. Expand or collapse them from the chevron, and use their context menu to manage the folder and its contents. A folder can contain folders, evidence, notes, and references; only folders are valid item parents.

`folder_tree`

## Move, rename, and remove

Drag an item onto a folder to move it, or use the root drop zone to remove its parent. Item names must be unique among siblings, so rename an item before moving it if its destination already has the same name.

Right-click a folder or item to rename it or remove it. **Removal is immediate, with no confirmation dialog.** Before selecting **Remove folder**, review its entire tree: the folder, nested folders, notes, references, and evidence items inside it are removed from the case. Underlying hit and event records are not deleted, but their associations with this case are removed. Notes and references stored in the removed items are deleted.

Linked cases always remain at the case root and cannot be placed inside a folder.
