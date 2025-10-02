# Howler UI Plugins

Howler UI plugins provide a powerful way to extend the functionality of the Howler interface using the `react-pluggable` framework. Plugins can inject custom components, add new operations, handle events, and provide integrations with external systems.

## Overview

Howler UI plugins are built on the `react-pluggable` framework and provide a robust architecture for extending the Howler interface. The plugin system offers multiple extension points and capabilities:

### Core Capabilities

**Component Injection**: Plugins can inject custom React components into various parts of the UI, including status displays, action buttons, help sections, and administrative interfaces.

**Custom Operations**: Add new operations that users can perform on hits via the action interface, with full form interfaces and documentation integration through the `addOperation` method.

**Lead and Pivot Management**: Extend Howler's data relationship capabilities by adding custom lead formats with `addLead` and pivot formats with `addPivot`.

**Event-Driven Architecture**: React to user interactions through a comprehensive event system that triggers on actions like viewing hits, selecting items, or refreshing data.

**Localization Support**: Full internationalization support with the ability to add translation resources for multiple languages.

## Plugin Architecture

All Howler UI plugins extend the abstract `HowlerPlugin` class, which provides a standardized interface for plugin development. The base class handles plugin lifecycle management, function registration, and provides hooks for various UI extension points.

## Installing Plugins

Plugins are installed in the main application entry point (`src/index.tsx`) using the plugin store:

```tsx
import howlerPluginStore from '@cccsaurora/howler-ui/plugins/store';
import MyCustomPlugin from 'plugins/my-custom-plugin';

// Install the plugin
howlerPluginStore.install(new MyCustomPlugin());
```

## HowlerPlugin Class Methods

### Required Properties

Every plugin must define these abstract properties:

- **`name`**: Unique identifier for the plugin
- **`version`**: Plugin version (semantic versioning recommended)
- **`author`**: Plugin author information
- **`description`**: Brief description of plugin functionality

### Lifecycle Methods

#### `activate(): void`

Called when the plugin is activated. This is where you should register your custom operations, leads, pivots, and other plugin functionality.

```tsx
activate(): void {
  super.activate();

  // Add custom operations
  super.addOperation('my-operation', MyOperationComponent, {
    id: 'my-operation',
    i18nKey: 'help.actions.my-operation',
    component: () => <MyOperationDocumentation />
  });
}
```

#### `deactivate(): void`

Called when the plugin is deactivated. The base class handles cleanup automatically.

### Extension Methods

#### `addLead(format, form, renderer)`

Adds a custom lead format to the system.

- **`format`**: String identifier for the lead type
- **`form`**: React component for the lead creation form
- **`renderer`**: React component for rendering the lead content

#### `addPivot(format, form, renderer)`

Adds a custom pivot format to the system.

- **`format`**: String identifier for the pivot type
- **`form`**: React component for the pivot creation form
- **`renderer`**: React component for rendering pivot links

#### `addOperation(format, form, documentation)`

Adds a custom operation to the system.

- **`format`**: String identifier for the operation
- **`form`**: React component for the operation form
- **`documentation`**: Documentation object with component and metadata

### UI Hook Methods

#### `actions(hits: Hit[]): ActionButton[]`

Returns an array of action buttons to display for the selected hits.

```tsx
actions(hits: Hit[]): ActionButton[] {
  return [{
    type: 'action',
    name: 'My Custom Action',
    actionFunction: () => this.performCustomAction(hits)
  }];
}
```

#### `status(props: StatusProps): React.ReactNode`

Returns a React component to display in the hit status area.

#### `support(): React.ReactNode`

Returns a React component for plugin-specific support information.

#### `help(): React.ReactNode`

Returns a React component for plugin help content.

#### `settings(section: string): React.ReactNode`

Returns settings components for different sections ('profile', 'local', 'admin', 'security').

### Event Handling

#### `on(event: string, hit?: Hit): void`

Handles UI events. Currently supports:

- `'viewing'`: When a hit is being viewed

### Provider and Setup

#### `provider(): React.FC<PropsWithChildren<{}>> | null`

Returns a React context provider to wrap the application (optional).

#### `setup(): void`

Called during plugin initialization for any setup tasks.

### Localization and Helpers

#### `localization(i18n: I18N): void`

Adds localization resources to the i18n instance.

```tsx
localization(i18n: i18n): void {
  i18n.addResourceBundle('en', 'translation', enTranslations, true, false);
  i18n.addResourceBundle('fr', 'translation', frTranslations, true, false);
}
```

#### `helpers(): HowlerHelper[]`

Returns an array of Handlebars helpers for template rendering.

### UI Components

#### `typography(props: PluginTypographyProps): React.ReactNode`

Returns custom typography components. This is useful for wrapping content in various portions of the UI with custom
styling, or augmented functionality (e.g., enrichment)

## Example Plugin Implementation

