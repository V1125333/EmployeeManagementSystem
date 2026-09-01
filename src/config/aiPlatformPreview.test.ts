import { describe, expect, it } from 'vitest';
import { isAiPlatformPreviewAvailable } from './aiPlatformPreview';

describe('AI Platform preview environment gate', () => {
  it('requires both development mode and an explicit true flag', () => {
    expect(isAiPlatformPreviewAvailable({ dev: true, enabled: 'true' })).toBe(true);
    expect(isAiPlatformPreviewAvailable({ dev: true, enabled: 'false' })).toBe(false);
    expect(isAiPlatformPreviewAvailable({ dev: false, enabled: 'true' })).toBe(false);
    expect(isAiPlatformPreviewAvailable({ dev: false })).toBe(false);
  });
});
