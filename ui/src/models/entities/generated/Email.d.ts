import type { Attachment } from './Attachment';
import type { Bcc } from './Bcc';
import type { Cc } from './Cc';
import type { From } from './From';
import type { Parent } from './Parent';
import type { ReplyTo } from './ReplyTo';
import type { Sender } from './Sender';
import type { To } from './To';

/**
 * NOTE: This is an auto-generated file. Don't edit this manually.
 */
export interface Email {
  attachments?: Attachment[];
  bcc?: Bcc;
  cc?: Cc;
  content_type?: string;
  delivery_timestamp?: string;
  direction?: string;
  from?: From;
  local_id?: string;
  message_id?: string;
  origination_timestamp?: string;
  parent?: Parent;
  reply_to?: ReplyTo;
  sender?: Sender;
  subject?: string;
  to?: To;
  x_mailer?: string;
}
