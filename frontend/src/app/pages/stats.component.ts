import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';

import { ApiService } from '../services/api.service';

@Component({
  selector: 'app-stats',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './stats.component.html',
  styleUrls: ['./stats.component.css']
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
