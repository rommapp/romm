export interface JsDosCI {
  config: () => Promise<any>;
  persist: () => Promise<Uint8Array>;
  exit: () => Promise<void>;
}

export type DosEvent =
  | "emu-ready"
  | "ci-ready"
  | "bnd-play"
  | "open-key"
  | "fullscreen-change";

export type InitBundleEntry = Uint8Array;

export interface InitFileEntry {
  path: string;
  contents: Uint8Array;
}

export type InitFsEntry = InitBundleEntry | InitFileEntry;
export type InitFs = InitFsEntry | InitFsEntry[];

export interface JsDosOptions {
  url: string;
  dosboxConf?: string;
  initFs?: InitFs;
  theme?:
    | "light"
    | "dark"
    | "cupcake"
    | "bumblebee"
    | "emerald"
    | "corporate"
    | "synthwave"
    | "retro"
    | "cyberpunk"
    | "valentine"
    | "halloween"
    | "garden"
    | "forest"
    | "aqua"
    | "lofi"
    | "pastel"
    | "fantasy"
    | "wireframe"
    | "black"
    | "luxury"
    | "dracula"
    | "cmyk"
    | "autumn"
    | "business"
    | "acid"
    | "lemonade"
    | "night"
    | "coffee"
    | "winter";
  noSidebar?: boolean;
  autoStart?: boolean;
  fullScreen?: boolean;
  onEvent?: (event: DosEvent, arg?: any) => void;
  onExit?: () => void;
}

export interface DosProps {
  getVersion(): [string, string];
  setFullScreen(fullScreen: boolean): void;
  setAutoStart(autoStart: boolean): void;
  setAutoSave(autoSave: boolean): void;
  save(): Promise<boolean>;
  stop(): Promise<void>;
}

declare global {
  interface Window {
    Dos: (
      element: HTMLDivElement,
      options: Partial<JsDosOptions>,
    ) => DosProps;
  }
}

export {};
