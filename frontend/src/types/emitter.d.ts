import type { Rom } from "@/stores/roms";
import type { User } from "@/stores/users";

export interface UserItem extends User {
  password: string;
  avatar: File | null;
}

export type SnackbarStatus = {
  msg: string;
  timeout?: number;
  icon?: string;
  color?: string;
};

export type Events = {
  showSearchRomDialog: Rom;
  showEditRomDialog: Rom;
  showDeleteRomDialog: Rom;
  showUploadRomDialog: Rom;
  showCreateExclusionDialog: any;
  showCreatePlatformBindingDialog: any;
  showCreateUserDialog: null;
  showEditUserDialog: UserItem;
  showDeleteUserDialog: UserItem;
  toggleDrawer: any;
  toggleDrawerRail: any;
  snackbarShow: SnackbarStatus;
  refreshDrawer: any;
  showLoadingDialog: {
    loading: boolean;
    scrim: boolean;
  };
  openFabMenu: any;
  filter: null;
};
