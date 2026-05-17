import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Api } from '../../../shared/sevice/api';
import { MaterialCreateRequest, MaterialImportResult, MaterialResponse } from '../../../shared/model/interfaces';

@Component({
  selector: 'app-admin-materials',
  imports: [CommonModule, FormsModule],
  templateUrl: './admin-materials.html',
  styleUrl: './admin-materials.scss',
})
export class AdminMaterials implements OnInit {
  public materials: MaterialResponse[] = [];
  public isLoading = true;
  public errorMessage = '';

  // ─── Formulaire création ──────────────────────────────────────────────────
  public showCreateForm = false;
  public newMaterial: MaterialCreateRequest = this.emptyForm();
  public isCreating = false;
  public createError = '';

  // ─── Édition inline ───────────────────────────────────────────────────────
  public editingId: number | null = null;
  public editForm: MaterialCreateRequest = this.emptyForm();
  public isSaving = false;
  public saveError = '';

  // ─── Suppression ─────────────────────────────────────────────────────────
  public deletingId: number | null = null;

  // ─── Import Excel ─────────────────────────────────────────────────────────
  public selectedImportFile: File | null = null;
  public isImporting = false;
  public importResult: MaterialImportResult | null = null;
  public importError = '';

  private token = localStorage.getItem('admin_access_token') ?? '';

  constructor(private api: Api, private cdr: ChangeDetectorRef) {}

  ngOnInit(): void {
    this.loadMaterials();
  }

  private emptyForm(): MaterialCreateRequest {
    return { name: '', description: null, unite_defaut: '', unite_commerciale: null, conditionnement: null, facteur_conversion: null };
  }

  // ─── Chargement ───────────────────────────────────────────────────────────

  loadMaterials(): void {
    this.isLoading = true;
    this.errorMessage = '';
    this.api.getAdminMaterials(this.token).subscribe({
      next: (mats) => {
        this.materials = mats;
        this.isLoading = false;
        this.cdr.detectChanges();
      },
      error: () => {
        this.errorMessage = 'Impossible de charger le catalogue.';
        this.isLoading = false;
        this.cdr.detectChanges();
      },
    });
  }

  // ─── Création ─────────────────────────────────────────────────────────────

  openCreateForm(): void {
    this.newMaterial = this.emptyForm();
    this.createError = '';
    this.showCreateForm = true;
    this.editingId = null;
    this.cdr.detectChanges();
  }

  createMaterial(): void {
    if (!this.newMaterial.name.trim() || !this.newMaterial.unite_defaut.trim()) return;
    this.isCreating = true;
    this.createError = '';
    this.api.createAdminMaterial(this.token, this.newMaterial).subscribe({
      next: (mat) => {
        this.materials = [...this.materials, mat];
        this.showCreateForm = false;
        this.newMaterial = this.emptyForm();
        this.isCreating = false;
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.createError = err?.error?.detail ?? 'Erreur lors de la création.';
        this.isCreating = false;
        this.cdr.detectChanges();
      },
    });
  }

  // ─── Édition ──────────────────────────────────────────────────────────────

  startEdit(mat: MaterialResponse): void {
    this.editingId = mat.id;
    this.editForm = {
      name: mat.name,
      description: mat.description,
      unite_defaut: mat.unite_defaut,
      unite_commerciale: mat.unite_commerciale,
      conditionnement: mat.conditionnement,
      facteur_conversion: mat.facteur_conversion,
    };
    this.saveError = '';
    this.showCreateForm = false;
    this.cdr.detectChanges();
  }

  cancelEdit(): void {
    this.editingId = null;
    this.saveError = '';
    this.cdr.detectChanges();
  }

  saveEdit(): void {
    if (!this.editingId || !this.editForm.name.trim() || !this.editForm.unite_defaut.trim()) return;
    this.isSaving = true;
    this.saveError = '';
    this.api.updateAdminMaterial(this.token, this.editingId, this.editForm).subscribe({
      next: (updated) => {
        this.materials = this.materials.map(m => m.id === updated.id ? updated : m);
        this.editingId = null;
        this.isSaving = false;
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.saveError = err?.error?.detail ?? 'Erreur lors de la sauvegarde.';
        this.isSaving = false;
        this.cdr.detectChanges();
      },
    });
  }

  // ─── Suppression ─────────────────────────────────────────────────────────

  deleteMaterial(mat: MaterialResponse): void {
    if (!confirm(`Supprimer "${mat.name}" du catalogue ?`)) return;
    this.deletingId = mat.id;
    this.api.deleteAdminMaterial(this.token, mat.id).subscribe({
      next: () => {
        this.materials = this.materials.filter(m => m.id !== mat.id);
        if (this.editingId === mat.id) this.editingId = null;
        this.deletingId = null;
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.errorMessage = err?.error?.detail ?? 'Erreur lors de la suppression.';
        this.deletingId = null;
        this.cdr.detectChanges();
      },
    });
  }

  // ─── Import Excel ─────────────────────────────────────────────────────────

  onImportFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.selectedImportFile = input.files?.[0] ?? null;
    this.importResult = null;
    this.importError = '';
    this.cdr.detectChanges();
  }

  importExcel(): void {
    if (!this.selectedImportFile) return;
    this.isImporting = true;
    this.importResult = null;
    this.importError = '';
    this.api.importAdminMaterials(this.token, this.selectedImportFile).subscribe({
      next: (result) => {
        this.importResult = result;
        this.selectedImportFile = null;
        this.isImporting = false;
        // Recharge la liste complète pour refléter les ajouts/mises à jour
        this.loadMaterials();
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.importError = err?.error?.detail ?? "Erreur lors de l'import.";
        this.isImporting = false;
        this.cdr.detectChanges();
      },
    });
  }
}
