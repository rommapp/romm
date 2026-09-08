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
  };
}

export interface JsDosProps {
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
