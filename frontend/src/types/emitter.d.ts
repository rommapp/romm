import type { SaveSchema, StateSchema } from "@/__generated__";
import type { Collection } from "@/stores/collections";
import type { Platform } from "@/stores/platforms";
import type { SimpleRom } from "@/stores/roms";
import type { User } from "@/stores/users";

export type SnackbarStatus = {
  id?: number;
  msg: string;
  timeout?: number;
  icon?: string;
  color?: string;
};

export type Events = {
  showDeletePlatformDialog: Platform;
  showCreateCollectionDialog: null;
  showAddToCollectionDialog: SimpleRom[];
  showRemoveFromCollectionDialog: SimpleRom[];
  showDeleteCollectionDialog: Collection;
  showMatchRomDialog: SimpleRom;
  showSearchCoverDialog: { term: string; aspectRatio: number | null };
  updateUrlCover: string;
  showSearchRomDialog: null;
  showEditRomDialog: SimpleRom;
  showCopyDownloadLinkDialog: string;
  showDeleteRomDialog: SimpleRom[];
  showUploadRomDialog: Platform | null;
  showDeleteFirmwareDialog: FirmwareSchema[];
  addFirmwareDialog: null;
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
  showCreateExclusionDialog: {
    type: string;
    icon: string;
    title: string;
  };
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
  addStatesDialog: DetailedRom;
  addSavesDialog: DetailedRom;
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
  firmwareDrawerShow: null;
  updateDataTablePages: null;
  sortBarShow: null;
  romUpdated: DetailedRom;
  showQRCodeDialog: SimpleRom;
};
