import type { PhraseAnalysis, PhraseToken } from '.';
import type PhraseConsumer from './PhraseConsumer';

export default abstract class PhraseLexer {
  private _phrase: string = null;

  private _buffer: string[] = null;

  private _tokens: PhraseToken[] = null;

  private _consumers: PhraseConsumer<PhraseLexer>[] = null;

  private _consumer: PhraseConsumer<PhraseLexer> = null;

  private _startIndex: number = 0;

  private _endIndex: number = -1;

  private find(cursor: number, tokens: PhraseToken[]): { token: PhraseToken; index: number } {
    const index = tokens.findIndex(t => t.startIndex <= cursor && cursor <= t.endIndex);
    const token = tokens.at(index);
    return { index, token };
  }

  public parse(phrase: string, cursor: number = 0): PhraseAnalysis {
    this._phrase = phrase;
    this._buffer = [];
    this._tokens = [];
    this._consumers = this.consumers();
    this._consumer = null;
    this._startIndex = 0;
    this._endIndex = -1;

    for (let i = 0; i < this._phrase.length; i++) {
      this._endIndex += 1;

      const next = this._phrase[i];
      this._buffer.push(next);

      // console.log(this._buffer.join(''));

      // Prevent duplication of next character
      //  when aquiring new consumer lock.
      let newLock = false;

      // Try to find a consumer to lock on.
      if (!this._consumer) {
        this._consumer = this.lock();
        if (this._consumer) {
          newLock = true;
          // console.log('new lock...');
          // console.log(this._consumer);
          this._consumer.init(this._buffer, this);
        }
      }

      // If we have a consumer, write next character into it
      //  and then see if it can consume the buffer.
      if (this._consumer) {
        if (newLock) {
          newLock = false;
        } else {
          this._consumer.append(next, this);
        }

        const token = this._consumer.consume(this);
        if (token) {
          this._tokens.push(token);
          this._buffer = [];
          this._consumer = null;
          this._startIndex = this._endIndex + 1;
        }
      }
    }

    // Always add a EOP (end-of-phrase) token.
    this._tokens.push({ type: 'eop', startIndex: phrase.length, endIndex: phrase.length, value: '' });

    // Flatten token structure.
    // By collapsing all children token, we can find the exact token for the current cursor position.
    const flatTokens = this._tokens.flatMap(t => (t.children && t.children.length > 0 ? t.children : [t]));

    // Find the index of the token within range or cursor.
    const { token: parent, index: parentIndex } = this.find(cursor, this._tokens);
    const { token: current, index: currentIndex } = this.find(cursor, flatTokens);

    // Figure out which token to use to generate suggestions.
    // When at the start of a token, use the previous one.
    // console.log(currentIndex);
    // console.log(flatTokens[currentIndex - 1]);
    const filter =
      cursor === current.startIndex && flatTokens[currentIndex - 1] ? flatTokens[currentIndex - 1] : current;

    return {
      cursor,
      parentIndex,
      parent,
      currentIndex,
      current,
      suggest: {
        token: filter,
        parent: this.find(filter.startIndex, this._tokens).token,
        value: filter.value.substring(0, cursor - filter.startIndex)
      },
      tokens: this._tokens
    };
  }

  public lock(): PhraseConsumer<PhraseLexer> {
    return this._consumers.find(c => c.lock(this));
  }

  public buffer(): string[] {
    return this._buffer;
  }

  public bufferValue(): string {
    return this._buffer.join('');
  }

  public start(): number {
    return this._startIndex;
  }

  public end(): number {
    return this._endIndex;
  }

  public ahead(inc?: number): string {
    const start = this._endIndex + 1;
    if (inc) {
      return this._phrase.slice(start, start + inc);
    }
    return this._phrase.substring(start);
  }

  public behind(inc?: number): string {
    if (inc) {
      return this.bufferValue().slice(-inc);
    }
    return this.bufferValue();
  }

  public behindEndsWithAny(trim: boolean, ...values: string[]): boolean {
    const behind = trim ? this.behind().trimEnd() : this.behind();
    return values.some(v => behind.endsWith(v));
  }

  public testBehind(regex: RegExp): boolean {
    return regex.test(this.behind());
  }

  public aheadStartsWithAny(trim: boolean, ...values: string[]): boolean {
    const ahead = trim ? this.ahead().trimStart() : this.ahead();
    return values.some(v => ahead.startsWith(v));
  }

  public aheadIsEmpty(trim: boolean = false): boolean {
    return trim ? this.ahead().trim().length === 0 : this.ahead().length === 0;
  }

  public testAhead(regex: RegExp): boolean {
    return regex.test(this.ahead());
  }

  abstract consumers(): PhraseConsumer<PhraseLexer>[];
}
