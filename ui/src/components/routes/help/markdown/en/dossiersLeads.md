# Add leads

A lead is a tab of information displayed in the hit viewer when the dossier matches. Open the **Leads** tab and use the add button to create one. The order of the lead tabs follows the order in the dossier editor.

`dossier_lead`

## Required lead details

Every lead needs English and French labels, a valid Iconify icon ID, a format, and content. The localized labels are what users see in their selected interface language. Use the Iconify browser linked from the editor to choose an icon that exists.

The built-in **markdown** format renders the content in the hit viewer. It is appropriate for concise investigation steps and context. Markdown leads are Handlebars templates rendered with the current hit as their context, so `{{howler.id}}` resolves to the hit ID and supported Howler helpers are available. Validate dynamic content against a real matching hit before publishing it.

External links in Markdown leads are rendered as plain text, except for internal (`/...`) and `*.gc.ca` links. Use a link pivot for a clickable external destination.

## Plugin lead formats

Installed plugins can register additional lead formats. Selecting one displays its plugin-specific editor and can store format-specific metadata. The format must be available in the current Howler deployment for the lead to render; otherwise, the hit viewer reports an invalid lead.

Changing a lead's format clears its current content and metadata. Finish configuring the new format before saving, and remove unused leads with the delete control.
