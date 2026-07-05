import type {
  PermissionGroupSchema,
  SaveSchema,
  StateSchema,
} from "@/__generated__";
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
  /** v1 — opens the legacy AddRoms picker. The v2 equivalent is
   *  `showManageCollectionsDialog`; this entry stays while v1 still
   *  consumes it.
   *  @deprecated v2 → use `showManageCollectionsDialog`. */
  showAddToCollectionDialog: SimpleRom[];
  /** v2 — opens ManageCollectionsDialog with the given selection. */
  showManageCollectionsDialog: SimpleRom[];
  /** v2 — fired by ManageCollectionsDialog when it closes, so the
   *  GameActionBtn that opened it can drop its pinned-hover state. */
  closeManageCollectionsDialog: null;
  showRemoveFromCollectionDialog: SimpleRom[];
  showDeleteCollectionDialog: Collection;
  showDeleteSmartCollectionDialog: SmartCollection;
  showMatchRomDialog: SimpleRom;
  /** v2 — `rom` is optional; when provided, the dialog also fetches
   *  per-provider covers via `/search/roms` so the user can pick the
   *  IGDB / MobyGames / Screenscraper / … artwork without going
   *  through the manual-match flow. Collection-cover edits omit it. */
  showSearchCoverDialog: {
    term: string;
    platformId?: number;
    rom?: SimpleRom;
  };
  updateUrlCover: string;
  showEditRomDialog: SimpleRom;
  showRefreshMetadataDialog: SimpleRom;
  /** v2-only — bulk refresh of multiple ROMs from the SelectionBar.
   * The v2 RefreshMetadataDialog listens to both this and the single
   * event; v1 keeps the single-rom contract. */
  showRefreshMetadataDialogBulk: SimpleRom[];
  showCopyDownloadLinkDialog: string;
  showDeleteRomDialog: SimpleRom[];
  showUploadRomDialog: Platform | null;
  /** v2 — opens the add-physical-game dialog. When a Platform is
   *  provided the platform field is prefilled; null lets the user pick. */
  showAddPhysicalGameDialog: Platform | null;
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
  // v2 permission administration. `null` opens the group form in create mode.
  showGroupFormDialog: PermissionGroupSchema | null;
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
  // The QR dialog only reads SimpleRom fields (name, fs_name, extension)
  // and the NDS/download helpers all accept SimpleRom, so gallery surfaces
  // (which only ever hold SimpleRom) can trigger it too.
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
  showChangelogDialog: null;
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
  // v2 only — generic confirmation dialog. Consumers go through
  // `useConfirm()`; the payload carries an id used to route the result
  // back via the matching `confirmResolved` event.
  showConfirm: {
    id: number;
    title: string;
    body?: string;
    confirmText?: string;
    cancelText?: string;
    tone?: "warning" | "danger";
    requireTyped?: string;
  };
  confirmResolved: { id: number; confirmed: boolean };
};
