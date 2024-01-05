import type { Platform } from "@/stores/platforms";
import type { Rom } from "@/stores/roms";
import type { User } from "@/stores/users";

export type UserItem = User & {
  password: string;
  avatar?: File[];
}

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
  showCreateExclusionDialog: null;
  showCreatePlatformBindingDialog: null;
  showCreateUserDialog: null;
  showEditUserDialog: UserItem;
  showDeleteUserDialog: UserItem;
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
};
