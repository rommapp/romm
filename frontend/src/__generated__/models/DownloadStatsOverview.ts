/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DownloadSourceStat } from './DownloadSourceStat';
import type { DownloadStatsSummary } from './DownloadStatsSummary';
import type { DownloadTimelinePoint } from './DownloadTimelinePoint';
import type { PlatformDownloadStat } from './PlatformDownloadStat';
import type { TopDownloadedRom } from './TopDownloadedRom';
export type DownloadStatsOverview = {
    summary: DownloadStatsSummary;
    top_roms: Array<TopDownloadedRom>;
    by_platform: Array<PlatformDownloadStat>;
    by_source: Array<DownloadSourceStat>;
    timeline: Array<DownloadTimelinePoint>;
};

