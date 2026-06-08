import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import { ApiService, InputFile, VideoMetadata } from '../services/api.service';

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
  presets = ['Progressive', 'Interlaced video', 'Telecined/DVD', 'PAL DVD/TV', 'Heavy compression', 'Soft low-resolution source', 'Custom'];
  form = {
    input_path: '',
    preset: 'Progressive',
    target: { mode: '1080p', width: undefined as number | undefined, height: undefined as number | undefined },
    preprocessing: { deinterlace: 'none', inverse_telecine: 'off', denoise: 'off', deblock: 'off' },
    seedvr2: {
      model: '3B',
      custom_model_path: null,
      precision: 'auto',
      batch_size: 5,
      temporal_overlap: 2,
      vae_tiling: true,
      blockswap: false,
      colour_correction: true
    },
    encode: { codec: 'h265', hardware: 'nvenc', quality: 20, preset: 'medium', copy_audio: true }
  };

  constructor(private api: ApiService, private router: Router) {}

  ngOnInit(): void {
    this.loadInputs();
  }

  loadInputs(): void {
    this.api.inputFiles().subscribe((files) => (this.inputFiles = files));
  }

  probe(): void {
    this.api.probe(this.form.input_path).subscribe((metadata) => (this.metadata = metadata));
  }

  submit(): void {
    const payload = { ...this.form, source_metadata: this.metadata };
    this.api.createJob(payload).subscribe((job) => this.router.navigate(['/jobs', job.id]));
  }
}
