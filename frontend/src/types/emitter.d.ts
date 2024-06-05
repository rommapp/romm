import type { SaveSchema, SearchRomSchema, StateSchema } from "@/__generated__";
import type { Platform } from "@/stores/platforms";
import type { SimpleRom } from "@/stores/roms";
import type { User } from "@/stores/users";
import type internal from "stream";

export type UserItem = User & {
  password: string;
  avatar?: File;
};

export type SnackbarStatus = {
  id?: number;
  msg: string;
  timeout?: number;
  icon?: string;
  color?: string;
};

export type Events = {
  showDeletePlatformDialog: Platform;
  showMatchRomDialog: SimpleRom;
  showSelectSourceDialog: SearchRomSchema;
  showSearchRomDialog: null;
  showEditRomDialog: SimpleRom;
  showCopyDownloadLinkDialog: string;
  showDeleteRomDialog: SimpleRom[];
  showUploadRomDialog: Platform | null;
  showFirmwareDialog: Platform;
  showAddPlatformDialog: null;
  showCreatePlatformBindingDialog: {
    fsSlug: string;
    slug: string;
  };
  showDeletePlatformBindingDialog: {
    fsSlug: string;
    slug: string;
  };
  showCreatePlatformVersionDialog: {
    fsSlug: string;
    slug: string;
  };
  showDeletePlatformVersionDialog: {
    fsSlug: string;
    slug: string;
  };
  showCreateExclusionDialog: { exclude: string };
  showCreateUserDialog: null;
  showEditUserDialog: User;
  showDeleteUserDialog: User;
  showDeleteSavesDialog: {
    rom: DetailedRom;
    saves: SaveSchema[];
  };
  showDeleteStatesDialog: {
    rom: DetailedRom;
    states: StateSchema[];
  };
  showEmulation: null;
  toggleDrawer: null;
  toggleDrawerRail: null;
  snackbarShow: SnackbarStatus;
  refreshDrawer: null;
  refreshView: null;
  showLoadingDialog: {
    loading: boolean;
    scrim: boolean;
  };
  openFabMenu: boolean;
  filter: null;
  filterDrawerShow: null;
  updateDataTablePages: null;
  sortBarShow: null;
  romUpdated: DetailedRom;
};
