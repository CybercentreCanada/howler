declare module '*.md';

declare module 'md5' {
  const md5: (message: string | number[] | ArrayBuffer) => string;
  export default md5;
}

declare module 'handlebars-async-helpers' {
  const asyncHelpers: <T>(handlebars: T) => T;
  export default asyncHelpers;
}

declare module 'react-syntax-highlighter/dist/esm/prism-async-light' {
  import type { CSSProperties, ComponentType } from 'react';

  interface SyntaxHighlighterProps {
    children: string;
    style?: CSSProperties | Record<string, unknown>;
    language?: string;
    PreTag?: string;
    [prop: string]: unknown;
  }

  const SyntaxHighlighter: ComponentType<SyntaxHighlighterProps>;
  export default SyntaxHighlighter;
}

declare module 'react-syntax-highlighter/dist/esm/styles/prism' {
  const oneDark: Record<string, unknown>;
  const oneLight: Record<string, unknown>;
  export { oneDark, oneLight };
}
