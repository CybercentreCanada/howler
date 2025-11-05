# Frontend Development

??? warning "System dependencies"
    Before running these steps, ensure you have
    [completed the installation steps here](/howler-docs/developer/getting_started/#frontend-dependencies).

## Running the Development Server

Running the Howler UI for development is straightforward:

```shell
# Navigate to the UI directory
cd ui

# Install dependencies
pnpm install

# Run the development server
pnpm dev
```

The development server will start on `http://localhost:5173` by default (Vite's default port).

## Available Scripts

The UI provides several npm scripts for development:

- `pnpm dev` or `pnpm start` - Start the Vite development server
- `pnpm build` - Build the application for production (runs TypeScript compiler and Vite build)
- `pnpm serve` - Preview the production build locally
- `pnpm lint` - Format code using Prettier
- `pnpm test` - Run tests with coverage using Vitest
- `pnpm test-ui` - Run tests with UI and coverage

## Key Dependencies

The Howler UI is built with modern web technologies:

### Core Framework

- **React 18** - The UI framework powering the application
- **React Router v6** - Client-side routing
- **TypeScript** - Type safety and improved developer experience
- **Vite** - Fast build tool and development server

### UI Components & Styling

- **Material-UI (MUI) v5** - Primary component library providing the design system

### State Management & Data

- **axios** - HTTP client for API requests
- **use-context-selector** - Optimized React context for state management
- **react-pluggable** - Plugin system for extensibility

### Code & Content Editing

- **Monaco Editor** - VS Code's editor component (via @monaco-editor/react)
- **react-markdown** - Markdown rendering with GitHub-flavored markdown support

### Utilities

- **dayjs** - Lightweight date/time library
- **lodash-es** - Modern utility library (ES modules)
- **i18next** - Internationalization framework

### Development Tools

- **Vitest** - Fast unit testing framework (Vite-native)
- **ESLint** - Code linting with TypeScript, React, and Prettier integration
- **Prettier** - Code formatting
- **lint-staged** - Run linters on staged files

## Visual Studio Code

If developing in VS Code, it is recommended to install the workspace's recommended extensions for built-in Prettier and
ESLint support. These can be found in the `.vscode/extensions.json` file.
