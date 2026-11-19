/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { NotificationChannelMinLevel } from './NotificationChannelMinLevel';
import type { NotificationTopic } from './NotificationTopic';
export type AppriseChannelCreatePayload = {
    min_level?: NotificationChannelMinLevel;
    /**
     * The topics the channel forwards. Null forwards every topic.
     */
    topics?: (Array<NotificationTopic> | null);
    /**
     * The kind of channel.
     */
    type: string;
    /**
     * The name of the channel.
     */
    name: string;
    /**
     * The Apprise service to send through.
     */
    service: string;
    /**
     * The settings of the Apprise service.
     */
    fields: Record<string, (boolean | number | string | Array<string>)>;
};

