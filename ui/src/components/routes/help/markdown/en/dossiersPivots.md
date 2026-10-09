# Add pivots

A pivot is an action shown with a matching hit. It can open a related resource, such as a SIEM, ticketing system, or investigation dashboard, using values from that hit.

`dossier_pivot`

## Link pivots

The built-in **link** format uses the pivot value as a Handlebars template. Add mappings to expose hit fields or custom values under template keys, then reference them in the value. For example, map `host.name` to the key `hostname` and use `https://investigate.example/?host={{hostname}}` as the value.

Each mapping key must be unique. A mapping also needs a selected hit field, or a custom value when its field is `custom`. When a mapped hit field is an array, Howler uses its first value. Review generated links with a representative hit before sharing the dossier.

## Organize pivot groups

Use the optional **Pivot Group** field to place a pivot in a nested menu. For example, `SIEM/Hosts` groups it under that slash-separated path. Leave the field empty to keep the pivot at the menu root. Matching dossiers that use the same group path contribute pivots to the same menu group.

Group segments can contain English letters, supported French accented letters, and digits, but not spaces or other punctuation. Use `/` between non-empty segments; leading or trailing slashes and repeated slashes such as `SIEM//Hosts` are invalid. The editor suggests existing group paths as you type so you can reuse them.

## Plugin pivot formats

Plugins can supply additional pivot formats and their configuration forms. Those pivots are rendered by the installed plugin rather than as an ordinary link. If the required implementation is absent, Howler displays an error indicator instead of silently opening an incorrect destination.

Like leads, pivots require English and French labels, a valid Iconify icon, and a configured format. A pivot value is always required; link pivots may have no mappings only when the destination needs no hit-specific value.
