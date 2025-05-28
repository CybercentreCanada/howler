import type { PhraseToken } from '../..';
import PhraseConsumer from '../../PhraseConsumer';
import type PhraseLexer from '../../PhraseLexer';

export default class WhitespaceConsumer extends PhraseConsumer<PhraseLexer> {
  public lock(lexer: PhraseLexer): boolean {
    return lexer.bufferValue().match(/\s/) && lexer.ahead(1) !== ' ';
  }

  public consume(lexer: PhraseLexer): PhraseToken {
    if (lexer.ahead(1) !== ' ') {
      return {
        type: 'whitespace',
        startIndex: lexer.start(),
        endIndex: lexer.end(),
        value: this._buffer.join('')
      };
    }
    return null;
  }
}
