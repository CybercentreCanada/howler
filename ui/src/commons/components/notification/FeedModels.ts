export type SystemMessage = {
  user: string;
  title: string;
  severity: 'success' | 'info' | 'warning' | 'error';
  message: string;
};

export type FeedItem = {
  id: string;
  url?: string;
  external_url?: string;
  title?: string;
  content_html?: string;
  content_text?: string;
  content_md?: string;
  summary?: string;
  image?: string;
  banner_image?: string;
  date_published?: Date;
  date_modified?: Date;
  authors?: Array<FeedAuthor>;
  tags?: Array<'new' | 'current' | 'dev' | 'service' | 'blog'>;
  language?: string;
  attachments?: Array<FeedAttachment>;
  _isNew: boolean;
};

export type FeedAuthor = {
  name?: string;
  url?: string;
  avatar?: string;
};

export type FeedAttachment = {
  url: string;
  mime_type: string;
  title?: string;
  size_in_bytes?: number;
  duration_in_seconds?: number;
};

export type Feed = {
  version: string;
  title: string;
  home_page_url?: string;
  feed_url?: string;
  description?: string;
  user_comment?: string;
  next_url?: string;
  icon?: string;
  favicon?: string;
  authors?: Array<FeedAuthor>;
  language?: string;
  expired?: boolean;
  hubs?: Array<{ type: string; url: string }>;
  items: Array<FeedItem>;
};

export const DEFAULT_FEED: Feed = {
  version: null,
  title: null,
  home_page_url: null,
  feed_url: null,
  description: null,
  user_comment: null,
  next_url: null,
  icon: null,
  favicon: null,
  authors: [],
  language: null,
  expired: false,
  hubs: [],
  items: []
};

export const DEFAULT_FEED_ITEM: FeedItem = {
  id: null,
  url: null,
  external_url: null,
  title: null,
  content_html: null,
  content_text: null,
  summary: null,
  image: null,
  banner_image: null,
  date_published: new Date(0),
  date_modified: new Date(0),
  authors: [],
  tags: [],
  language: null,
  attachments: [],
  _isNew: false
};

export const DEFAULT_FEED_ATTACHMENT: FeedAttachment = {
  url: null,
  mime_type: null,
  title: null,
  size_in_bytes: 0,
  duration_in_seconds: 0
};

export const DEFAULT_FEED_AUTHOR: any = {
  name: null,
  url: null,
  avatar: null
};

function decodeHTML(html: string) {
  if (!html || typeof html !== 'string') return '';
  var txt = document.createElement('textarea');
  txt.innerHTML = html;
  return txt.value;
}

export function parseFeedAttachments(attachments: any): FeedAttachment[] {
  return attachments && Array.isArray(attachments)
    ? attachments
        .map(attachment =>
          attachment && typeof attachment === 'object' ? { ...DEFAULT_FEED_ATTACHMENT, ...attachment } : null
        )
        .filter(attachment => attachment)
    : [];
}

export function parseFeedAuthors(authors: any): FeedAuthor[] {
  return authors && Array.isArray(authors)
    ? authors
        .map(author => (author && typeof author === 'object' ? { ...DEFAULT_FEED_AUTHOR, ...author } : null))
        .filter(author => author)
    : [];
}

export function parseFeedItems(items: any): FeedItem[] {
  return items && Array.isArray(items)
    ? items
        .map(item =>
          item && typeof item === 'object'
            ? {
                ...DEFAULT_FEED_ITEM,
                ...item,
                date_published: new Date(item.date_published),
                date_modified: new Date(item.date_modified),
                authors: parseFeedAuthors(item?.authors),
                attachments: parseFeedAttachments(item?.attachments),
                content_html: decodeHTML(item?.content_html)
              }
            : null
        )
        .filter(item => item)
    : [];
}

export function parseFeed(feed: any): Feed {
  return feed && typeof feed === 'object'
    ? {
        ...DEFAULT_FEED,
        ...feed,
        items: parseFeedItems(feed?.items),
        authors: parseFeedAuthors(feed?.authors)
      }
    : null;
}
