---
status: accepted
---

# Register UI plugins at build entry via react-pluggable

UI extensions implement `HowlerPlugin` on top of `react-pluggable` and are installed statically in `ui/src/index.tsx` rather than loaded dynamically as external runtime bundles. Bundling plugins at build time preserves TypeScript type checking against generated entity models, integrates plugin translation bundles into `i18next`, and keeps frontend deployment to a single static asset bundle.

## Consequences

- Adding, removing, or upgrading UI plugins requires rebuilding and redeploying the UI package (or toggling compile-time feature flags such as `VITE_ENABLE_CLUE`).
