import type { PhraseAnalysis, PhraseSuggester } from '..';

export default class WordSuggestor implements PhraseSuggester {
  constructor(private suggestions: string[]) {}

  public suggest(phrase: PhraseAnalysis): string[] {
    return this.suggestions.filter(s => s.indexOf(phrase.suggest.value) > -1);
  }
}
