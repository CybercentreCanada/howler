/* eslint-disable no-console */
import {
  type TypographyProps,
  Checkbox,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow
} from '@mui/material';
import {
  type EnrichedTypographyProps,
  EnrichedTypography,
  Entry,
  Fetcher,
  Group,
  useBorealisEnrichSelector
} from 'borealis-ui';
import FlexOne from 'components/elements/addons/layout/FlexOne';
import i18nInstance from 'i18n';
import { capitalize, groupBy, uniq } from 'lodash-es';
import { type FC, type PropsWithChildren, useState } from 'react';
import { useTranslation } from 'react-i18next';

interface BorealisCell {
  column: string;
  row: string;
  value: string;
  borealis_type?: string;
  borealis_entity?: boolean;
  action_value?: string;
}

const BorealisTypography: FC<EnrichedTypographyProps & TypographyProps> = props => {
  const { t } = useTranslation();

  try {
    const guessType = useBorealisEnrichSelector(ctx => ctx.guessType);

    let type: string = props.type;
    if (!type || type?.toLowerCase() === 'guess') {
      type = guessType(props.value);
    }

    if (!type) {
      return <span>{props.value}</span>;
    }

    return <EnrichedTypography {...props} type={type} />;
  } catch (err) {
    return (
      <Stack>
        <strong style={{ color: 'red' }}>{t('markdown.error')}</strong>
        <strong>{err.toString()}</strong>
        <code style={{ fontSize: '0.8rem' }}>
          <pre>{err.stack}</pre>
        </code>
      </Stack>
    );
  }
};

const BorealisGroup: FC<PropsWithChildren<{ type: string; enabled?: boolean }>> = props => {
  if (!props.enabled) {
    return <>{props.children}</>;
  }
  if (!props.type) {
    console.error('Missing required props for group helper');
    return (
      <Stack spacing={1}>
        <strong style={{ color: 'red' }}>{i18nInstance.t('markdown.error')}</strong>
        {/* eslint-disable-next-line react/jsx-no-literals */}
        <code style={{ fontSize: '0.8rem' }}>{i18nInstance.t('markdown.props.missing')}: type</code>
      </Stack>
    );
  }

  return <Group type={props.type}>{props.children}</Group>;
};

const BorealisEntry: FC<{ value: string }> = ({ value }) => {
  const [checked, setChecked] = useState(false);

  return (
    <Entry entry={value} selected={checked}>
      <Paper sx={{ p: 1 }}>
        <Stack direction="row" spacing={1}>
          <Checkbox checked={checked} onChange={(_event, _checked) => setChecked(_checked)} />
          <BorealisTypography value={value} />
          <FlexOne />
        </Stack>
      </Paper>
    </Entry>
  );
};

const BorealisCheckbox: FC<{ value: string }> = ({ value }) => {
  const [checked, setChecked] = useState(false);

  return (
    <Entry entry={value} selected={checked}>
      <Checkbox checked={checked} onChange={(_event, _checked) => setChecked(_checked)} />
    </Entry>
  );
};

