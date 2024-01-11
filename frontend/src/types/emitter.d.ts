import type { Platform } from "@/stores/platforms";
import type { Rom } from "@/stores/roms";
import type { User } from "@/stores/users";
import type { SaveSchema, StateSchema } from "@/__generated__";

export type UserItem = User & {
  password: string;
  avatar?: File[];
};

export type SnackbarStatus = {
  msg: string;
  timeout?: number;
  icon?: string;
  color?: string;
};

export type Events = {
  showDeletePlatformDialog: Platform;
  showSearchRomDialog: Rom;
  showEditRomDialog: Rom;
  showDeleteRomDialog: Rom[];
  showUploadRomDialog: null;
  showCreatePlatformBindingDialog: null;
  showDeletePlatformBindingDialog: string;
  showCreateExclusionDialog: null;
  showCreateUserDialog: null;
  showEditUserDialog: UserItem;
  showDeleteUserDialog: UserItem;
  showDeleteSavesDialog: {
    rom: Rom;
    saves: SaveSchema[];
  };
  showDeleteStatesDialog: {
    rom: Rom;
    states: StateSchema[];
  };
  toggleDrawer: null;
  toggleDrawerRail: null;
  snackbarShow: SnackbarStatus;
  refreshDrawer: null;
  showLoadingDialog: {
    loading: boolean;
    scrim: boolean;
  };
  openFabMenu: boolean;
  filter: null;
  romUpdated: Rom;
};
