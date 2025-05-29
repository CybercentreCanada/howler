export type PhraseAnalysis = {
  cursor: number;
  parentIndex: number;
  parent: PhraseToken;
  currentIndex: number;
  current: PhraseToken;
  suggest: {
    token: PhraseToken;
    parent: PhraseToken;
    value: string;
  };
  tokens?: PhraseToken[];
};

export type PhraseToken = {
  value: string;
  startIndex: number;
  endIndex: number;
  type?: string;
  children?: PhraseToken[];
};

export type PhraseSuggester = {
  suggest: (phrase: PhraseAnalysis) => string[];
};

export type PhraseSuggestorValue = {
  field: string;
  values: string[];
};

export class PhraseBuffer {
  constructor(type?: string) {
    this.type = type;
  }

  private type: string;

  private startIndex: number = 0;

  private endIndex: number = -1;

  private buffer: string[] = [];

  public init(startIndex: number, buffer?: string[]): PhraseBuffer {
    this.buffer = buffer ? [...buffer] : [];
    this.startIndex = startIndex;
    this.endIndex = startIndex + (buffer ? buffer.length : 0);
    return this;
  }

  public append(value: string): PhraseBuffer {
    this.buffer.push(value);
    this.endIndex += value.length;
    return this;
  }

  public value(): string {
    return this.buffer.join('');
  }

  public start(index?: number): number {
    if (index !== undefined) {
      this.startIndex = index;
    }
    return this.startIndex;
  }

  public end(index?: number): number {
    if (index !== undefined) {
      this.endIndex = index;
    }
    return this.endIndex;
  }

  public token(): PhraseToken {
    return this.endIndex > 0
      ? {
          type: this.type,
          value: this.value(),
          startIndex: this.startIndex,
          endIndex: this.endIndex - 1
        }
      : null;
  }
}
