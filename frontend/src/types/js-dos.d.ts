export interface JsDosOptions {
  url: string;
  backend: "dosbox" | "dosboxX";
  backendLocked: boolean;
  pathPrefix: string;
  autoStart: boolean;
  autoSave: boolean;
  fullScreen: boolean;
  fsChanges: {
    local?: boolean;
    urlToKey?: (url: string) => Promise<string>;
    /** Supplies the saved changes in place of browser storage. */
    pull?: (key: string) => Promise<Uint8Array | null>;
    /** Receives the changes on each save in place of browser storage; a throw fails the save. */
    push?: (key: string, changes: Uint8Array) => Promise<void>;
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
