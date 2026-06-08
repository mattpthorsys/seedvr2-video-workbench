import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ApiService, Job } from '../services/api.service';

@Component({
  selector: 'app-logs',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './logs.component.html',
  styleUrls: ['./logs.component.css']
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
