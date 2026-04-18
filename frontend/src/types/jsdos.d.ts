export interface JsDosCI {
  config: () => Promise<any>;
  persist: () => Promise<Uint8Array>;
  exit: () => Promise<void>;
}

export interface JsDosOptions {
  url: string;
  dosboxConf?: string;
  theme?: string;
  noSidebar?: boolean;
  onEvent?: (event: string, ci: JsDosCI) => void;
  onExit?: () => void;
}

declare global {
  interface Window {
    Dos: (element: HTMLElement, options: JsDosOptions) => Promise<void>;
  }
}

export {};
