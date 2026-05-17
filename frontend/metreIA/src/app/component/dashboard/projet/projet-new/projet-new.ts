import { Component, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { lastValueFrom } from 'rxjs';
import { Api } from '../../../../shared/sevice/api';

// ─── Représentation locale d'un plan en attente d'upload ─────────────────────
export interface LocalPlanFile {
  file: File;
  name: string;
  description: string;
  previewUrl?: string;
}

@Component({
  selector: 'app-projet-new',
  imports: [CommonModule, FormsModule],
  templateUrl: './projet-new.html',
  styleUrl: './projet-new.scss',
})
export class ProjetNew {

  // ─── Étape courante (1 = infos, 2 = plans) ───────────────────────────────
  public currentStep: 1 | 2 = 1;

  // ─── Step 1 : Informations projet ────────────────────────────────────────
  public projectName = '';
  public projectDescription = '';

  // ─── Step 2 : Plans de bâtiment ──────────────────────────────────────────
  public planFiles: LocalPlanFile[] = [];
  public isDragging = false;

  // ─── État soumission ──────────────────────────────────────────────────────
  public isSubmitting = false;
  public submitProgress = '';
  public errorMessage = '';

  private token = localStorage.getItem('access_token') ?? '';

  constructor(
    private api: Api,
    private router: Router,
    private cdr: ChangeDetectorRef,
  ) {}

  // ─── Navigation entre étapes ──────────────────────────────────────────────

  goToStep(step: 1 | 2): void {
    if (step === 1) { this.currentStep = 1; return; }
    if (this.canProceedStep1()) { this.currentStep = step; }
  }

  nextStep(): void {
    if (this.currentStep === 1 && this.canProceedStep1()) this.currentStep = 2;
  }

  prevStep(): void {
    if (this.currentStep === 2) this.currentStep = 1;
  }

  canProceedStep1(): boolean {
    return this.projectName.trim().length > 0;
  }

  // ─── Step 2 : Gestion des plans de bâtiment ──────────────────────────────

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files) {
      this.addFiles(Array.from(input.files));
      input.value = '';
    }
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.isDragging = true;
  }

  onDragLeave(): void {
    this.isDragging = false;
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    this.isDragging = false;
    if (event.dataTransfer?.files) {
      this.addFiles(Array.from(event.dataTransfer.files));
    }
  }

  private addFiles(files: File[]): void {
    const allowed = ['application/pdf', 'image/png', 'image/jpeg', 'image/jpg', 'image/webp'];
    for (const file of files) {
      if (!allowed.includes(file.type)) continue;
      const previewUrl = file.type.startsWith('image/') ? URL.createObjectURL(file) : undefined;
      this.planFiles.push({
        file,
        name: file.name.replace(/\.[^.]+$/, ''),
        description: '',
        previewUrl,
      });
    }
    this.cdr.detectChanges();
  }

  removePlan(index: number): void {
    const plan = this.planFiles[index];
    if (plan.previewUrl) URL.revokeObjectURL(plan.previewUrl);
    this.planFiles.splice(index, 1);
    this.cdr.detectChanges();
  }

  // ─── Soumission ───────────────────────────────────────────────────────────

  canSubmit(): boolean {
    return this.projectName.trim().length > 0 && !this.isSubmitting;
  }

  async submit(): Promise<void> {
    if (!this.canSubmit()) return;
    this.isSubmitting = true;
    this.errorMessage = '';
    this.submitProgress = 'Création du projet…';

    let projectId: number;
    try {
      const project = await lastValueFrom(
        this.api.createProject(this.token, {
          name: this.projectName.trim(),
          description: this.projectDescription.trim() || null,
        }),
      );
      projectId = project.id;
    } catch (err: any) {
      this.errorMessage = err?.error?.detail ?? 'Erreur lors de la création du projet.';
      this.isSubmitting = false;
      this.submitProgress = '';
      this.cdr.detectChanges();
      return;
    }

    // Upload des plans séquentiellement (non bloquant en cas d'échec unitaire)
    for (let i = 0; i < this.planFiles.length; i++) {
      const plan = this.planFiles[i];
      this.submitProgress = `Upload des plans (${i + 1} / ${this.planFiles.length})…`;
      this.cdr.detectChanges();
      try {
        await lastValueFrom(
          this.api.uploadPlanBatiment(
            this.token,
            projectId,
            plan.file,
            plan.name || undefined,
            plan.description || undefined,
          ),
        );
      } catch {
        // Upload non bloquant : on continue avec les plans suivants
      }
    }

    // Déclencher le workflow agentique une fois tous les plans uploadés
    this.submitProgress = "Démarrage de l'analyse…";
    this.cdr.detectChanges();
    try {
      await lastValueFrom(this.api.runProjectWorkflow(this.token, projectId));
    } catch {
      // Le workflow peut aussi être relancé manuellement depuis la page du projet
    }

    this.router.navigate(['/dashboard/projects', projectId]);
  }

  cancel(): void {
    this.router.navigate(['/dashboard/projects']);
  }
}