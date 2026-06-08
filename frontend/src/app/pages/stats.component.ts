import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';

import { ApiService } from '../services/api.service';

@Component({
  selector: 'app-stats',
  standalone: true,
  imports: [CommonModule],
  template: `
    <section class="page-header">
      <div>
        <h1>Stats</h1>
        <p>ETA history, throughput profiles, and completed job accuracy.</p>
      </div>
      <button type="button" (click)="load()">Refresh</button>
    </section>

    <section class="split">
      <div class="panel">
        <h2>Throughput By Stage</h2>
        <table>
          <thead>
            <tr><th>Stage</th><th>Samples</th><th>Average FPS</th></tr>
          </thead>
          <tbody>
            <tr *ngFor="let row of stageRows">
              <td>{{ row['stage_name'] }}</td>
              <td>{{ row['sample_count'] }}</td>
              <td>{{ row['average_fps'] | number:'1.2-2' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="panel">
        <h2>ETA Accuracy</h2>
        <table>
          <thead>
            <tr><th>Job</th><th>Initial Error</th><th>Final Error</th><th>Actual</th></tr>
          </thead>
          <tbody>
            <tr *ngFor="let row of etaRows">
              <td>#{{ row['id'] }}</td>
              <td>{{ row['initial_error_percent'] | number:'1.1-1' }}%</td>
              <td>{{ row['final_error_percent'] | number:'1.1-1' }}%</td>
              <td>{{ row['total_elapsed_seconds'] | number:'1.1-1' }}s</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="panel">
      <h2>Performance Profiles</h2>
      <table>
        <thead>
          <tr><th>Stage</th><th>Preset</th><th>Model</th><th>Precision</th><th>Encoder</th><th>Samples</th><th>Mean FPS</th></tr>
        </thead>
        <tbody>
          <tr *ngFor="let profile of profiles">
            <td>{{ profile['stage_name'] }}</td>
            <td>{{ profile['preset'] || '-' }}</td>
            <td>{{ profile['model'] || '-' }}</td>
            <td>{{ profile['precision'] || '-' }}</td>
            <td>{{ profile['encoder'] || '-' }}</td>
            <td>{{ profile['sample_count'] }}</td>
            <td>{{ profile['mean_fps'] | number:'1.2-2' }}</td>
          </tr>
        </tbody>
      </table>
    </section>
  `
})
export class StatsComponent implements OnInit {
  stageRows: any[] = [];
  etaRows: any[] = [];
  profiles: any[] = [];

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.api.stats().subscribe((stats) => {
      this.stageRows = (stats['stage_throughput'] as any[]) || [];
      this.etaRows = (stats['eta_accuracy'] as any[]) || [];
    });
    this.api.performanceProfiles().subscribe((profiles) => (this.profiles = profiles));
  }
}
