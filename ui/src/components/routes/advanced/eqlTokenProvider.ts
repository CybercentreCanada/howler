/* eslint-disable no-useless-escape */
import type { languages } from 'monaco-editor';

/**
 * Monaco language token provider for EQL. Very basic. Contact Matt R <matthew.rafuse@cyber.gc.ca> for more info, and/or read:
 * https://microsoft.github.io/monaco-editor/monarch.html
 * https://www.elastic.co/guide/en/elasticsearch/reference/current/eql-syntax.html
 */
const TOKEN_PROVIDER: languages.IMonarchLanguage = {
  defaultToken: 'invalid',
  includeLF: true,

  operators: /[<:>+\-*/%=\|~]|<=|==|!=|>=/,

  timespans: /[0-9]+[dhms]|ms|micros|nanos/,

  keywords: ['where', 'like', 'regex', 'in', 'in~', 'not', 'descendant', 'child', 'event', 'of', 'head', 'tail'],

  booleans: ['and', 'or'],

  function: /[a-zA-Z]+(?=~?\()/,

  regexpctl: /[(){}\[\]\$\^|\-*+?\.]/,
  regexpesc: /\\(?:[bBdDfnrstvwWn0\\\/]|@regexpctl|c[A-Z]|x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4})/,

  tokenizer: {
    root: [
      // TODO: Match this to valid field names in ES
      ['@function', { token: 'identifier' }],
      [
        /[a-zA-Z_*]+/,
        {
          cases: {
            '@keywords': 'operator',
            '@booleans': 'boolean',
            '@default': 'key'
          }
        }
      ],
      ['@operators', { token: 'operator' }],
      [/\./, { token: 'dot' }],

      // parens
      [/[\[\(]/, { token: 'bracket', bracket: '@open', next: '@parens_root' }],

      // whitespace
      [/[ \t\r\n]+/, { token: 'whitespace' }],

      { include: 'common' }
    ],

    boolean: [[/true|false|and|or/, 'boolean']],

    common: [
      // regular expression: ensure it is terminated before beginning (otherwise it is an opeator)
      [
        /\/(?=([^\\\/]|\\.)+\/([gimsuy]*)(\s*)(\.|;|\/|,|\)|\]|\}|$))/,
        { token: 'regexp', bracket: '@open', next: '@regexp' }
      ],

      // strings
      [/"([^"\\]|\\.)*$/, { token: 'string.invalid' }], // non-teminated string
      [/"/, { token: 'string.quote', bracket: '@open', next: '@string' }],

      // comments
      [/#.*\n/, { token: 'comment' }],

      // numbers
      ['@timespans', 'number.hex'],
      [/\d*\.\d+([eE][-+]?\d+)?/, 'number.float'],
      [/0[xX][0-9a-fA-F]+/, 'number.hex'],
      [/\d+/, 'number'],

      // commas
      [/,/, 'comma']
    ],

    parens_root: [{ include: '@root' }, [/[\]\)]/, { token: 'bracket', next: '@pop' }]],

    string: [
      [/[^"']+/, { token: 'string' }],
      [/"/, { token: 'string.quote', bracket: '@close', next: '@pop' }]
    ],

    regexp: [
      [/(\{)(\d+(?:,\d*)?)(\})/, ['regexp.escape.control', 'regexp.escape.control', 'regexp.escape.control']],
      [
        /(\[)(\^?)(?=(?:[^\]\\\/]|\\.)+)/,
        ['regexp.escape.control', { token: 'regexp.escape.control', next: '@regexrange' }]
      ],
      [/(\()(\?:|\?=|\?!)/, ['regexp.escape.control', 'regexp.escape.control']],
      [/[()]/, 'regexp.escape.control'],
      [/@regexpctl/, 'regexp.escape.control'],
      [/[^\\\/]/, 'regexp'],
      [/@regexpesc/, 'regexp.escape'],
      [/\\\./, 'regexp.invalid'],
      [/(\/)([gimsuy]*)/, [{ token: 'regexp', bracket: '@close', next: '@pop' }, 'keyword.other']]
    ],

    regexrange: [
      [/-/, 'regexp.escape.control'],
      [/\^/, 'regexp.invalid'],
      [/@regexpesc/, 'regexp.escape'],
      [/[^\]]/, 'regexp'],
      [/\]/, { token: 'regexp.escape.control', next: '@pop', bracket: '@close' }]
    ]
  }
};

export default TOKEN_PROVIDER;
