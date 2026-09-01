export type PreviewEnvironment = {
  dev: boolean;
  enabled?: string;
};

export function isAiPlatformPreviewAvailable(environment: PreviewEnvironment): boolean {
  return environment.dev && environment.enabled?.trim().toLowerCase() === 'true';
}

export const AI_PLATFORM_PREVIEW_AVAILABLE = isAiPlatformPreviewAvailable({
  dev: import.meta.env.DEV,
  enabled: import.meta.env.VITE_AI_PLATFORM_PREVIEW_ENABLED,
});
