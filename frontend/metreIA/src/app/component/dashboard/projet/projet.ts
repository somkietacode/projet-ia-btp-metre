import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { Api } from '../../../shared/sevice/api';
import { ProjectSummaryResponse } from '../../../shared/model/interfaces';

@Component({
  selector: 'app-projet',
  imports: [CommonModule],
  templateUrl: './projet.html',
  styleUrl: './projet.scss',
})
export class Projet implements OnInit {
  public projects: ProjectSummaryResponse[] = [];
  public isLoading = true;
  public errorMessage = '';
  public deletingId: number | null = null;

  private token = localStorage.getItem('access_token') ?? '';

  constructor(
    private api: Api,
    private router: Router,
    private cdr: ChangeDetectorRef,
  ) {}

  ngOnInit(): void {
    this.loadProjects();
  }

  loadProjects(): void {
    this.isLoading = true;
    this.errorMessage = '';
    this.api.getProjects(this.token).subscribe({
      next: (projects) => {
        this.projects = projects;
        this.isLoading = false;
        this.cdr.detectChanges();
      },
      error: () => {
        this.errorMessage = 'Impossible de charger les projets.';
        this.isLoading = false;
        this.cdr.detectChanges();
      },
    });
  }

  goToNewProject(): void {
    this.router.navigate(['/dashboard/projects/new']);
  }

  openProject(id: number): void {
    this.router.navigate(['/dashboard/projects', id]);
  }

  confirmDelete(project: ProjectSummaryResponse): void {
    if (!confirm(`Supprimer définitivement le projet "${project.name}" ?`)) return;
    this.deletingId = project.id;
    this.api.deleteProject(this.token, project.id).subscribe({
      next: () => {
        this.projects = this.projects.filter(p => p.id !== project.id);
        this.deletingId = null;
        this.cdr.detectChanges();
      },
      error: () => {
        this.errorMessage = `Impossible de supprimer le projet #${project.id}.`;
        this.deletingId = null;
        this.cdr.detectChanges();
      },
    });
  }

  getStatusLabel(status: string): string {
    const labels: Record<string, string> = {
      pending:           'En attente',
      vision_running:    'Analyse en cours',
      vision_done:       'Analyse terminée',
      extraction_running:'Extraction en cours',
      waiting_user:      'En attente de réponse',
      calcul_running:    'Calcul en cours',
      done:              'Terminé',
      error:             'Erreur',
    };
    return labels[status] ?? status;
  }

  getStatusClass(status: string): string {
    const classes: Record<string, string> = {
      pending:           'status-pending',
      vision_running:    'status-running',
      vision_done:       'status-running',
      extraction_running:'status-running',
      waiting_user:      'status-waiting',
      calcul_running:    'status-running',
      done:              'status-done',
      error:             'status-error',
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
