/* eslint-disable prefer-arrow/prefer-arrow-functions */
import {
  Alert,
  Box,
  darken,
  lighten,
  Paper,
  Table,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  useTheme
} from '@mui/material';
import { useAppTheme } from 'commons/components/app/hooks';
import mermaid from 'mermaid';
import { memo, useEffect, type FC, type ReactElement } from 'react';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';
import { Link } from 'react-router-dom';
import SyntaxHighlighter from 'react-syntax-highlighter/dist/esm/prism-async-light';
import { oneDark, oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';
import rehypeRaw from 'rehype-raw';
import remarkGfm from 'remark-gfm';
import DynamicTabs from './DynamicTabs';
import Image from './Image';
import { Notebook } from './Notebook';
import JSONViewer from './json/JSONViewer';
import { codeTabs } from './markdownPlugins/tabs';

export interface MarkdownProps {
  md: string;
  components?: { [index: string]: ReactElement };
  disableLinks?: boolean;
}

const customComponents = (type: string, children: any) => {
  const child = children instanceof Array ? children[0] : children;
  if (type === 'alert') {
    return (
      <Alert severity="info" variant="outlined" sx={{ '.MuiAlert-message': { whiteSpace: 'normal' } }}>
        {child}
      </Alert>
    );
  } else if (type === 'notebook') {
    return <Notebook ipynb={child} />;
  } else if (type === 'tabs') {
    return (
      <DynamicTabs
        tabs={JSON.parse(child).map(t => ({ title: t.title, children: customComponents(t.lang, t.value) }))}
      />
    );
  } else {
    return <code>{child}</code>;
  }
};

const Markdown: FC<MarkdownProps> = ({ md, components = {}, disableLinks = false }) => {
  const theme = useTheme();
  const { isDark } = useAppTheme();
  const { t } = useTranslation();

  useEffect(() => {
    mermaid.initialize({
      startOnLoad: false,
      theme: isDark ? 'dark' : 'base',
      securityLevel: 'loose',
      themeCSS: `
      .relation {
        stroke: ${theme.palette.divider};
        stroke-width: 1;
      }

      .nodes rect {
        fill: ${(isDark ? lighten : darken)(theme.palette.background.paper, 0.05)}
      }
      `
    });
  }, [isDark, theme]);

  useEffect(() => {
    mermaid.run();
  });

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, codeTabs]}
      rehypePlugins={[rehypeRaw]}
      urlTransform={(value: string) => value}
      components={{
        code({ node, className, children, ...props }) {
          if (node.children?.length === 1 && node.children[0].type === 'text') {
            if (node.children[0].value.startsWith('t(')) {
              return <span>{t(node.children[0].value.replace(/t\((.+)\)/, '$1'))}</span>;
            } else if (components[node.children[0].value]) {
              return components[node.children[0].value];
            }
          }

          const match = /language-(\w+)/.exec(className || '');

          if (match && ['alert', 'notebook', 'tabs'].includes(match[1])) {
            return customComponents(match[1], children);
          }

          if (match?.[1] === 'mermaid') {
            return <pre className="mermaid">{(node.children[0] as any).value}</pre>;
          }

          if (match?.[1] === 'json') {
            try {
              return <JSONViewer data={JSON.parse((node.children[0] as any).value)} />;
            } catch (e) {
              return <code style={{ color: 'red' }}>{t('markdown.json.invalid')}</code>;
            }
          }

          return match ? (
            <SyntaxHighlighter
              // eslint-disable-next-line react/no-children-prop
              children={String(children).replace(/\n$/, '')}
              style={isDark ? oneDark : oneLight}
              language={match[1]}
              PreTag="div"
              {...props}
            />
          ) : (
            <code className={className} {...props}>
              {children}
            </code>
          );
        },
        blockquote({ children }) {
          return <Box sx={{ pl: 1, borderLeft: `2px solid ${theme.palette.divider}` }}>{children}</Box>;
        },
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        img({ node, ...props }) {
          // eslint-disable-next-line jsx-a11y/alt-text
          return <Image {...props} style={{ ...props.style, maxWidth: '75%' }} />;
        },
        table({ children }) {
          return (
            <TableContainer component={Paper}>
              <Table>{children}</Table>
            </TableContainer>
          );
        },
        thead({ children }) {
          return <TableHead>{children}</TableHead>;
        },
        tr({ children }) {
          return <TableRow>{children}</TableRow>;
        },
        th({ children, ...props }) {
          return <TableCell style={props.style}>{children}</TableCell>;
        },
        td({ children, ...props }) {
          return <TableCell style={props.style}>{children}</TableCell>;
        },
        a({ children, ...props }) {
          if (!props.href) {
            return <a {...props}>{children}</a>;
          }

          if (props.href?.startsWith('/')) {
            return (
              <Link to={props.href} {...props}>
                {children}
              </Link>
            );
          }

          if (!disableLinks) {
            return <a {...props}>{children}</a>;
          }

          if (props.href.startsWith('#')) {
            return <a {...props}>{children}</a>;
          }

          const parsed = new URL(props.href);
          if (parsed.hostname.endsWith('gc.ca')) {
            return <a {...props}>{children}</a>;
          }

          return (
            <span>
              {children}
              {props.href !== children && ` (${props.href})`}
            </span>
          );
        }
      }}
    >
      {md?.replace(/<!--.+?-->/g, '')}
    </ReactMarkdown>
  );
};

export default memo(Markdown);
