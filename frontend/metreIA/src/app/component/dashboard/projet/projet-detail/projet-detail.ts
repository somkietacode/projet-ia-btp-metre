import { Component, OnInit, OnDestroy, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { Api } from '../../../../shared/sevice/api';
import {
  ProjectDetailResponse,
  QuestionResponse,
  OuvrageResponse,
  PlanBatimentResponse,
  AgentStreamEvent,
} from '../../../../shared/model/interfaces';

@Component({
  selector: 'app-projet-detail',
  imports: [CommonModule, FormsModule],
  templateUrl: './projet-detail.html',
  styleUrl: './projet-detail.scss',
})
export class ProjetDetail implements OnInit, OnDestroy {
  public project: ProjectDetailResponse | null = null;
  public isLoading = true;
  public errorMessage = '';

  // ─── Onglet actif : 'overview' | 'questions' | 'ouvrages' | 'plans' ──────
  public activeTab: 'overview' | 'questions' | 'ouvrages' | 'plans' = 'overview';

  // ─── Réponse aux questions ────────────────────────────────────────────────
  public answeringId: number | null = null;
  public answerDraft = '';
  public isSubmittingAnswer = false;
  public answerError = '';

  // ─── Upload plan ──────────────────────────────────────────────────────────
  public selectedPlanFile: File | null = null;
  public planName = '';
  public isUploadingPlan = false;
  public uploadPlanError = '';
  public uploadPlanSuccess = '';

  // ─── Quota token live ────────────────────────────────────────────────────────
  public liveQuotaUsed: number | null = null;
  public livePlanQuota: number | null = null;

  // ─── Journal d'activité temps réel ──────────────────────────────────────────
  public activityLog: { time: string; message: string; icon: string }[] = [];
  private readonly MAX_LOG_ENTRIES = 50;

  // ─── SSE (Server-Sent Events) ───────────────────────────────────────────────
  private eventSource: EventSource | null = null;

  // ─── Ancien polling (conservé pour compatibilité statuts non-SSE) ─────────
  private pollingInterval: ReturnType<typeof setInterval> | null = null;
  private readonly POLLING_DELAY_MS = 5000;

  private token = localStorage.getItem('access_token') ?? '';
  private projectId!: number;

  constructor(
    private api: Api,
    private route: ActivatedRoute,
    private router: Router,
    private cdr: ChangeDetectorRef,
  ) {}

  ngOnInit(): void {
    this.projectId = Number(this.route.snapshot.paramMap.get('id'));
    this.loadProject();
  }

  ngOnDestroy(): void {
    this.stopPolling();
    this.stopSSE();
  }

  // ─── Chargement ───────────────────────────────────────────────────────────

  loadProject(silent = false): void {
    if (!silent) {
      this.isLoading = true;
      this.errorMessage = '';
    }
    this.api.getProject(this.token, this.projectId).subscribe({
      next: (project) => {
        this.project = project;
        this.isLoading = false;
        this.cdr.detectChanges();
        // Démarrage SSE pour les statuts actifs (avant de retomber sur le polling)
        if (['calcul_running', 'waiting_user'].includes(project.status)) {
          this.startSSE();
        } else {
          this.managePolling(project.status);
        }
      },
      error: () => {
        this.errorMessage = 'Impossible de charger le projet.';
        this.isLoading = false;
        this.stopPolling();
        this.cdr.detectChanges();
      },
    });
  }

  // ─── SSE — flux temps réel du workflow agentique ──────────────────────────

  private addToLog(message: string, icon = 'fa-gear'): void {
    const time = new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    this.activityLog = [{ time, message, icon }, ...this.activityLog].slice(0, this.MAX_LOG_ENTRIES);
  }

  startSSE(): void {
    if (this.eventSource) return; // déjà connecté
    this.stopPolling();
    this.eventSource = this.api.streamProjectEvents(this.token, this.projectId);
    this.eventSource.onmessage = (e: MessageEvent) => {
      try {
        const event: AgentStreamEvent = JSON.parse(e.data);
        this.handleSSEEvent(event);
      } catch { /* ignore malformed events */ }
    };
    this.eventSource.onerror = () => {
      // En cas d'erreur réseau, on repasse sur le polling classique
      this.stopSSE();
      this.loadProject(true);
    };
  }

  private stopSSE(): void {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }

  private handleSSEEvent(event: AgentStreamEvent): void {
    if (!this.project) return;

    switch (event.type) {
      case 'step':
        this.project.current_step = event.message ?? null;
        this.project.status = 'calcul_running';
        this.addToLog(event.message ?? '...', 'fa-gear');
        break;

      case 'ouvrage': {
        // Ajout optimiste d'un nouvel ouvrage dans la liste locale
        const newOuvrage: OuvrageResponse = {
          id: event.id!,
          name: event.name!,
          categorie: event.categorie!,
          description: event.description ?? null,
          position: this.project.ouvrages.length,
          lignes_de_calcul: [],
        };
        this.project.ouvrages = [...this.project.ouvrages, newOuvrage];
        this.project.current_step = `Ouvrage créé : ${event.name}`;
        this.addToLog('Ouvrage créé : ' + event.name, 'fa-layer-group');
        // Basculer automatiquement sur l'onglet ouvrages au 1er ouvrage
        if (this.project.ouvrages.length === 1) {
          this.activeTab = 'ouvrages';
        }
        break;
      }

      case 'calcul': {
        // Ajout optimiste d'une ligne de calcul à l'ouvrage concerné
        const ouvrageIdx = this.project.ouvrages.findIndex(o => o.id === event.ouvrage_id);
        if (ouvrageIdx !== -1) {
          const ouvrage = this.project.ouvrages[ouvrageIdx];
          const newLigne = {
            id: event.id!,
            description: event.message ?? event.description ?? '',
            quantity: event.quantity!,
            unit: event.unit!,
            position: ouvrage.lignes_de_calcul.length,
            material: { id: 0, name: '', description: null, unite_defaut: event.unit!, project_id: this.projectId },
          };
          const updated = { ...ouvrage, lignes_de_calcul: [...ouvrage.lignes_de_calcul, newLigne] };
          this.project.ouvrages = [
            ...this.project.ouvrages.slice(0, ouvrageIdx),
            updated,
            ...this.project.ouvrages.slice(ouvrageIdx + 1),
          ];
        }
        this.addToLog((event.description ?? event.message ?? 'Calcul') + (event.quantity ? ' : ' + event.quantity + ' ' + (event.unit ?? '') : ''), 'fa-calculator');
        break;
      }

      case 'question': {
        // Ajout de la question et basculement sur l'onglet questions
        const q: QuestionResponse = {
          id: event.id!,
          project_id: this.projectId,
          project_name: this.project.name,
          ouvrage_id: event.ouvrage_id ?? null,
          ouvrage_name: null,
          question_text: event.text!,
          status: 'pending',
          asked_date: new Date().toISOString(),
          answer_text: null,
          answered_date: null,
        };
        const alreadyExists = this.project.questions.some(existing => existing.id === q.id);
        if (!alreadyExists) {
          this.project.questions = [...this.project.questions, q];
          this.project.questions_pending_count = this.pendingQuestions.length;
        }
        this.project.status = 'waiting_user';
        this.activeTab = 'questions';
        this.addToLog('Question : ' + event.text, 'fa-circle-question');
        break;
      }

      case 'quota':
        this.liveQuotaUsed = event.quota_used ?? null;
        this.livePlanQuota = event.plan_quota ?? null;
        break;

      case 'done':
        this.project.status = 'done';
        this.project.current_step = event.message ?? 'Calculs terminés';
        this.addToLog('Analyse terminée', 'fa-circle-check');
        this.stopSSE();
        // Recharge complète pour avoir les données BDD à jour
        this.loadProject(true);
        break;

      case 'error':
        this.project.status = 'error';
        this.errorMessage = event.message ?? 'Une erreur est survenue.';
        this.addToLog('Erreur : ' + (event.message ?? ''), 'fa-triangle-exclamation');
        this.stopSSE();
        break;

      case 'answer_received':
        this.project.status = 'calcul_running';
        break;
    }

    this.cdr.detectChanges();
  }

  // ─── Polling pour les projets en cours de traitement ─────────────────────

  private managePolling(status: string): void {
    const isActive = ['vision_running', 'extraction_running', 'calcul_running'].includes(status);
    if (isActive && !this.pollingInterval) {
      this.pollingInterval = setInterval(() => this.loadProject(true), this.POLLING_DELAY_MS);
    } else if (!isActive) {
      this.stopPolling();
    }
  }

  private stopPolling(): void {
    if (this.pollingInterval) {
      clearInterval(this.pollingInterval);
      this.pollingInterval = null;
    }
  }

  // ─── Navigation ───────────────────────────────────────────────────────────

  goBack(): void {
    this.router.navigate(['/dashboard/projects']);
  }

  setTab(tab: 'overview' | 'questions' | 'ouvrages' | 'plans'): void {
    this.activeTab = tab;
  }

  // ─── Questions ────────────────────────────────────────────────────────────

  get pendingQuestions(): QuestionResponse[] {
    return this.project?.questions.filter(q => q.status === 'pending') ?? [];
  }

  get answeredQuestions(): QuestionResponse[] {
    return this.project?.questions.filter(q => q.status === 'answered') ?? [];
  }

  openAnswer(q: QuestionResponse): void {
    this.answeringId = q.id;
    this.answerDraft = '';
    this.answerError = '';
    this.cdr.detectChanges();
  }

  cancelAnswer(): void {
    this.answeringId = null;
    this.answerDraft = '';
    this.cdr.detectChanges();
  }

  submitAnswer(q: QuestionResponse): void {
    if (!this.answerDraft.trim()) return;
    this.isSubmittingAnswer = true;
    this.answerError = '';
    this.api.resumeWorkflow(this.token, this.projectId, this.answerDraft.trim()).subscribe({
      next: () => {
        if (this.project) {
          // Marque la question comme répondue localement
          this.project.questions = this.project.questions.map(existing =>
            existing.id === q.id
              ? { ...existing, status: 'answered' as const, answer_text: this.answerDraft.trim() }
              : existing,
          );
          this.project.questions_pending_count = this.pendingQuestions.length;
          this.project.status = 'calcul_running';
        }
        this.answeringId = null;
        this.answerDraft = '';
        this.isSubmittingAnswer = false;
        // S'assure que le flux SSE est actif pour recevoir la suite
        this.startSSE();
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.answerError = err?.error?.detail ?? 'Erreur lors de la soumission.';
        this.isSubmittingAnswer = false;
        this.cdr.detectChanges();
      },
    });
  }

  // ─── Lancement du workflow ─────────────────────────────────────────────────

  canRunWorkflow(): boolean {
    return !!this.project && ['pending', 'done', 'error'].includes(this.project.status);
  }

  isRunningWorkflow = false;

  runWorkflow(): void {
    if (!this.project || this.isRunningWorkflow) return;
    this.isRunningWorkflow = true;
    this.errorMessage = '';
    this.activityLog = [];
    this.cdr.detectChanges();
    this.api.runProjectWorkflow(this.token, this.projectId).subscribe({
      next: () => {
        if (this.project) this.project.status = 'calcul_running';
        this.isRunningWorkflow = false;
        this.startSSE();
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.errorMessage = err?.error?.detail ?? 'Erreur lors du lancement du workflow.';
        this.isRunningWorkflow = false;
        this.cdr.detectChanges();
      },
    });
  }

  // ─── Plans de bâtiment ────────────────────────────────────────────────────

  onPlanFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.selectedPlanFile = input.files?.[0] ?? null;
    this.uploadPlanError = '';
    this.uploadPlanSuccess = '';
    this.cdr.detectChanges();
  }

  uploadPlan(): void {
    if (!this.selectedPlanFile) return;
    this.isUploadingPlan = true;
    this.uploadPlanError = '';
    this.uploadPlanSuccess = '';
    this.api.uploadPlanBatiment(
      this.token, this.projectId, this.selectedPlanFile, this.planName.trim() || undefined,
    ).subscribe({
      next: (plan) => {
        if (this.project) {
          this.project.plans_batiment = [...this.project.plans_batiment, plan];
          this.project.plans_count = this.project.plans_batiment.length;
        }
        this.uploadPlanSuccess = `"${plan.name}" ajouté avec succès.`;
        this.selectedPlanFile = null;
        this.planName = '';
        this.isUploadingPlan = false;
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.uploadPlanError = err?.error?.detail ?? "Erreur lors de l'upload.";
        this.isUploadingPlan = false;
        this.cdr.detectChanges();
      },
    });
  }

  deletePlan(plan: PlanBatimentResponse): void {
    if (!confirm(`Supprimer le plan "${plan.name}" ?`)) return;
    this.api.deletePlanBatiment(this.token, this.projectId, plan.id).subscribe({
      next: () => {
        if (this.project) {
          this.project.plans_batiment = this.project.plans_batiment.filter(p => p.id !== plan.id);
          this.project.plans_count = this.project.plans_batiment.length;
        }
        this.cdr.detectChanges();
      },
    });
  }

  // ─── Export résultats CSV ─────────────────────────────────────────────────

  exportResults(): void {
    if (!this.project || this.project.ouvrages.length === 0) return;

    const lines: string[] = ['Ouvrage;Catégorie;Description;Matériau;Quantité;Unité'];
    for (const ouvrage of this.project.ouvrages) {
      for (const ligne of ouvrage.lignes_de_calcul) {
        lines.push([
          ouvrage.name,
          ouvrage.categorie,
          ligne.description,
          ligne.material.name,
          ligne.quantity.toString().replace('.', ','),
          ligne.unit,
        ].map(v => `"${v}"`).join(';'));
      }
    }

    const blob = new Blob(['\uFEFF' + lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${this.project.name}_resultats.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  // ─── Utilitaires ─────────────────────────────────────────────────────────

  getStatusLabel(status: string): string {
    const labels: Record<string, string> = {
      pending:            'En attente',
      vision_running:     'Analyse visuelle en cours',
      vision_done:        'Analyse terminée',
      extraction_running: 'Extraction en cours',
      waiting_user:       'En attente de vos réponses',
      calcul_running:     'Calcul en cours',
      done:               'Terminé',
      error:              'Erreur',
    };
    return labels[status] ?? status;
  }

  getStatusClass(status: string): string {
    const classes: Record<string, string> = {
      pending:            'status-pending',
      vision_running:     'status-running',
      vision_done:        'status-running',
      extraction_running: 'status-running',
      waiting_user:       'status-waiting',
      calcul_running:     'status-running',
      done:               'status-done',
      error:              'status-error',
    };
    return classes[status] ?? '';
  }

  isProcessing(status: string): boolean {
    return ['vision_running', 'extraction_running', 'calcul_running'].includes(status);
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

  totalQuantityByMaterial(): { name: string; unite: string; total: number }[] {
    if (!this.project) return [];
    const map = new Map<string, { name: string; unite: string; total: number }>();
    for (const ouvrage of this.project.ouvrages) {
      for (const ligne of ouvrage.lignes_de_calcul) {
        const key = `${ligne.material.name}__${ligne.unit}`;
        const existing = map.get(key);
        if (existing) {
          existing.total += ligne.quantity;
        } else {
          map.set(key, { name: ligne.material.name, unite: ligne.unit, total: ligne.quantity });
        }
      }
    }
    return Array.from(map.values()).sort((a, b) => a.name.localeCompare(b.name));
  }
}
