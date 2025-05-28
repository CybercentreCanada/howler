import type PhraseConsumer from '../PhraseConsumer';
import PhraseLexer from '../PhraseLexer';
import WhitespaceConsumer from './consumers/WhitespaceConsumer';
import WordConsumer from './consumers/WordConsumer';

export default class WordLexer extends PhraseLexer {
  public consumers(): PhraseConsumer<PhraseLexer>[] {
    return [new WordConsumer(), new WhitespaceConsumer()];
  }
}
