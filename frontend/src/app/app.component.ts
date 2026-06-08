import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <div class="shell">
      <aside class="sidebar">
        <div class="brand">
          <span class="brand-mark">SV</span>
          <div>
            <strong>SeedVR2</strong>
            <small>Video Workbench</small>
          </div>
        </div>
        <nav>
          <a routerLink="/" routerLinkActive="active" [routerLinkActiveOptions]="{ exact: true }">Dashboard</a>
          <a routerLink="/jobs/new" routerLinkActive="active">New Job</a>
          <a routerLink="/logs" routerLinkActive="active">Logs</a>
          <a routerLink="/stats" routerLinkActive="active">Stats</a>
          <a routerLink="/settings" routerLinkActive="active">Settings</a>
        </nav>
      </aside>
      <main>
        <router-outlet></router-outlet>
      </main>
    </div>
  `
})
export class AppComponent {}

