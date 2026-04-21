import type { AuditorFormat } from './AuditorFormatGrid';

export function toBackendFormat(format: AuditorFormat): string {
  if (format === 'legal') return 'isa';
  if (format === 'compliance') return 'fta';
  if (format === 'custom') return 'standard';
  return format;
}
