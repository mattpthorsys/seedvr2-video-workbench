import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import { ApiService, BrowseResponse, BrowseItem, BrowseRoot, InputFile, ModelDownloadStatus, ModelStatus, ModelTestResult, VideoMetadata } from '../services/api.service';

@Component({
  selector: 'app-new-job',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './new-job.component.html',
  styleUrls: ['./new-job.component.css']
})
export class NewJobComponent implements OnInit, OnDestroy {
  inputFiles: InputFile[] = [];
  metadata?: VideoMetadata;
  modelStatus?: ModelStatus;
  modelTest?: ModelTestResult;
  modelDownloads: ModelDownloadStatus[] = [];
  uploadMessage = '';
  probeMessage = '';
  modelTestRunning = false;
  private downloadPoll?: ReturnType<typeof setInterval>;

  showBrowseModal = false;
  browseTarget: 'source' | 'destination' = 'source';
  browseRoots: BrowseRoot[] = [];
  currentRootId = '0';
  currentBrowsePath = '';
  browseData?: BrowseResponse;
  browseSearchQuery = '';
  newFilename = '';

  readonly acceptedVideoTypes = [
    '.3g2', '.3gp', '.asf', '.avi', '.divx', '.dv', '.f4v', '.flv',
    '.m2ts', '.m2v', '.m4v', '.mkv', '.mov', '.mp4', '.mpeg', '.mpg',
    '.mts', '.mxf', '.ogm', '.ogv', '.rm', '.rmvb', '.ts', '.vob',
    '.webm', '.wmv'
  ].join(',');

  presets = ['Progressive', 'Interlaced video', 'Telecined/DVD', 'PAL DVD/TV', 'Heavy compression', 'Soft low-resolution source', 'Custom'];
  
  form = {
    input_path: '',
    output_path: '',
    preset: 'Progressive',
    target: { mode: '1080p', width: undefined as number | undefined, height: undefined as number | undefined },
    preprocessing: { deinterlace: 'none', inverse_telecine: 'off', denoise: 'off', deblock: 'off' },
    seedvr2: {
      model: '3B',
      custom_model_path: null as string | null,
      precision: 'auto',
      batch_size: 5,
      temporal_overlap: 2,
      vae_tiling: true,
      blockswap: false,
      colour_correction: true
    },
    encode: { codec: 'h265', hardware: 'auto', container: 'mkv', quality: 20, preset: 'medium', copy_audio: true, audio_mode: 'copy', audio_bitrate: '192k' }
  };

  constructor(private api: ApiService, private router: Router) {}

  ngOnInit(): void {
    this.loadInputs();
    this.loadModelStatus();
    this.loadBrowseRoots();
    this.loadModelDownloads();
    this.downloadPoll = setInterval(() => this.loadModelDownloads(), 4000);
  }

  ngOnDestroy(): void {
    if (this.downloadPoll) {
      clearInterval(this.downloadPoll);
    }
  }

  get selectedInput(): InputFile | undefined {
    return this.inputFiles.find((file) => file.relative_path === this.form.input_path);
  }

  get gpuName(): string {
    const gpu = this.modelStatus?.gpu || {};
    return (gpu['name'] as string) || 'GPU not visible yet';
  }

  get canSubmit(): boolean {
    return !!this.form.input_path;
  }

  get filteredFolders(): BrowseItem[] {
    if (!this.browseData?.folders) return [];
    return this.browseData.folders.filter(f => f.name.toLowerCase().includes(this.browseSearchQuery.toLowerCase()));
  }

  get filteredFiles(): BrowseItem[] {
    if (!this.browseData?.files) return [];
    return this.browseData.files.filter(f => {
      const matchSearch = f.name.toLowerCase().includes(this.browseSearchQuery.toLowerCase());
      if (this.browseTarget === 'source') {
        return matchSearch && !!f.is_video;
      }
      return matchSearch;
    });
  }

  get browseCrumbs(): Array<{ label: string; path: string }> {
    if (!this.currentBrowsePath) {
      return [];
    }
    const parts = this.currentBrowsePath.split('/').filter(Boolean);
    return parts.map((part, index) => ({
      label: part,
      path: parts.slice(0, index + 1).join('/')
    }));
  }

  loadInputs(): void {
    this.api.inputFiles().subscribe((files) => (this.inputFiles = files));
  }

  loadModelStatus(): void {
    this.api.models().subscribe((status) => (this.modelStatus = status));
  }

  loadModelDownloads(): void {
    this.api.modelDownloads().subscribe((response) => (this.modelDownloads = response.downloads));
  }

  downloadFor(model: string): ModelDownloadStatus | undefined {
    return this.modelDownloads.find((download) => download.model === model);
  }

  downloadPercent(download: ModelDownloadStatus | undefined): number {
    if (!download?.estimated_bytes) {
      return 0;
    }
    return Math.min(100, Math.round((download.bytes_downloaded / download.estimated_bytes) * 100));
  }

  isDownloading(model: string): boolean {
    const status = this.downloadFor(model)?.status;
    return status === 'queued' || status === 'running';
  }

