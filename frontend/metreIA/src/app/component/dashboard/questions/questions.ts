import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Api } from '../../../shared/sevice/api';
import { QuestionResponse } from '../../../shared/model/interfaces';

@Component({
  selector: 'app-questions',
  imports: [CommonModule, FormsModule],
  templateUrl: './questions.html',
  styleUrl: './questions.scss',
})
export class Questions implements OnInit {
  public questions: QuestionResponse[] = [];
  public isLoading = true;
  public errorMessage = '';

  // Filtre actif : 'all' | 'pending' | 'answered'
  public activeFilter: 'all' | 'pending' | 'answered' = 'all';

  // ID de la question dont l'input de réponse est ouvert
  public answeringId: number | null = null;
  public answerDraft = '';
  public isSubmitting = false;
  public submitError = '';

  private token = localStorage.getItem('access_token') ?? '';

  constructor(private api: Api, private cdr: ChangeDetectorRef) {}

  ngOnInit(): void {
    this.loadQuestions();
  }

  loadQuestions(): void {
    this.isLoading = true;
    this.errorMessage = '';
    this.api.getQuestions(this.token, this.activeFilter === 'all' ? undefined : this.activeFilter).subscribe({
      next: (data) => {
        this.questions = data;
        this.isLoading = false;
        this.cdr.detectChanges();
      },
      error: () => {
        this.errorMessage = 'Impossible de charger les questions.';
        this.isLoading = false;
        this.cdr.detectChanges();
      },
    });
  }

  setFilter(filter: 'all' | 'pending' | 'answered'): void {
    this.activeFilter = filter;
    this.loadQuestions();
  }

  get pendingCount(): number {
    return this.questions.filter(q => q.status === 'pending').length;
  }

  openAnswer(q: QuestionResponse): void {
    this.answeringId = q.id;
    this.answerDraft = '';
    this.submitError = '';
  }

  cancelAnswer(): void {
    this.answeringId = null;
    this.answerDraft = '';
    this.submitError = '';
  }

  submitAnswer(q: QuestionResponse): void {
    if (!this.answerDraft.trim()) return;
    this.isSubmitting = true;
    this.submitError = '';
    this.api.answerQuestion(this.token, q.id, this.answerDraft.trim()).subscribe({
      next: (updated) => {
        const idx = this.questions.findIndex(x => x.id === updated.id);
        if (idx !== -1) this.questions[idx] = updated;
        this.answeringId = null;
        this.answerDraft = '';
        this.cdr.detectChanges();
        this.isSubmitting = false;
      },
      error: () => {
        this.submitError = 'Erreur lors de l\'envoi de la réponse.';
        this.isSubmitting = false;
      },
    });
  }

  formatDate(iso: string): string {
    const d = new Date(iso);
    return d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  }
}
