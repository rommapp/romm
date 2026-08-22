export interface JsDosOptions {
  url: string;
  backend: "dosbox" | "dosboxX";
  backendLocked: boolean;
  pathPrefix: string;
  autoStart: boolean;
  autoSave: boolean;
  fullScreen: boolean;
  fsChanges: {
    local: boolean;
    urlToKey?: (url: string) => Promise<string>;
    pull?: (key: string) => Promise<Uint8Array | null>;
    push?: (key: string, data: Uint8Array) => Promise<void>;
    delete?: (key: string) => Promise<void>;
  };
}

export interface JsDosProps {
  getLocalChanges(key: string): Promise<Uint8Array | null>;
  setNoCloud(noCloud: boolean): void;
  save(): Promise<boolean>;
  stop(): Promise<void>;
}

export type JsDosFactory = (
  element: HTMLDivElement,
  options: Partial<JsDosOptions>,
) => JsDosProps;

declare global {
  interface Window {
    Dos?: JsDosFactory;
  }
}
