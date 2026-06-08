import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';

import { ApiService } from '../services/api.service';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './settings.component.html',
  styleUrls: ['./settings.component.css']
})
export class SettingsComponent implements OnInit {
  settings: Record<string, unknown> = {};
  health: Record<string, unknown> = {};

  constructor(private api: ApiService) {}

  get settingItems(): Array<{ key: string; value: unknown }> {
    return Object.entries(this.settings).map(([key, value]) => ({ key, value }));
  }

  get gpuItems(): Array<{ key: string; value: unknown }> {
    const gpu = (this.health['gpu'] as Record<string, unknown>) || {};
    return Object.entries(gpu).map(([key, value]) => ({ key, value }));
  }

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.api.settings().subscribe((settings) => (this.settings = settings));
    this.api.health().subscribe((health) => (this.health = health));
  }
}