const HELPERS = [
  {
    keyword: 'borealis',
    documentation: 'Given a selector, this helper enriches the selector through borealis.',
    componentCallback: (type, value) => {
      if (typeof type !== 'string' || typeof value !== 'string') {
        return (
          <Stack spacing={1}>
            <strong style={{ color: 'red' }}>{i18nInstance.t('markdown.error')}</strong>
            {/* eslint-disable-next-line react/jsx-no-literals */}
            <code style={{ fontSize: '0.8rem' }}>You must provide at least two arguments: type and value.</code>
          </Stack>
        );
      }

      return (
        <BorealisTypography
          slotProps={{ stack: { component: 'span', sx: { width: 'fit-content' } } }}
          component="span"
          type={type}
          value={typeof value === 'string' ? value : null}
        />
      );
    }
  },

  {
    keyword: 'fetcher',
    documentation: 'Given a selector, this helper fetches data for the selector through borealis.',
    componentCallback: (...args: any[]) => {
      const options = args.pop() as Handlebars.HelperOptions;
      const props = options?.hash ?? {};

      if (!props.type || !props.value || !props.fetcherId) {
        console.error('Missing required props for fetcher helper');
        return (
          <Stack spacing={1}>
            <strong style={{ color: 'red' }}>{i18nInstance.t('markdown.error')}</strong>
            <code style={{ fontSize: '0.8rem' }}>
              {i18nInstance.t('markdown.props.missing')}:{' '}
              {['type', 'value', 'fetcherId'].filter(key => !props[key]).join(', ')}
            </code>
          </Stack>
        );
      }

      console.debug(`Rendering fetcher (${props.fetcherId}) for selector ${props.type}:${props.value}`);

      return (
        <Fetcher
          slotProps={{ stack: { component: 'span', sx: { width: 'fit-content' } } }}
          component="span"
          {...props}
        />
      );
    }
  },

  {
    keyword: 'borealis_group',
    documentation: 'Initializes a borealis group',
    componentCallback: (values: any, ...args: any[]) => {
      const options = args.pop() as Handlebars.HelperOptions;
      const props = options?.hash ?? {};

      const missing: string[] = [];
      if (!Array.isArray(values)) {
        missing.push('values');
      }

      if (!props.type) {
        missing.push('type');
      }

      if (missing.length > 0) {
        return (
          <Stack spacing={1}>
            <strong style={{ color: 'red' }}>{i18nInstance.t('markdown.error')}</strong>
            <code style={{ fontSize: '0.8rem' }}>
              {i18nInstance.t('markdown.props.missing')}: {missing.join(', ')}
            </code>
          </Stack>
        );
      }

      return (
        <BorealisGroup type={props.type} enabled>
          <Stack spacing={1} mt={1}>
            {uniq(values as any[]).map(value => (
              <BorealisEntry key={value} value={value} />
            ))}
          </Stack>
        </BorealisGroup>
      );
    }
  },
  {
    keyword: 'borealis_table',
    documentation: `Render a table with optional Borealis enrichments and actions.

Borealis enrichments are performed for cells with a borealis_type.

Borealis actions are enabled by specifying a borealis action type using the optional borealis_action_type parameter. If enabled, cells with borealis_entity==true will be selectable for use with Borealis enrichments and actions, with a value of action_value if present, and otherwise value.

Example:
\`\`\`markdown
{{curly 'borealis_table borealis_table_cells borealis_action_type="ip"'}}
\`\`\`
where borealis_table_cells is an array with properties:

\`\`\`
  column: string;
  row: string;
  value: string;
  borealis_type (optional): string;
  borealis_entity (optional): boolean;
  action_value (optional): string;
\`\`\`
    `,
    componentCallback: (cells: BorealisCell[], ...args: any[]) => {
      const options = args.pop() as Handlebars.HelperOptions;
      const props = options?.hash ?? {};

      const columns = Object.keys(groupBy(cells, 'column'));
      const rows = groupBy(cells, 'row');

      const enableBorealisActions = !props.borealis_action_type ? false : true;
      const borealisActionType = !props.borealis_action_type ? 'false' : props.borealis_action_type;

      return (
        <Paper sx={{ width: '95%', overflowX: 'auto', m: 1 }}>
          <BorealisGroup type={borealisActionType} enabled={enableBorealisActions}>
            <Table>
              <TableHead>
                <TableRow>
                  {columns.map(col => (
                    <TableCell key={col} sx={{ maxWidth: '150px' }}>
                      {col
                        .split(/[_-]/)
                        .map(word => capitalize(word))
                        .join(' ')}
                    </TableCell>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody sx={{ '& td': { wordBreak: 'break-word' } }}>
                {Object.entries(rows).map(([rowId, _cells]) => {
                  return (
                    <TableRow key={rowId}>
                      {columns.map(col => {
                        const cell = _cells.find(row => row.column === col);

                        return (
                          <TableCell key={col + cell?.value}>
                            {enableBorealisActions && typeof cell.borealis_entity && cell.borealis_entity === true ? (
                              <BorealisCheckbox value={cell.action_value ?? cell.value} />
                            ) : null}
                            {typeof cell.borealis_type === 'string' ? (
                              <BorealisTypography
                                slotProps={{
                                  stack: {
                                    component: 'span',
                                    sx: { width: 'fit-content' },
                                    display: 'inline-flex'
                                  }
                                }}
                                component="span"
                                type={cell?.borealis_type}
                                value={cell?.value}
                              />
                            ) : (
                              (cell?.value ?? 'N/A')
                            )}
                          </TableCell>
                        );
                      })}
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </BorealisGroup>
        </Paper>
      );
    }
  }
];

export default HELPERS;
