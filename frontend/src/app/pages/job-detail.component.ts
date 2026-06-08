import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { interval, Subscription } from 'rxjs';

import { ApiService, Job } from '../services/api.service';

@Component({
  selector: 'app-job-detail',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './job-detail.component.html',
  styleUrls: ['./job-detail.component.css']
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
