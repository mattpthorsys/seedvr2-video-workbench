import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

export interface InputFile {
  name: string;
  path: string;
  relative_path: string;
  size_bytes: number;
}

export interface BrowseItem {
  name: string;
  root_id: string;
  relative_path: string;
  select_path: string;
  size_bytes?: number;
  is_video?: boolean;
}

export interface BrowseRoot {
  id: string;
  label: string;
  path: string;
  exists: boolean;
}

export interface BrowseResponse {
  root_id: string;
  root_label: string;
  root_path: string;
  current_path: string;
  current_select_path: string;
  parent_path: string | null;
  roots: BrowseRoot[];
  folders: BrowseItem[];
  files: BrowseItem[];
}

export interface VideoMetadata {
  filename: string;
  duration_seconds?: number;
  frame_count_estimate?: number;
  width?: number;
  height?: number;
  frame_rate?: number;
  scan_type?: string;
  video_codec?: string;
  audio_streams: Array<{ index: number; codec?: string; channels?: number; language?: string }>;
}

export interface Job {
  id: number;
  input_path: string;
  output_path?: string;
  status: string;
  created_at: string;
  started_at?: string;
  finished_at?: string;
  current_stage?: string;
  frames_total: number;
  frames_processed: number;
  progress: number;
  estimated_total_seconds_initial?: number;
  estimated_total_seconds_final?: number;
  eta_confidence_initial?: string;
  error_message?: string;
  stages?: StageStat[];
}

export interface StageStat {
  id: number;
  stage_name: string;
  status: string;
  elapsed_seconds?: number;
  frames_total?: number;
  frames_processed?: number;
  effective_fps?: number;
}

export interface ModelStatus {
  ok: boolean;
  message: string;
  gpu: Record<string, unknown>;
  cli: { path: string; exists: boolean };
  model_dir: string;
  models: Array<{ name: string; ready: boolean; path: string; file_count: number; model_file_count: number; size_bytes: number }>;
  mock_pipeline: boolean;
}

export interface ModelTestResult {
  ok: boolean;
  status: string;
  message: string;
  gpu: Record<string, unknown>;
  model: Record<string, unknown>;
  prepared_input_path?: string;
  output_path?: string;
  command?: string[];
  inference_ran: boolean;
  log_path: string;
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  constructor(private http: HttpClient) {}

  health(): Observable<Record<string, unknown>> {
    return this.http.get<Record<string, unknown>>('/api/health');
  }

  settings(): Observable<Record<string, unknown>> {
    return this.http.get<Record<string, unknown>>('/api/settings');
  }

  inputFiles(): Observable<InputFile[]> {
    return this.http.get<InputFile[]>('/api/files/input');
  }

  uploadInput(file: File): Observable<InputFile> {
    const body = new FormData();
    body.append('file', file);
    return this.http.post<InputFile>('/api/files/input/upload', body);
  }

  probe(inputPath: string): Observable<VideoMetadata> {
    return this.http.post<VideoMetadata>('/api/probe', { input_path: inputPath });
  }

  models(): Observable<ModelStatus> {
    return this.http.get<ModelStatus>('/api/models');
  }

  testModel(payload: unknown): Observable<ModelTestResult> {
    return this.http.post<ModelTestResult>('/api/models/test', payload);
  }

  jobs(): Observable<Job[]> {
    return this.http.get<Job[]>('/api/jobs');
  }

  createJob(payload: unknown): Observable<Job> {
    return this.http.post<Job>('/api/jobs', payload);
  }

  job(id: number): Observable<Job> {
    return this.http.get<Job>(`/api/jobs/${id}`);
  }

  cancelJob(id: number): Observable<Job> {
    return this.http.post<Job>(`/api/jobs/${id}/cancel`, {});
  }

  logs(id: number): Observable<{ text: string }> {
    return this.http.get<{ text: string }>(`/api/jobs/${id}/logs`);
  }

  eta(id: number): Observable<Record<string, unknown>> {
    return this.http.get<Record<string, unknown>>(`/api/jobs/${id}/eta`);
  }

  stats(): Observable<Record<string, unknown>> {
    return this.http.get<Record<string, unknown>>('/api/stats');
  }

  performanceProfiles(): Observable<Array<Record<string, unknown>>> {
    return this.http.get<Array<Record<string, unknown>>>('/api/stats/performance-profiles');
  }

  browseRoots(): Observable<BrowseRoot[]> {
    return this.http.get<BrowseRoot[]>('/api/files/roots');
  }

  browseFiles(rootId: string, path: string): Observable<BrowseResponse> {
    return this.http.get<BrowseResponse>(`/api/files/browse?root_id=${encodeURIComponent(rootId)}&path=${encodeURIComponent(path)}`);
  }
}
