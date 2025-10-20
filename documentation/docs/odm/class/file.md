??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

# File

> A file is defined as a set of information that has been created on, or has existed on a filesystem.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| accessed | Date | Last time the file was accessed. | :material-minus-box-outline: Optional | `None` |
| attributes | List [Keyword] | Array of file attributes. | :material-minus-box-outline: Optional | `None` |
| created | Date | File creation time. | :material-minus-box-outline: Optional | `None` |
| ctime | Date | Last time the file attributes or metadata changed. | :material-minus-box-outline: Optional | `None` |
| device | Keyword | Device that is the source of the file. | :material-minus-box-outline: Optional | `None` |
| directory | Keyword | Directory where the file is located. It should include the drive letter, when appropriate. | :material-minus-box-outline: Optional | `None` |
| drive_letter | Keyword | Drive letter where the file is located. This field is only relevant on Windows. | :material-minus-box-outline: Optional | `None` |
| extension | Keyword | File extension, excluding the leading dot. | :material-minus-box-outline: Optional | `None` |
| fork_name | Keyword | A fork is additional data associated with a filesystem object. | :material-minus-box-outline: Optional | `None` |
| gid | Keyword | Primary group ID (GID) of the file. | :material-minus-box-outline: Optional | `None` |
| group | Keyword | Primary group name of the file. | :material-minus-box-outline: Optional | `None` |
| inode | Keyword | Inode representing the file in the filesystem. | :material-minus-box-outline: Optional | `None` |
| mime_type | Keyword | MIME type should identify the format of the file or stream of bytes using IANA official types, where possible. | :material-minus-box-outline: Optional | `None` |
| mode | Keyword | Mode of the file in octal representation. | :material-minus-box-outline: Optional | `None` |
| mtime | Date | Last time the file content was modified. | :material-minus-box-outline: Optional | `None` |
| name | Keyword | Name of the file including the extension, without the directory. | :material-minus-box-outline: Optional | `None` |
| owner | Keyword | File owner’s username. | :material-minus-box-outline: Optional | `None` |
| path | Keyword | Full path to the file, including the file name. It should include the drive letter, when appropriate. | :material-minus-box-outline: Optional | `None` |
| size | Integer | File size in bytes. | :material-minus-box-outline: Optional | `None` |
| target_path | Keyword | Target path for symlinks. | :material-minus-box-outline: Optional | `None` |
| type | Enum | File type (file, dir, or symlink).<br>Values:<br>`"dir", "file", "symlink"` | :material-minus-box-outline: Optional | `None` |
| uid | Keyword | The user ID (UID) or security identifier (SID) of the file owner. | :material-minus-box-outline: Optional | `None` |
| code_signature | [CodeSignature](/howler-docs/odm/class/codesignature) | These fields contain information about binary code signatures. | :material-minus-box-outline: Optional | `None` |
| elf | [ELF](/howler-docs/odm/class/elf) | These fields contain Linux Executable Linkable Format (ELF) metadata. | :material-minus-box-outline: Optional | `None` |
| hash | [Hashes](/howler-docs/odm/class/hashes) | These fields contain Windows Portable Executable (PE) metadata. | :material-minus-box-outline: Optional | `None` |
| pe | [PE](/howler-docs/odm/class/pe) | Hashes, usually file hashes. | :material-minus-box-outline: Optional | `None` |
