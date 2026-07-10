# tsx_user_tags

Allow analysts to manage personal tags (portfolio, products, disciplines)

---

**Author**: ts-veerreddys

[UI Plugin Docs](https://github.com/CybercentreCanada/howler/blob/develop/docs/ui/plugins.md)

---

## Install Plugin

### Configure Howler to load your plugin

`/workspaces/howler/ui/src/index.tsx`

```yaml
import TSXUserTags from './plugins/tsx_user_tags';

if(TSXUserTags.shouldLoad()){ howlerPluginStore.install(new TSXUserTags()); }
```

This plugin depends on the UI Plugin in `/workspaces/howler/plugins/tsx_user_tags`

During ui plugin activation a check is made to the following two endpoints, if either endpoint returns False then the UI Plugin will not load.

| Route              | Description                                                                                |
| ------------------ | ------------------------------------------------------------------------------------------ |
| /api/v1/tags/ready | Route that returns 200 OK if all services the API Plugin needs are online/ready/configured |
| /api/v1/tags/live  | Route that returns a simple 200 OK if plugin is loaded                                     |
