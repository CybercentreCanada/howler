import type { PhraseToken } from '.';
import type PhraseLexer from './PhraseLexer';

export default abstract class PhraseConsumer<L extends PhraseLexer> {
  protected _buffer = [];

  public reset(): void {
    this._buffer = [];
  }

  public init(buffer: string[], _lexer?: L): void {
    this._buffer = [...buffer];
  }

  public append(next: string, _lexer?: L): void {
    this._buffer.push(next);
  }

  public bufferValue(): string {
    return this._buffer.join('');
  }

  public endsWithAny(...values: string[]): boolean {
    const _bufferValue = this.bufferValue();
    return values.some(v => _bufferValue.endsWith(v));
  }

  public test(regex: RegExp): boolean {
    return regex.test(this.bufferValue());
  }

  abstract lock(lexer: L): boolean;

  abstract consume(lexer: L): PhraseToken;
}
