declare module "*.vue" {
  import { defineComponent } from "vue";
  const Component: ReturnType<typeof defineComponent>;
  export default Component;
}

declare global {
	interface Window {
        EJS_player: string;
        EJS_pathtodata: string;
        EJS_color: string;
        EJS_defaultOptions: object;
        EJS_gameID: number;
        EJS_gameName: string;
        EJS_backgroundImage: string;
        EJS_gameUrl: string;
        EJS_loadStateURL: string;
        EJS_cheats: string;
        EJS_gamePatchUrl: string;
        EJS_netplayServer: string;
        EJS_onGameStart: () => void;
        EJS_onSaveState: (args: { screenshot: File, state: File}) => void;
        EJS_onLoadState: () => void;
    }
}
