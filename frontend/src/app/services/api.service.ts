import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

export interface InputFile {
  name: string;
  path: string;
  relative_path: string;
  size_bytes: number;
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

  probe(inputPath: string): Observable<VideoMetadata> {
    return this.http.post<VideoMetadata>('/api/probe', { input_path: inputPath });
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
}

