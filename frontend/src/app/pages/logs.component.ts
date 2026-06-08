import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ApiService, Job } from '../services/api.service';

@Component({
  selector: 'app-logs',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="page-header">
      <div>
        <h1>Logs</h1>
        <p>Command output and worker messages for queued and completed jobs.</p>
      </div>
    </section>
    <section class="panel">
      <label>
        Job
        <select [(ngModel)]="selectedId" name="selectedId" (change)="loadLogs()">
          <option *ngFor="let job of jobs" [ngValue]="job.id">#{{ job.id }} - {{ job.status }} - {{ job.input_path }}</option>
        </select>
      </label>
      <pre class="log-output tall">{{ logText }}</pre>
    </section>
  `
})
export class LogsComponent implements OnInit {
  jobs: Job[] = [];
  selectedId?: number;
  logText = '';

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.api.jobs().subscribe((jobs) => {
      this.jobs = jobs;
      this.selectedId = jobs[0]?.id;
      this.loadLogs();
    });
  }

  loadLogs(): void {
    if (!this.selectedId) {
      this.logText = '';
      return;
    }
    this.api.logs(this.selectedId).subscribe((logs) => (this.logText = logs.text));
  }
}

