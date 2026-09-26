import type { Tone } from '@/shared/ui/Badge';
import type { Category, Priority } from '@/shared/api/types';

export const PRIORITY_META: Record<Priority, { label: string; tone: Tone }> = {
  CRITICAL: { label: 'Critical', tone: 'red' },
  HIGH: { label: 'High', tone: 'orange' },
  NORMAL: { label: 'Normal', tone: 'slate' },
  LOW: { label: 'Low', tone: 'teal' },
};

export const CATEGORY_META: Record<Category, { label: string; tone: Tone }> = {
  WORK: { label: 'Work', tone: 'indigo' },
  PERSONAL: { label: 'Personal', tone: 'pink' },
  FINANCE: { label: 'Finance', tone: 'green' },
  CUSTOMER: { label: 'Customer', tone: 'violet' },
  SALES: { label: 'Sales', tone: 'blue' },
  MARKETING: { label: 'Marketing', tone: 'amber' },
  SOCIAL: { label: 'Social', tone: 'pink' },
  NOTIFICATION: { label: 'Notification', tone: 'slate' },
  TRANSACTION: { label: 'Transaction', tone: 'teal' },
  SUPPORT: { label: 'Support', tone: 'blue' },
  NEWSLETTER: { label: 'Newsletter', tone: 'amber' },
  OTHER: { label: 'Other', tone: 'slate' },
};
