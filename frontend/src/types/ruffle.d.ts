/* eslint-disable @typescript-eslint/no-explicit-any */

interface LegacyRuffleAPI {
  onFSCommand: ((command: string, args: string) => void) | null;
  config: any;
  readonly loadedConfig: any;
  get readyState(): ReadyState;
  get metadata(): any;
  reload(): Promise<void>;
  load(options: string | any): Promise<void>;
  play(): void;
  get isPlaying(): boolean;
  get volume(): number;
  set volume(value: number);
  get fullscreenEnabled(): boolean;
  get isFullscreen(): boolean;
  setFullscreen(isFull: boolean): void;
  enterFullscreen(): void;
  exitFullscreen(): void;
  pause(): void;
  set traceObserver(observer: ((message: string) => void) | null);
  downloadSwf(): Promise<void>;
  displayMessage(message: string): void;
}

interface RufflePlayerElement extends HTMLElement, LegacyRuffleAPI {
  ruffle(version?: number): any;
}

export interface RuffleSourceAPI {
  version: string;
  polyfill(): void;
  pluginPolyfill(): void;
  createPlayer(): RufflePlayerElement;
}
