/* eslint-disable no-console */
import Handlebars from 'handlebars';
import asyncHelpers from 'handlebars-async-helpers';
import type { FC, ReactElement } from 'react';
import { memo, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import Throttler from 'utils/Throttler';
import { hashCode } from 'utils/utils';
import Markdown, { type MarkdownProps } from '../display/Markdown';
import { useHelpers } from './handlebars/helpers';

type HandlebarsInstance = typeof Handlebars;

interface HandlebarsMarkdownProps extends MarkdownProps {
  object?: { [index: string]: any };
  disableLinks?: boolean;
}

const THROTTLER = new Throttler(500);

const HandlebarsMarkdown: FC<HandlebarsMarkdownProps> = ({ md, object = {}, disableLinks = false }) => {
  const { t } = useTranslation();
  const helpers = useHelpers();

  const [rendered, setRendered] = useState('');

  const [mdComponents, setMdComponents] = useState<Record<string, ReactElement>>({});

  const handlebars: HandlebarsInstance = useMemo(() => {
    const instance = asyncHelpers(Handlebars);

    instance.registerHelper('img', async context => {
      const hash = Object.fromEntries(
        await Promise.all(Object.entries(context.hash).map(async ([key, val]) => [key, await val]))
      );

      if (!hash.src) {
        return '';
      }

      const props = Object.entries(hash)
        .map(([key, val]) => `${key}="${val}"`)
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
              result.then(_result => setMdComponents(_components => ({ ..._components, [id]: _result })));
            } else {
              setMdComponents(_components => ({ ..._components, [id]: result }));
            }
          }
          return new Handlebars.SafeString(`\`${id}\``);
        }

        return helper.callback(...args);
      });
    });
  }, [handlebars, mdComponents]);

  useEffect(() => {
    THROTTLER.debounce(async () => {
      try {
        const compiled = handlebars.compile(md || '');

        setRendered(await compiled(object));
      } catch (err) {
        // eslint-disable-next-line no-console
        console.error(err);

        setRendered(`
<h2 style="color: red">${t('markdown.error')}</h2>

**\`${err.toString()}\`**

<code style="font-size: 0.8rem"><pre>
${err.stack}
</pre></code>
        `);
      }
    });
  }, [md, handlebars, object, t]);

  return <Markdown md={rendered} disableLinks={disableLinks} components={mdComponents} />;
};

export default memo(HandlebarsMarkdown);
