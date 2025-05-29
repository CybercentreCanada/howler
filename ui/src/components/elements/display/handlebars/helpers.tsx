/* eslint-disable no-console */
import { Paper, Table, TableBody, TableCell, TableHead, TableRow } from '@mui/material';
import AppListEmpty from 'commons/components/display/AppListEmpty';
import HitCard from 'components/elements/hit/HitCard';
import { HitLayout } from 'components/elements/hit/HitLayout';
import { flatten } from 'flat';
import Handlebars from 'handlebars';
import { capitalize, get, groupBy, isObject } from 'lodash-es';
import { type ReactElement } from 'react';
import JSONViewer from '../json/JSONViewer';

export interface HowlerHelper {
  keyword: string;
  documentation?: string;
  callback?: Handlebars.HelperDelegate;
  componentCallback?: (...args: any[]) => ReactElement | Promise<ReactElement>;
}

interface Cell {
  column: string;
  row: string;
  value: string;
}

export const HELPERS: HowlerHelper[] = [
  {
    keyword: 'equals',
    documentation: 'Checks the equality of the string representation of the two arguments.',
    callback: (arg1, arg2) => arg1?.toString() === arg2.toString()
  },
  {
    keyword: 'and',
    documentation: 'Runs the comparison `arg1 && arg2`, and returns the result.',
    callback: (arg1, arg2) => arg1 && arg2
  },
  {
    keyword: 'or',
    documentation: 'Runs the comparison `arg1 || arg2`, and returns the result.',
    callback: (arg1, arg2) => arg1 || arg2
  },
  { keyword: 'not', documentation: 'Runs the comparison `!arg`, and returns the result.', callback: arg => !arg },
  {
    keyword: 'curly',
    documentation: 'Wraps the given argument in curly braces.',
    callback: arg1 => new Handlebars.SafeString(`{{${arg1}}}`)
  },
  {
    keyword: 'join',
    documentation: 'Joins two string arguments with a given string `sep`, or the empty string as a default.',
    callback: (arg1: string, arg2: string, context) =>
      [arg1?.toString() ?? '', arg2?.toString() ?? ''].join(context.hash?.sep ?? '')
  },
  {
    keyword: 'upper',
    documentation: 'Returns the uppercase representation of a string argment.',
    callback: (val: string) => val.toLocaleUpperCase()
  },
  {
    keyword: 'lower',
    documentation: 'Returns the lowercase representation of a string argment.',
    callback: (val: string) => val.toLocaleLowerCase()
  },
  {
    keyword: 'fetch',
    documentation:
      'Fetches the url provided and returns the given (flattened) key from the returned JSON object. Note that the result must be JSON!',
    callback: async (url, key) => {
      try {
        const response = await fetch(url);
        const json = await response.json();

        return flatten(json)[key];
      } catch (e) {
        return '';
      }
    }
  },
  {
    keyword: 'howler',
    documentation: 'Given a howler hit ID, this helper renders a hit card for that ID.',
    componentCallback: id => {
      if (!id) {
        return <AppListEmpty />;
      }

      return <HitCard id={id} layout={HitLayout.NORMAL} />;
    }
  },
  {
    keyword: 'entries',
    documentation: 'Given a dict, return an array of {key, value} objects.',
    callback: obj => {
      if (!isObject(obj)) {
        return new Handlebars.SafeString('Invalid Object.');
      }

      return Object.entries(obj).map(([key, value]) => ({ key, value }));
    }
  },
  {
    keyword: 'render_json',
    documentation: 'Given a howler hit ID, this helper renders a hit card for that ID.',
    componentCallback: data => {
      if (!data) {
        return <AppListEmpty />;
      }

      return <JSONViewer data={data} />;
    }
  },
  {
    keyword: 'to_json',
    documentation: 'Convert any object into a JSON string.',
    callback: obj => {
      return new Handlebars.SafeString(JSON.stringify(obj));
    }
  },
  {
    keyword: 'parse_json',
    documentation: 'Convert JSON string into and object.',
    callback: str => {
      return JSON.parse(str);
    }
  },
  {
    keyword: 'get',
    documentation: 'Returns the given (flattened) key from the provided object.',
    callback: async (data, key) => {
      try {
        return get(data, key);
      } catch (e) {
        return '';
      }
    }
  },
  {
    keyword: 'includes',
    documentation: 'Checks if field is in string',
    callback: (arg1, arg2) => {
      return !!arg2 && !!arg1?.includes(arg2);
    }
  },

  {
    keyword: 'table',
    documentation: 'Render a table in markdown given an array of cells',
    componentCallback: (cells: Cell[]) => {
      const columns = Object.keys(groupBy(cells, 'column'));
      const rows = groupBy(cells, 'row');

      return (
        <Paper sx={{ width: '95%', overflowX: 'auto', m: 1 }}>
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

                      return <TableCell key={col + cell?.value}>{cell?.value ?? 'N/A'}</TableCell>;
                    })}
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </Paper>
      );
    }
  }
];
