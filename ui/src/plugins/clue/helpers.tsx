/* eslint-disable no-console */
import EnrichedTypography, { type EnrichedTypographyProps } from '@cccsaurora/clue-ui/components/EnrichedTypography';
import Fetcher from '@cccsaurora/clue-ui/components/fetchers/Fetcher';
import Entry from '@cccsaurora/clue-ui/components/group/Entry';
import Group from '@cccsaurora/clue-ui/components/group/Group';
import { useClueEnrichSelector } from '@cccsaurora/clue-ui/hooks/selectors';
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
import FlexOne from 'components/elements/addons/layout/FlexOne';
import type { HowlerHelper } from 'components/elements/display/handlebars/helpers';
import i18nInstance from 'i18n';
import capitalize from 'lodash-es/capitalize';
import groupBy from 'lodash-es/groupBy';
import uniq from 'lodash-es/uniq';
import { type FC, type PropsWithChildren, useState } from 'react';
import { useTranslation } from 'react-i18next';

interface ClueCell {
  column: string;
  row: string;
  value: string;
  clue_type?: string;
  clue_fetcher?: string;
  fetcher_width?: string;
  clue_entity?: boolean;
  action_value?: string;
}

const MarkdownTypography: FC<EnrichedTypographyProps & TypographyProps> = ({ type, value, ...props }) => {
  const { t } = useTranslation();

  try {
    const guessType = useClueEnrichSelector(ctx => ctx.guessType);

    if (!type || type?.toString().toLowerCase() === 'guess') {
      type = guessType(value.toString());
    }

    if (!type) {
      return <span>{value}</span>;
    }

    return <EnrichedTypography {...props} type={type} value={value} />;
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

const ClueGroup: FC<PropsWithChildren<{ type: string; enabled?: boolean }>> = props => {
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

const ClueEntry: FC<{ value: string }> = ({ value }) => {
  const [checked, setChecked] = useState(false);

  return (
    <Entry entry={value} selected={checked}>
      <Paper sx={{ p: 1 }}>
        <Stack direction="row" spacing={1}>
          <Checkbox checked={checked} onChange={(_event, _checked) => setChecked(_checked)} />
          <MarkdownTypography value={value} />
          <FlexOne />
        </Stack>
      </Paper>
    </Entry>
  );
};

const ClueCheckbox: FC<{ value: string }> = ({ value }) => {
  const [checked, setChecked] = useState(false);

  return (
    <Entry entry={value} selected={checked}>
      <Checkbox checked={checked} onChange={(_event, _checked) => setChecked(_checked)} />
    </Entry>
  );
};

const HELPERS: HowlerHelper[] = [
  {
    keyword: 'clue',
    documentation: {
      en: 'Given a selector, this helper enriches the selector through clue.',
      fr: 'Étant donné un sélecteur, cet assistant enrichit le sélecteur via clue.'
    },
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
        <MarkdownTypography
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
    documentation: {
      en: 'Given a selector, this helper fetches data for the selector through clue.',
      fr: 'Étant donné un sélecteur, cet assistant récupère les données pour le sélecteur via clue.'
    },
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

      if (props.fetcherId.includes('eml')) {
        props.fetcherId = props.fetcherId.replace('eml', 'email');
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
    keyword: 'clue_group',
    documentation: {
      en: 'Initializes a clue group',
      fr: 'Initialise un groupe clue'
    },
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
        <ClueGroup type={props.type} enabled>
          <Stack spacing={1} mt={1}>
            {uniq(values as any[]).map(value => (
              <ClueEntry key={value} value={value} />
            ))}
          </Stack>
        </ClueGroup>
      );
    }
  },
  {
    keyword: 'clue_table',
    documentation: {
      en: `Render a table with optional Clue enrichments, fetchers and actions.

Clue enrichments are performed for cells with a clue_type and no clue_fetcher.

Clue fetchers are used for cells with a clue_type and a clue_fetcher.

Clue actions are enabled by specifying a clue action type using the optional clue_action_type parameter. If enabled, cells with clue_entity==true will be selectable for use with Clue enrichments and actions, with a value of action_value if present, and otherwise value.

Example:
\`\`\`markdown
{{curly 'clue_table clue_table_cells clue_action_type="ip"'}}
\`\`\`
where clue_table_cells is an array with properties:

\`\`\`
  column: string;
  row: string;
  value: string;
  clue_type (optional): string;
  clue_fetcher (optional): string;
  fetcher_width (optional): string;
  clue_entity (optional): boolean;
  action_value (optional): string;
\`\`\`
    `,
      fr: `Affiche un tableau avec des enrichissements, des extractions et des actions Clue optionnelles.

Les enrichissements Clue sont effectués pour les cellules avec un clue_type et sans un clue_fetcher.

Clue récupère les données pour le sélecteur pour les cellules avec un clue_type et un clue_fetcher.

Les actions Clue sont activées en spécifiant un type d'action clue en utilisant le paramètre optionnel clue_action_type. Si activé, les cellules avec clue_entity==true seront sélectionnables pour utilisation avec les enrichissements et actions Clue, avec une valeur de action_value si présente, sinon la valeur.

Exemple :
\`\`\`markdown
{{curly 'clue_table clue_table_cells clue_action_type="ip"'}}
\`\`\`
où clue_table_cells est un tableau avec les propriétés :

\`\`\`
  column: string;
  row: string;
  value: string;
  clue_type (optionnel): string;
  clue_fetcher (optionnel): string;
  fetcher_width (optionnel): string;
  clue_entity (optionnel): boolean;
  action_value (optionnel): string;
\`\`\`
    `
    },
    componentCallback: (cells: ClueCell[], ...args: any[]) => {
      const options = args.pop() as Handlebars.HelperOptions;
      const props = options?.hash ?? {};

      const columns = Object.keys(groupBy(cells, 'column'));
      const rows = groupBy(cells, 'row');

      const clueActionType = props.clue_action_type;
      const enableClueActions = !!clueActionType;

      return (
        <Paper sx={{ width: '95%', overflowX: 'auto', m: 1 }}>
          <ClueGroup type={clueActionType} enabled={enableClueActions}>
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

                        if (!cell) {
                          return <TableCell key={col} />;
                        }

                        return (
                          <TableCell key={col + cell.value}>
                            {enableClueActions && cell.clue_entity && (
                              <ClueCheckbox value={cell.action_value ?? cell.value} />
                            )}
                            {!!cell.clue_fetcher && !!cell.clue_type ? (
                              <Fetcher
                                slotProps={{
                                  image: { width: !!cell.fetcher_width ? cell.fetcher_width : 'fit-content' },
                                  stack: {
                                    component: 'span',
                                    sx: !!cell.fetcher_width
                                      ? { width: cell.fetcher_width, display: 'block' }
                                      : { width: 'fit-content' }
                                  }
                                }}
                                fetcherId={cell.clue_fetcher}
                                value={cell.value}
                                type={cell.clue_type}
                              />
                            ) : !!cell.clue_type ? (
                              <MarkdownTypography
                                slotProps={{
                                  stack: {
                                    component: 'span',
                                    sx: { width: 'fit-content' },
                                    display: 'inline-flex'
                                  }
                                }}
                                component="span"
                                type={cell.clue_type}
                                value={cell.value}
                              />
                            ) : (
                              (cell.value ?? 'N/A')
                            )}
                          </TableCell>
                        );
                      })}
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </ClueGroup>
        </Paper>
      );
    }
  }
];

export default HELPERS;
