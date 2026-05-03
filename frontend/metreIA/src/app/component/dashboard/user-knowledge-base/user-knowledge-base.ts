import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Api } from '../../../shared/sevice/api';
import {
  UserDocumentDetailResponse,
  UserDocumentResponse,
  UserVectorSearchChunkResult,
  UserVectorSearchResponse,
} from '../../../shared/model/interfaces';

@Component({
  selector: 'app-user-knowledge-base',
  imports: [CommonModule, FormsModule],
  templateUrl: './user-knowledge-base.html',
  styleUrl: './user-knowledge-base.scss',
})
export class UserKnowledgeBase implements OnInit {
  public docs: UserDocumentResponse[] = [];
  public isLoading = true;
  public errorMessage = '';
  public uploadError = '';
  public uploadSuccess = '';
  public isUploading = false;

  // Modale de prévisualisation du contenu textuel
  public previewDoc: UserDocumentDetailResponse | null = null;
  public isLoadingPreview = false;

  // Fichier sélectionné pour l'upload
  public selectedFile: File | null = null;

  // ─── Recherche vectorielle ─────────────────────────────────────────────────
  public searchQuery = '';
  public searchTopK = 5;
  public searchResults: UserVectorSearchResponse | null = null;
  public isSearching = false;
  public searchError = '';
  // Chunk ouvert dans la modale de détail résultat
  public activeChunk: UserVectorSearchChunkResult | null = null;

  private token = localStorage.getItem('access_token') ?? '';

  constructor(private api: Api, private cdr: ChangeDetectorRef) {}

  ngOnInit(): void {
    this.loadDocs();
  }

  // ─── Chargement ──────────────────────────────────────────────────────────

  loadDocs(): void {
    this.isLoading = true;
    this.api.getUserDocs(this.token).subscribe({
      next: (docs) => {
        this.docs = docs;
        this.isLoading = false;
        this.cdr.detectChanges();
      },
      error: () => {
        this.errorMessage = 'Impossible de charger votre base documentaire.';
        this.isLoading = false;
        this.cdr.detectChanges();
      },
    });
  }

  // ─── Upload ───────────────────────────────────────────────────────────────

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.selectedFile = input.files?.[0] ?? null;
    this.uploadError = '';
    this.uploadSuccess = '';
    this.cdr.detectChanges();
  }

  uploadFile(): void {
    if (!this.selectedFile) return;
    this.isUploading = true;
    this.uploadError = '';
    this.uploadSuccess = '';

    this.api.uploadUserDoc(this.token, this.selectedFile).subscribe({
      next: (doc) => {
        this.uploadSuccess = `"${doc.filename}" ajouté avec succès (${doc.indexation_status}).`;
        this.selectedFile = null;
        this.isUploading = false;
        this.docs = [doc, ...this.docs];
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.uploadError = this._extractErrorMessage(err, "Erreur lors de l'upload.");
        this.isUploading = false;
        this.cdr.detectChanges();
      },
    });
  }

  // ─── Prévisualisation ─────────────────────────────────────────────────────

  openPreview(doc: UserDocumentResponse): void {
    if (doc.indexation_status !== 'indexed') return;
    this.previewDoc = null;
    this.isLoadingPreview = true;
    this.cdr.detectChanges();

    this.api.getUserDoc(this.token, doc.id).subscribe({
      next: (detail) => {
        this.previewDoc = detail;
        this.isLoadingPreview = false;
        this.cdr.detectChanges();
      },
      error: () => {
        this.isLoadingPreview = false;
        this.cdr.detectChanges();
      },
    });
  }

  closePreview(): void {
    this.previewDoc = null;
    this.cdr.detectChanges();
  }

  // ─── Téléchargement ───────────────────────────────────────────────────────

  downloadDoc(doc: UserDocumentResponse): void {
    this.api.downloadUserDoc(this.token, doc.id).subscribe({
      next: (blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = doc.filename;
        a.click();
        URL.revokeObjectURL(url);
      },
    });
  }

  // ─── Suppression ─────────────────────────────────────────────────────────

  deleteDoc(doc: UserDocumentResponse): void {
    if (!confirm(`Supprimer définitivement "${doc.filename}" ?`)) return;
    this.api.deleteUserDoc(this.token, doc.id).subscribe({
      next: () => {
        this.loadDocs();
      },
      error: () => {
        this.errorMessage = `Impossible de supprimer le document #${doc.id}.`;
        this.cdr.detectChanges();
      },
    });
  }

  // ─── Recherche vectorielle ─────────────────────────────────────────────────

  runSearch(): void {
    if (!this.searchQuery.trim()) return;
    this.isSearching = true;
    this.searchError = '';
    this.searchResults = null;

    let topK = Number(this.searchTopK);
    if (isNaN(topK) || topK <= 0) {
      topK = 5;
    }

    this.api.searchUserDocs(this.token, this.searchQuery.trim(), topK).subscribe({
      next: (res) => {
        this.searchResults = res;
        this.isSearching = false;
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.searchError = this._extractErrorMessage(err, 'Erreur lors de la recherche.');
        this.isSearching = false;
        this.cdr.detectChanges();
      },
    });
  }

  openChunk(chunk: UserVectorSearchChunkResult): void {
    this.activeChunk = chunk;
    this.cdr.detectChanges();
  }

  closeChunk(): void {
    this.activeChunk = null;
    this.cdr.detectChanges();
  }

  scorePercent(score: number): string {
    return (score * 100).toFixed(1) + ' %';
  }

  scoreClass(score: number): string {
    if (score >= 0.75) return 'score-high';
    if (score >= 0.50) return 'score-mid';
    return 'score-low';
  }

  // ─── Helpers ─────────────────────────────────────────────────────────────

  private _extractErrorMessage(err: any, fallback: string): string {
    const detail = err?.error?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) return detail.map((e: any) => e.msg ?? JSON.stringify(e)).join(' — ');
    if (err?.message) return err.message;
    return fallback;
  }

  getStatusLabel(status: string): string {
    const labels: Record<string, string> = {
      indexed:  'Indexé',
      failed:   'Échec',
      pending:  'En attente',
      indexing: 'En cours',
    };
    return labels[status] ?? status;
  }

  getStatusClass(status: string): string {
    const classes: Record<string, string> = {
      indexed:  'status-indexed',
      failed:   'status-failed',
      pending:  'status-pending',
      indexing: 'status-indexing',
    };
    return classes[status] ?? '';
  }

  formatDate(iso: string): string {
    try {
      return new Date(iso).toLocaleString('fr-FR', {
        day: '2-digit', month: '2-digit', year: 'numeric',
        hour: '2-digit', minute: '2-digit',
      });
    } catch {
      return iso;
    }
  }
}
