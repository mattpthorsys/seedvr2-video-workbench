import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';

import { ApiService, InputFile, Job } from '../services/api.service';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.css']
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