Here's a complete example of a Howler UI plugin that demonstrates various features:

```tsx
import type { ActionButton } from '@cccsaurora/howler-ui/components/elements/hit/actions/SharedComponents';
import type { StatusProps } from '@cccsaurora/howler-ui/components/elements/hit/HitBanner';
import type { Hit } from '@cccsaurora/howler-ui/models/entities/generated/Hit';
import HowlerPlugin from '@cccsaurora/howler-ui/plugins/HowlerPlugin';
import type { i18n } from 'i18next';
import ExampleOperation from './components/ExampleOperation';
import ExampleHelp from './components/ExampleHelp';
import ExampleStatus from './components/ExampleStatus';
import ExampleSupport from './components/ExampleSupport';
import ExampleAdmin from './components/ExampleAdmin';
import en from './locales/example.en.json';
import fr from './locales/example.fr.json';

class ExamplePlugin extends HowlerPlugin {
  name = 'ExamplePlugin';
  version = '1.0.0';
  author = 'Your Name <your.email@example.com>';
  description = 'An example plugin demonstrating Howler UI plugin capabilities.';

  activate(): void {
    super.activate();

    // Add a custom operation
    super.addOperation('example-operation', props => <ExampleOperation {...props} />, {
      id: 'example-operation',
      i18nKey: 'help.actions.example',
      component: () => <div>Example operation documentation</div>
    });
  }

  localization(i18n: i18n): void {
    i18n.addResourceBundle('en', 'translation', en, true, false);
    i18n.addResourceBundle('fr', 'translation', fr, true, false);
  }

  actions(hits: Hit[]): ActionButton[] {
    const actions: ActionButton[] = [];

    // Add action for single hit
    if (hits.length === 1) {
      actions.push({
        type: 'action',
        name: 'Example Single Action',
        actionFunction: () => this.handleSingleAction(hits[0])
      });
    }

    // Add action for multiple hits
    if (hits.length > 1) {
      actions.push({
        type: 'action',
        name: 'Example Bulk Action',
        actionFunction: () => this.handleBulkAction(hits)
      });
    }

    return actions;
  }

  status(props: StatusProps): React.ReactNode {
    // Only show status for hits with specific properties
    if (!props.hit.someCustomProperty) {
      return null;
    }

    return <ExampleStatus {...props} key="example" />;
  }

  support(): React.ReactNode {
    return <ExampleSupport key="example" />;
  }

  help(): React.ReactNode {
    return <ExampleHelp key="example" />;
  }

  on(event: string): void {
    if (event === 'viewing') {
      // Handle viewing event
      console.log('User is viewing a hit');
    } else if (event === 'selecting') {
      // Handle selection event
      console.log('User selected hits');
    }
  }

  settings(section: 'profile' | 'local' | 'admin' | 'security'): React.ReactNode {
    if (section === 'admin') {
      return <ExampleAdmin />;
    }
    return null;
  }

  // Private helper methods
  private handleSingleAction(hit: Hit): void {
    // Implement single hit action logic
    console.log('Performing action on single hit:', hit.howler.id);
  }

  private handleBulkAction(hits: Hit[]): void {
    // Implement bulk action logic
    console.log('Performing bulk action on hits:', hits.map(h => h.howler.id));
  }
}

export default ExamplePlugin;
```

## Component Examples

### Example Operation Component

```tsx
// components/ExampleOperation.tsx
import React from 'react';
import type { CustomActionProps } from '@cccsaurora/howler-ui/components/routes/action/edit/ActionEditor';

const ExampleOperation: React.FC<CustomActionProps> = ({ hits, onComplete }) => {
  return (
    <Card variant="outlined" key={operation.id} sx={[!readonly && ready && { borderColor: 'success.main' }]}>
      <CardContent>
        <Stack spacing={2}>
          <ExampleStep />

          {loading  && <LinearProgress variant="indeterminate" />}

          <OtherStep />
        </Stack>
      </CardContent>
    </Card>
  );
};

export default ExampleOperation;
```

### Example Status Component

```tsx
// components/ExampleStatus.tsx
import React from 'react';
import type { StatusProps } from '@cccsaurora/howler-ui/components/elements/hit/HitBanner';

const ExampleStatus: React.FC<StatusProps> = ({ hit }) => {
  return (
    <div style={{
      backgroundColor: '#e3f2fd',
      padding: '4px 8px',
      borderRadius: '4px',
      fontSize: '12px'
    }}>
      Custom Status: {hit.someCustomProperty}
    </div>
  );
};

export default ExampleStatus;
```

## Best Practices

### Plugin Development Guidelines

1. **Naming Convention**: Use descriptive, unique names for your plugins to avoid conflicts.

2. **Version Management**: Follow semantic versioning for your plugins.

3. **Resource Management**: Always clean up resources in the `deactivate()` method.

