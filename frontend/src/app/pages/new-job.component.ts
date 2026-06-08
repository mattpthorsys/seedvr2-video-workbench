import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import { ApiService, InputFile, ModelStatus, ModelTestResult, VideoMetadata } from '../services/api.service';

@Component({
  selector: 'app-new-job',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './new-job.component.html',
  styleUrls: ['./new-job.component.css']
})
export class NewJobComponent implements OnInit {
  inputFiles: InputFile[] = [];
  metadata?: VideoMetadata;
  modelStatus?: ModelStatus;
  modelTest?: ModelTestResult;
  uploadMessage = '';
  probeMessage = '';
  modelTestRunning = false;
  readonly acceptedVideoTypes = [
    '.3g2',
    '.3gp',
    '.asf',
    '.avi',
    '.divx',
    '.dv',
    '.f4v',
    '.flv',
    '.m2ts',
    '.m2v',
    '.m4v',
    '.mkv',
    '.mov',
    '.mp4',
    '.mpeg',
    '.mpg',
    '.mts',
    '.mxf',
    '.ogm',
    '.ogv',
    '.rm',
    '.rmvb',
    '.ts',
    '.vob',
    '.webm',
    '.wmv'
  ].join(',');
  presets = ['Progressive', 'Interlaced video', 'Telecined/DVD', 'PAL DVD/TV', 'Heavy compression', 'Soft low-resolution source', 'Custom'];
  form = {
    input_path: '',
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

  loadInputs(): void {
    this.api.inputFiles().subscribe((files) => (this.inputFiles = files));
  }

  loadModelStatus(): void {
    this.api.models().subscribe((status) => (this.modelStatus = status));
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
}
