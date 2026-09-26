/**
 * Friendly aliases over the types generated from the backend OpenAPI schema
 * (`npm run gen:api` → schema.d.ts). Enums stay in sync with the backend.
 */
import type { components } from './schema';

type S = components['schemas'];

export type Priority = S['PriorityEnum'];
export type Category = S['CategoryEnum'];
export type AnalysisStatus = S['AnalysisStatusEnum'];
export type AnalysisSummary = S['AnalysisSummary'];
export type InboxItem = S['InboxItem'];
export type InboxPage = S['InboxPage'];
export type EmailDetail = S['EmailDetail'];
export type ThreadDetail = S['Thread'];
export type ThreadMessage = S['ThreadMessage'];
export type Attachment = S['Attachment'];
export type Recipient = S['Recipient'];

export const PRIORITIES: Priority[] = ['CRITICAL', 'HIGH', 'NORMAL', 'LOW'];
export const CATEGORIES: Category[] = [
  'WORK', 'PERSONAL', 'FINANCE', 'CUSTOMER', 'SALES', 'MARKETING', 'SOCIAL',
  'NOTIFICATION', 'TRANSACTION', 'SUPPORT', 'NEWSLETTER', 'OTHER',
];

export type DashboardSummary = S['DashboardSummary'];
export type NeedsAttention = S['NeedsAttention'];
export type AttentionItem = S['AttentionItem'];
