/* eslint-disable no-console */
import Handlebars, { type Exception } from 'handlebars';
import asyncHelpers from 'handlebars-async-helpers';
import type { FC, ReactElement } from 'react';
import { memo, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import Throttler from 'utils/Throttler';
import { hashCode } from 'utils/utils';
import Markdown, { type MarkdownProps } from '../display/Markdown';
import { HowlerHelperError, useHelpers } from './handlebars/helpers';

type HandlebarsInstance = typeof Handlebars;

interface HandlebarsMarkdownProps extends MarkdownProps {
  object?: { [index: string]: any };
  disableLinks?: boolean;
}

class HowlerHandlebarsRenderError extends Error {
  helper: string;
  hint?: string;

  constructor(message: string, helper: string, hint?: string) {
    super(Handlebars.escapeExpression(message));
    this.name = 'HowlerHandlebarsRenderError';
    this.helper = Handlebars.escapeExpression(helper);
    this.hint = hint ? Handlebars.escapeExpression(hint) : undefined;
  }
}

const THROTTLER = new Throttler(500);

const HandlebarsMarkdown: FC<HandlebarsMarkdownProps> = ({ md, object = {}, disableLinks = false }) => {
  const { t } = useTranslation();
  const helpers = useHelpers();

  const [rendered, setRendered] = useState('');

  const [mdComponents, setMdComponents] = useState<Record<string, ReactElement>>({});

  const handlebars: HandlebarsInstance = useMemo(() => {
    const instance = asyncHelpers(Handlebars);

    instance.registerHelper('img', async (context: Handlebars.HelperOptions) => {
      const hash = Object.fromEntries(
        await Promise.all(Object.entries(context.hash).map(async ([key, val]) => [key, await val]))
      ) as Record<string, string>;

      if (!hash.src) {
        return '';
      }

      const props = Object.entries(hash)
        .map(([key, val]: [string, string]) => `${key}="${val}"`)
        .join(' ');

      return new Handlebars.SafeString(`<img ${props} >`);
    });

    return instance;
  }, []);

  useEffect(() => {
    helpers.forEach(helper => {
      if (handlebars.helpers[helper.keyword] && !helper.componentCallback) {
        return;
      }

      handlebars.registerHelper(helper.keyword, (...args: any[]) => {
        console.debug(`Running helper ${helper.keyword}`);

        if (helper.componentCallback) {
          const id = hashCode(JSON.stringify([helper.keyword, ...args])).toString();
          if (!mdComponents[id]) {
            const result = helper.componentCallback(...args);

            if (result instanceof Promise) {
              void result.then(_result => setMdComponents(_components => ({ ..._components, [id]: _result })));
            } else {
              setMdComponents(_components => ({ ..._components, [id]: result }));
            }
          }

          return new Handlebars.SafeString(`\`${id}\``);
        }
        try {
          const result = helper.callback(...args);
          return result instanceof Promise
            ? result.catch(err => {
                if (err instanceof HowlerHelperError) {
                  throw new HowlerHandlebarsRenderError(err.message, helper.keyword, helper.hint);
                }
                throw err;
              })
            : result;
        } catch (err) {
          if (err instanceof HowlerHelperError) {
            throw new HowlerHandlebarsRenderError(err.message, helper.keyword, helper.hint);
          }
          throw err;
        }
      });
    });
  }, [handlebars, helpers, mdComponents]);

  useEffect(() => {
    THROTTLER.debounce(async () => {
      // Types are a bit muddled here due to the async helpers
      const compiled = handlebars.compile(md || '') as unknown as (obj: any) => PromiseLike<string>;
      try {
        setRendered(await compiled(object));
      } catch (err) {
        if ((err as Exception).message?.startsWith('Missing helper')) {
          const missingHelper = (err as Exception).message.replace(/.+"(.+)"/, '$1');
          handlebars.registerHelper(
            missingHelper,
            () =>
              new Handlebars.SafeString(
                `<span style="color: red; font-weight: bold; font-family: monospace;">Missing helper ${missingHelper}</span>`
              )
          );

          setRendered(await compiled(object));
          return;
        }

        if (err instanceof HowlerHandlebarsRenderError) {
          setRendered(`
<h2 style="color: red">${t('markdown.error')}</h2>
<span style="color: red; font-weight: bold; font-family: monospace;">Invalid Usage [${err.helper}]: ${err.message}</span>
${err.hint ? `<br/><span style="color: gray; font-family: monospace;">${err.hint}</span>` : ''}
          `);
          return;
        }

        // eslint-disable-next-line no-console
        console.error(err);

        setRendered(`
<h2 style="color: red">${t('markdown.error')}</h2>

**\`${err instanceof Error ? err.toString() : String(err)}\`**

<code style="font-size: 0.8rem"><pre>
${err instanceof Error ? err.stack : ''}
</pre></code>
        `);
      }
    });
  }, [md, handlebars, object, t]);

  return <Markdown md={rendered} disableLinks={disableLinks} components={mdComponents} />;
};

export default memo(HandlebarsMarkdown);