  startModelDownload(model: string): void {
    this.api.startModelDownload(model).subscribe({
      next: () => {
        this.loadModelDownloads();
        this.loadModelStatus();
      },
      error: () => this.loadModelDownloads()
    });
  }

  loadBrowseRoots(): void {
    this.api.browseRoots().subscribe((roots) => {
      this.browseRoots = roots;
      this.currentRootId = roots.find((root) => root.exists)?.id || roots[0]?.id || '0';
    });
  }

  uploadSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) {
      return;
    }
    this.uploadMessage = `Uploading ${file.name}...`;
    this.api.uploadInput(file).subscribe({
      next: (saved) => {
        this.uploadMessage = `Ready: ${saved.relative_path}`;
        this.form.input_path = saved.relative_path;
        this.metadata = undefined;
        this.loadInputs();
        this.probe();
        this.updateDefaultOutputPath(saved.relative_path);
      },
      error: (error) => {
        this.uploadMessage = error?.error?.detail || 'Upload failed.';
      }
    });
  }

  probe(): void {
    if (!this.form.input_path) {
      return;
    }
    this.probeMessage = 'Preparing source metadata...';
    this.api.probe(this.form.input_path).subscribe({
      next: (metadata) => {
        this.metadata = metadata;
        this.probeMessage = 'Source is probed and ready for conversion.';
      },
      error: (error) => {
        this.probeMessage = error?.error?.detail || 'Probe failed.';
      }
    });
  }

  testModel(runInference = false): void {
    this.modelTestRunning = true;
    this.modelTest = undefined;
    this.api
      .testModel({
        model: this.form.seedvr2.model,
        custom_model_path: this.form.seedvr2.custom_model_path,
        precision: this.form.seedvr2.precision,
        batch_size: 1,
        temporal_overlap: 0,
        run_inference: runInference,
        timeout_seconds: 300
      })
      .subscribe({
        next: (result) => {
          this.modelTest = result;
          this.modelTestRunning = false;
          this.loadModelStatus();
        },
        error: (error) => {
          this.modelTest = {
            ok: false,
            status: 'request_failed',
            message: error?.error?.detail || 'Model test failed.',
            gpu: {},
            model: {},
            inference_ran: false,
            log_path: ''
          };
          this.modelTestRunning = false;
        }
      });
  }

  submit(): void {
    const payload = { ...this.form, source_metadata: this.metadata };
    this.api.createJob(payload).subscribe((job) => this.router.navigate(['/jobs', job.id]));
  }

  openBrowse(target: 'source' | 'destination'): void {
    this.browseTarget = target;
    this.showBrowseModal = true;
    this.browseSearchQuery = '';

    const dataRoot = this.browseRoots.find((root) => root.label === 'Data' && root.exists) || this.browseRoots.find((root) => root.exists) || this.browseRoots[0];
    this.currentRootId = dataRoot?.id || '0';
    let defaultStart = '';
    if (target === 'source') {
      defaultStart = 'input';
    } else {
      defaultStart = 'output';
      if (this.form.input_path) {
        const base = this.form.input_path.split('/').pop() || 'video.mp4';
        const dotIndex = base.lastIndexOf('.');
        const stem = dotIndex !== -1 ? base.substring(0, dotIndex) : base;
        this.newFilename = `${stem}_restored`;
      } else {
        this.newFilename = 'restored_video';
      }
    }
    this.loadBrowsePath(defaultStart, this.currentRootId);
  }

  loadBrowsePath(path: string, rootId = this.currentRootId): void {
    this.currentRootId = rootId;
    this.currentBrowsePath = path;
    this.api.browseFiles(rootId, path).subscribe({
      next: (resp) => {
        this.browseData = resp;
        this.currentRootId = resp.root_id;
        this.currentBrowsePath = resp.current_path;
      },
      error: () => {
        if (path !== '') {
          this.loadBrowsePath('');
        }
      }
    });
  }

  navigateBrowse(dirPath: string): void {
    this.loadBrowsePath(dirPath);
  }

  selectFile(item: BrowseItem): void {
    if (this.browseTarget !== 'source') {
      return;
    }
    this.form.input_path = item.select_path;
    this.showBrowseModal = false;
    this.metadata = undefined;
    this.probe();
    this.updateDefaultOutputPath(item.select_path);
  }

  confirmDestinationBrowse(): void {
    if (this.browseTarget === 'destination') {
      const ext = this.form.encode.container || 'mkv';
      const selectedDir = this.browseData?.current_select_path || this.currentBrowsePath || 'output';
      const separator = selectedDir.endsWith('/') || selectedDir.endsWith('\\') ? '' : '/';
      this.form.output_path = `${selectedDir}${separator}${this.newFilename}.${ext}`;
      this.showBrowseModal = false;
    }
  }

  updateDefaultOutputPath(inputPath: string): void {
    const base = inputPath.split('/').pop() || 'video.mp4';
    const dotIndex = base.lastIndexOf('.');
    const stem = dotIndex !== -1 ? base.substring(0, dotIndex) : base;
    const ext = this.form.encode.container || 'mkv';
    this.form.output_path = `output/${stem}_restored.${ext}`;
  }
}
