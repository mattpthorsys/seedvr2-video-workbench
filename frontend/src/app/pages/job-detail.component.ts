import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { interval, Subscription } from 'rxjs';

import { ApiService, Job } from '../services/api.service';

@Component({
  selector: 'app-job-detail',
  standalone: true,
  imports: [CommonModule],
  template: `
    <section class="page-header" *ngIf="job">
      <div>
        <h1>Job #{{ job.id }}</h1>
        <p>{{ job.input_path }}</p>
      </div>
      <button type="button" class="danger" (click)="cancel()" [disabled]="isTerminal">Cancel</button>
    </section>

    <section class="job-layout" *ngIf="job">
      <div class="panel">
        <div class="progress-bar"><span [style.width.%]="job.progress * 100"></span></div>
        <div class="job-facts">
          <div><span>Status</span><strong>{{ job.status }}</strong></div>
          <div><span>Stage</span><strong>{{ job.current_stage || '-' }}</strong></div>
          <div><span>Frames</span><strong>{{ job.frames_processed }} / {{ job.frames_total }}</strong></div>
          <div><span>ETA</span><strong>{{ job.estimated_total_seconds_final || job.estimated_total_seconds_initial | number:'1.0-0' }}s</strong></div>
        </div>
        <h2>Stages</h2>
        <table>
          <thead>
            <tr>
              <th>Stage</th>
              <th>Status</th>
              <th>Frames</th>
              <th>FPS</th>
              <th>Elapsed</th>
            </tr>
          </thead>
          <tbody>
            <tr *ngFor="let stage of job.stages">
              <td>{{ stage.stage_name }}</td>
              <td><span class="status" [ngClass]="stage.status">{{ stage.status }}</span></td>
              <td>{{ stage.frames_processed || 0 }} / {{ stage.frames_total || 0 }}</td>
              <td>{{ stage.effective_fps | number:'1.2-2' }}</td>
              <td>{{ stage.elapsed_seconds | number:'1.1-1' }}s</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="panel">
        <div class="panel-title">
          <h2>Live Logs</h2>
          <button type="button" (click)="load()">Refresh</button>
        </div>
        <pre class="log-output">{{ logText }}</pre>
      </div>
    </section>
  `
})
export class JobDetailComponent implements OnInit, OnDestroy {
  job?: Job;
  logText = '';
  private timer?: Subscription;

  constructor(private api: ApiService, private route: ActivatedRoute) {}

  get isTerminal(): boolean {
    return !!this.job && ['complete', 'failed', 'cancelled'].includes(this.job.status);
  }

  ngOnInit(): void {
    this.load();
    this.timer = interval(2500).subscribe(() => this.load());
  }

  ngOnDestroy(): void {
    this.timer?.unsubscribe();
  }

  load(): void {
    const id = Number(this.route.snapshot.paramMap.get('id'));
    this.api.job(id).subscribe((job) => (this.job = job));
    this.api.logs(id).subscribe((logs) => (this.logText = logs.text));
  }

  cancel(): void {
    if (!this.job) {
      return;
    }
    this.api.cancelJob(this.job.id).subscribe((job) => (this.job = job));
  }
}
