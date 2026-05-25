# External scripts

## reindex_data.py

Reindex one or more Elasticsearch indexes used by Howler.

### Usage

```bash
# Reindex specific indexes (confirms each one before proceeding)
python reindex_data.py hit user

# Reindex all indexes
python reindex_data.py --all

# Skip confirmation prompts and countdown
python reindex_data.py hit --force

# Print index schema before reindexing
python reindex_data.py hit --verbose
```

### Options

| Argument    | Description                                  |
|-------------|----------------------------------------------|
| `indexes`   | One or more index names to reindex.          |
| `--all`     | Reindex all indexes.                         |
| `--force`   | Skip confirmation prompts and countdown.     |
| `--verbose` | Print the index schema before reindexing.    |