4. **Error Handling**: Implement proper error handling in all plugin methods.

5. **Performance**: Be mindful of performance impact, especially in frequently called methods like `status()` and `actions()`.

6. **Localization**: Always provide localization support for user-facing text.

### Event Handling Best Practices

- Use the `on()` method sparingly and only for essential event handling
- Avoid heavy operations in event handlers
- Consider debouncing frequent events like 'selecting'

### UI Integration Guidelines

- Keep UI components lightweight and focused
- Use consistent styling with the main application
- Provide clear user feedback for long-running operations
- Follow accessibility guidelines

### Testing Plugins

1. **Unit Testing**: Test individual plugin methods
2. **Integration Testing**: Test plugin integration with the main application
3. **User Testing**: Validate user experience with real workflows

## Troubleshooting

### Common Issues

1. **Plugin Not Loading**: Check that the plugin is properly installed in the plugin store
2. **Actions Not Appearing**: Verify that the `actions()` method returns valid ActionButton objects
3. **Localization Not Working**: Ensure localization resources are properly loaded in the `localization()` method
4. **Events Not Firing**: Check that event names match the expected values

## Creating Plugin Components

When developing a plugin, you'll need to create various React components. Here are some stub examples:

### Component Directory Structure

```text
plugins/
  your-plugin/
    index.tsx                   # Main plugin class
    components/
      YourOperation.tsx         # Custom operation component
      YourStatus.tsx            # Status display component
      YourHelp.tsx              # Help content component
      YourSupport.tsx           # Support information component
      YourAdmin.tsx             # Admin settings component
    locales/
      your-plugin.en.json       # English translations
      your-plugin.fr.json       # French translations
    types.d.ts                  # Type definitions
```

### Component Stubs

```tsx
// components/YourOperation.tsx
import React from 'react';
import type { CustomActionProps } from '@cccsaurora/howler-ui/components/routes/action/edit/ActionEditor';

const YourOperation: React.FC<CustomActionProps> = ({ hits, onComplete }) => {
  return (
    <div>
      <h3>Your Custom Operation</h3>
      {/* TODO: Add operation form */}
    </div>
  );
};

export default YourOperation;
```

```tsx
// components/YourStatus.tsx
import React from 'react';
import type { StatusProps } from '@cccsaurora/howler-ui/components/elements/hit/HitBanner';

const YourStatus: React.FC<StatusProps> = ({ hit }) => {
  return (
    <div>
      {/* TODO: Implement status display logic */}
      Status: Active
    </div>
  );
};

export default YourStatus;
```

### Localization Files

```json
// locales/your-plugin.en.json
{
  "help.actions.your-operation": "Your Custom Operation",
  "actions.your-action": "Your Action",
  "actions.bulk-action": "Bulk Action",
  "status.active": "Active",
  "status.inactive": "Inactive"
}
```

## Advanced Features

### Custom Hooks

You can create custom hooks for complex logic:

```tsx
// hooks/useYourPlugin.ts
import { useState, useCallback } from 'react';
import type { Hit } from '@cccsaurora/howler-ui/models/entities/generated/Hit';

export const useYourPlugin = (hits: Hit | Hit[]) => {
  const [loading, setLoading] = useState(false);

  const performAction = useCallback(async () => {
    setLoading(true);
    try {
      // TODO: Implement action logic
      console.log('Performing action on hits:', hits);
    } finally {
      setLoading(false);
    }
  }, [hits]);

  return {
    loading,
    performAction
  };
};
```

### Type Definitions

Define custom types for your plugin:

```tsx
// types/index.ts
import type { Hit } from '@cccsaurora/howler-ui/models/entities/generated/Hit';

export interface ExtendedHit extends Hit {
  yourCustomProperty?: string;
  yourPluginData?: {
    status: 'active' | 'inactive';
    metadata: Record<string, any>;
  };
}

export interface YourPluginConfig {
  apiUrl: string;
  timeout: number;
  enableFeatureX: boolean;
}
```

## Troubleshooting

### Common Issues

1. **Plugin Not Loading**: Check that the plugin is properly installed in the plugin store
2. **Actions Not Appearing**: Verify that the `actions()` method returns valid ActionButton objects
3. **Localization Not Working**: Ensure localization resources are properly loaded in the `localization()` method
4. **Events Not Firing**: Check that event names match the expected values

### Debugging Tips

- Use browser developer tools to inspect plugin registration
- Add console logging to plugin methods during development
- Verify plugin dependencies and imports
- Check for JavaScript errors in the browser console

## Plugin Installation

To install your plugin, add it to the main application entry point:

```tsx
// src/index.tsx
import howlerPluginStore from '@cccsaurora/howler-ui/plugins/store';
import YourPlugin from 'plugins/your-plugin';

// Install your plugin
howlerPluginStore.install(new YourPlugin());
```

Remember to import any required styles or assets your plugin needs.
