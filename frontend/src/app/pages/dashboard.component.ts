import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';

import { ApiService, InputFile, Job } from '../services/api.service';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <section class="page-header">
      <div>
        <h1>Dashboard</h1>
        <p>Local queue, inputs, and recent restoration jobs.</p>
      </div>
      <a class="primary-action" routerLink="/jobs/new">New Job</a>
    </section>

    <section class="metrics">
      <div>
        <span>{{ jobs.length }}</span>
        <label>Total jobs</label>
      </div>
      <div>
        <span>{{ runningJobs }}</span>
        <label>Running</label>
      </div>
      <div>
        <span>{{ completeJobs }}</span>
        <label>Complete</label>
      </div>
      <div>
        <span>{{ inputFiles.length }}</span>
        <label>Input files</label>
      </div>
    </section>

    <section class="split">
      <div class="panel">
        <div class="panel-title">
          <h2>Recent Jobs</h2>
          <button type="button" (click)="load()">Refresh</button>
        </div>
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Input</th>
              <th>Status</th>
              <th>Stage</th>
              <th>Progress</th>
            </tr>
          </thead>
          <tbody>
            <tr *ngFor="let job of jobs">
              <td><a [routerLink]="['/jobs', job.id]">#{{ job.id }}</a></td>
              <td>{{ job.input_path }}</td>
              <td><span class="status" [ngClass]="job.status">{{ job.status }}</span></td>
              <td>{{ job.current_stage || '-' }}</td>
              <td>{{ job.progress | percent:'1.0-0' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="panel">
        <div class="panel-title">
          <h2>Input Folder</h2>
        </div>
        <ul class="file-list">
          <li *ngFor="let file of inputFiles">
            <strong>{{ file.name }}</strong>
            <small>{{ file.size_bytes | number }} bytes</small>
          </li>
        </ul>
      </div>
    </section>
  `
})
export class DashboardComponent implements OnInit {
  jobs: Job[] = [];
  inputFiles: InputFile[] = [];

  constructor(private api: ApiService) {}

  get runningJobs(): number {
    return this.jobs.filter((job) => job.status === 'running').length;
  }

  get completeJobs(): number {
    return this.jobs.filter((job) => job.status === 'complete').length;
  }

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.api.jobs().subscribe((jobs) => (this.jobs = jobs));
    this.api.inputFiles().subscribe((files) => (this.inputFiles = files));
  }
}
