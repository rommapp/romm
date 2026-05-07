import type { SaveSchema, StateSchema } from "@/__generated__";
import type { ClientTokenSchema } from "@/services/api/client-token";
import type { Collection, SmartCollection } from "@/stores/collections";
import type { Platform } from "@/stores/platforms";
import type { DetailedRom, SimpleRom } from "@/stores/roms";
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
  showCreateSmartCollectionDialog: null;
  showAddToCollectionDialog: SimpleRom[];
  showRemoveFromCollectionDialog: SimpleRom[];
  showDeleteCollectionDialog: Collection;
  showDeleteSmartCollectionDialog: SmartCollection;
  showMatchRomDialog: SimpleRom;
  showSearchCoverDialog: { term: string; platformId?: number };
  updateUrlCover: string;
  showEditRomDialog: SimpleRom;
  showRefreshMetadataDialog: SimpleRom;
  showCopyDownloadLinkDialog: string;
  showDeleteRomDialog: SimpleRom[];
  showUploadRomDialog: Platform | null;
  showDeleteFirmwareDialog: FirmwareSchema[];
  addFirmwareDialog: null;
  showAddPlatformDialog: null;
  showCreateFolderMappingDialog: null | {
    fsSlug: string;
    slug: string;
    type: "alias" | "variant";
  };
  showDeleteFolderMappingDialog: {
    fsSlug: string;
    slug: string;
    type: "alias" | "variant";
  };
  showCreateExclusionDialog: null;
  showCreateUserDialog: null;
  showCreateInviteLinkDialog: void;
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
  filterRoms: null;
  firmwareDrawerShow: null;
  sortBarShow: null;
  showQRCodeDialog: SimpleRom;
  selectSaveDialog: DetailedRom;
  selectStateDialog: DetailedRom;
  saveSelected: SaveSchema;
  openEmulatorJSCacheDialog: null;
  stateSelected: StateSchema;
  showCreateClientTokenDialog: null;
  showRegenerateClientTokenDialog: ClientTokenSchema;
  showDeleteClientTokenDialog: ClientTokenSchema;
  showAboutDialog: null;
  showNoteDialog: SimpleRom;
  showDeleteManualDialog: {
    rom: DetailedRom;
    isPrimary: boolean;
    fileId?: number;
  };
  showManualUploadTargetDialog: {
    rom: DetailedRom;
    files: File[];
  };
  playGame: number;
};
