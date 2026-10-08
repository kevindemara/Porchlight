import type { components } from './api-schema'

export type Session = components['schemas']['SessionView']
export type Settings = components['schemas']['AppSettings']
export type Health = components['schemas']['Health']
export type OwnerEntity = components['schemas']['OwnerEntity']
export type Event = components['schemas']['EventView']
export type EventList = components['schemas']['EventList']
export type Models = components['schemas']['ModelList']
export type AiResources = components['schemas']['AiResources']
export type ModelTest = components['schemas']['ModelTestResult']
export type Setup = components['schemas']['SetupState']
export type BlinkStatus = components['schemas']['BlinkStatus']
export type CameraList = components['schemas']['CameraList']
export type CameraCommand = components['schemas']['CameraCommandView']
export type RecordingSync = components['schemas']['RecordingSync']
export type LocalRecordingStatus = components['schemas']['LocalRecordingStatus']
export type AnalysisStatus = components['schemas']['AnalysisStatus']
export type AnalysisView = components['schemas']['AnalysisView']
export type AnalysisJob = components['schemas']['AnalysisJobView']
export type LiveSession = components['schemas']['LiveSession']
export type Capture = components['schemas']['CaptureView']
export type CaptureList = components['schemas']['CaptureList']
export type SearchPreview = components['schemas']['SearchPreview']
export type EventFilters = components['schemas']['EventFilters']
export type DailyDigest = components['schemas']['DailyDigest']
export type InboxView = components['schemas']['InboxView']
export type RuleView = components['schemas']['RuleView']
export type RetentionPreview = components['schemas']['RetentionPreview']
export type RetentionResult = components['schemas']['RetentionResult']
export type SavedView = components['schemas']['SavedViewResult']
export type PushStatus = components['schemas']['PushStatus']
export type FaceStatus = components['schemas']['FaceStatus']
export type FaceResult = components['schemas']['FaceResult']
export type FaceCandidate = components['schemas']['FaceCandidate']
export type FaceCandidates = components['schemas']['FaceCandidates']
export type FaceGallery = components['schemas']['FaceGallery']
export type FaceApprovalResult = components['schemas']['FaceApprovalResult']
export type FaceGroup = components['schemas']['FaceGroup']
export type FaceRescan = components['schemas']['FaceRescan']
export type PersonProfile = components['schemas']['PersonProfile']
export type PersonProfiles = components['schemas']['PersonProfiles']

export function analysisLabel(status: string) {
  return ({ queued: 'Analysis queued', analyzing: 'Analyzing', analyzed: 'AI description', analysis_failed: 'Analysis failed' } as Record<string, string>)[status] ?? 'Not analyzed'
}

export function sourceLabel(event: Event) {
  return event.source_type === 'blink_cloud' ? 'Blink cloud' : event.source_type === 'blink_local' ? 'Sync Module' : 'Manual import'
}

let csrfToken = ''
export function setSession(session: Session | null) { csrfToken = session?.csrf_token ?? '' }

export class ApiError extends Error {
  constructor(public status: number, message: string, public code?: string) { super(message) }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body && typeof options.body === 'string') headers.set('Content-Type', 'application/json')
  if (options.method && options.method !== 'GET') headers.set('X-CSRF-Token', csrfToken)
  let response: Response
  try {
    response = await fetch(`/api/v1${path}`, { ...options, headers, credentials: 'same-origin' })
  } catch {
    throw new ApiError(0, 'Porchlight is unreachable. Check that the local app is running.')
  }
  if (!response.ok) {
    const error = await response.json().catch(() => ({})) as { message?: string; code?: string }
    throw new ApiError(response.status, error.message ?? 'The request could not be completed.', error.code)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export function message(error: unknown): string {
  return error instanceof Error ? error.message : 'The request could not be completed.'
}
