import { Routes } from '@angular/router';

import { DashboardComponent } from './pages/dashboard.component';
import { JobDetailComponent } from './pages/job-detail.component';
import { LogsComponent } from './pages/logs.component';
import { NewJobComponent } from './pages/new-job.component';
import { SettingsComponent } from './pages/settings.component';
import { StatsComponent } from './pages/stats.component';

export const routes: Routes = [
  { path: '', component: DashboardComponent },
  { path: 'jobs/new', component: NewJobComponent },
  { path: 'jobs/:id', component: JobDetailComponent },
  { path: 'logs', component: LogsComponent },
  { path: 'stats', component: StatsComponent },
  { path: 'settings', component: SettingsComponent },
  { path: '**', redirectTo: '' }
];

