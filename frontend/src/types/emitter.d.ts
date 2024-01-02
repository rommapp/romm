export type SnackbarStatus = {
  msg: string;
  timeout?: number;
  icon?: string;
  color?: string;
};

export type Events = {
  showSearchRomDialog: any;
  showEditRomDialog: any;
  showDeleteRomDialog: any;
  showUploadRomDialog: any;
  showCreateExclusionDialog: any;
  showCreatePlatformBindingDialog: any;
  showCreateUserDialog: any;
  showEditUserDialog: any;
  showDeleteUserDialog: any;
  toggleDrawer: any;
  toggleDrawerRail: any;
  snackbarShow: SnackbarStatus;
  refreshDrawer: any;
  showLoadingDialog: any;
  openFabMenu: any;
  filter: null;
};
