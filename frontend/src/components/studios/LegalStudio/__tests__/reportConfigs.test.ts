import { describe, it, expect } from 'vitest';
import { REPORT_CONFIGS } from '../reportConfigs';

describe('reportConfigs', () => {
  it('all entries have type, label, icon', () => {
    for (const key of Object.keys(REPORT_CONFIGS)) {
      const c = REPORT_CONFIGS[key];
      expect(c.type, `${key}.type`).toBeTruthy();
      expect(c.label, `${key}.label`).toBeTruthy();
      expect(c.icon, `${key}.icon`).toBeTruthy();
    }
  });

  it('mis config has sections with kpi_cards and chart types', () => {
    const mis = REPORT_CONFIGS['mis'];
    expect(mis.sections).toBeDefined();
    const types = mis.sections!.map(s => s.type);
    expect(types).toContain('kpi_cards');
    expect(types).toContain('chart');
    expect(mis.chartTypes).toContain('bar');
    expect(mis.detectFields).toContain('entity_name');
  });

  it('audit config has supportedFormats including big4', () => {
    expect(REPORT_CONFIGS['audit'].supportedFormats).toContain('big4');
  });

  it('vat config has regulatoryNote mentioning VAT-201', () => {
    expect(REPORT_CONFIGS['vat'].regulatoryNote).toMatch(/VAT-201/i);
  });

  it('corporate_tax config has detectFields including period_end', () => {
    expect(REPORT_CONFIGS['corporate_tax'].detectFields).toContain('period_end');
  });
});
