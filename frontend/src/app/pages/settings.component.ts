import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';

import { ApiService } from '../services/api.service';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [CommonModule],
  template: `
    <section class="page-header">
      <div>
        <h1>Settings</h1>
        <p>Runtime paths and local capability checks.</p>
      </div>
      <button type="button" (click)="load()">Refresh</button>
    </section>

    <section class="split">
      <div class="panel">
        <h2>Application</h2>
        <dl>
          <div *ngFor="let item of settingItems">
            <dt>{{ item.key }}</dt>
            <dd>{{ item.value }}</dd>
          </div>
        </dl>
      </div>

      <div class="panel">
        <h2>GPU</h2>
        <dl>
          <div *ngFor="let item of gpuItems">
            <dt>{{ item.key }}</dt>
            <dd>{{ item.value }}</dd>
          </div>
        </dl>
      </div>
    </section>
  `
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

