import type * as mdast from 'mdast';
import type * as unified from 'unified';
import { visit } from 'unist-util-visit';

//this plugins aims to bring docusaurus tabs functionality to base react-markdown.
//will expose a code tabs elements which can be later rendered with a custom component

const findTabs = (index, parent) => {
  const { children } = parent;
  const tabs = [];

  while (index++ < children.length) {
    const child = children[index];

    if (child && child.type === 'code') {
      const metaString = `${child.lang ?? ''} ${child.meta ?? ''}`.trim();
      if (!metaString) break;
      const [tabtitle] = metaString.match(/(?<=tab=("|'))(.*?)(?=("|'))/) ?? [''];
      if (!tabtitle) {
        // eslint-disable-next-line no-console
        console.warn('Failed to parse tab title.');
        break;
      }

      tabs.push({ title: tabtitle, lang: child.lang, value: child.value });
    } else {
      break;
    }
  }

  return tabs;
};

export const codeTabs: unified.Plugin<[], mdast.Root> = () => {
  return (tree, file) => {
    visit(tree, 'code', (node, index, parent) => {
      const metaString = `${node.lang ?? ''} ${node.meta ?? ''}`.trim();
      if (!metaString) {
        return;
      }
      const [tab] = metaString.match(/(?<=tab=("|'))(.*?)(?=("|'))/) ?? [''];
      if (!tab && metaString.includes('tab=')) {
        file.message('Invalid tab title', node, 'remark-code-title');
        return;
      }
      if (!tab) {
        return;
      }

      const tabs = [{ title: tab, lang: node.lang, value: node.value }, ...findTabs(index, parent)];

      if (tabs.length > 1) {
        const tabsNode: mdast.Code = {
          type: 'code',
          lang: 'tabs',
          value: JSON.stringify(tabs)
        };

        parent.children.splice(index, tabs.length, tabsNode);

        return index + tabs.length - 1;
      } else {
        const titleNode: mdast.Paragraph = {
          type: 'paragraph',
          data: {
            hName: 'div',
            hProperties: {
              'data-remark-code-title': true,
              'data-language': node.lang
            }
          },
          children: [{ type: 'text', value: tab }]
        };

        parent.children.splice(index, 0, titleNode);
        /* Skips this node (title) and the next node (code) */
        return index + 2;
      }
    });
  };
};
