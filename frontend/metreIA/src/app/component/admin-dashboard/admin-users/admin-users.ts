import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Api } from '../../../shared/sevice/api';
import { PlanResponse } from '../../../shared/model/interfaces';

@Component({
  selector: 'app-admin-users',
  imports: [CommonModule, FormsModule],
  templateUrl: './admin-users.html',
  styleUrl: './admin-users.scss',
})
export class AdminUsers implements OnInit {
  public allUsers: any[] = [];
  public filteredUsers: any[] = [];
  public plans: PlanResponse[] = [];
  public isLoading = true;
  public errorMessage = '';
  public searchQuery = '';
  public selectedPlan = '';

  // ─── Édition inline du plan ────────────────────────────────────────────────
  public editingPlanUserId: number | null = null;
  public editingPlanValue: number | null = null;
  public planSaving = false;
  public planFeedback: { userId: number; ok: boolean; message: string } | null = null;

  constructor(private apiService: Api, private cdr: ChangeDetectorRef) {}

  ngOnInit(): void {
    const token = localStorage.getItem('admin_access_token') ?? '';
    this.apiService.getPlans().subscribe({
      next: (plans) => { this.plans = plans; this.cdr.detectChanges(); }
    });
    this.apiService.getAdminUsers(token).subscribe({
      next: (users) => {
        this.allUsers = users;
        this.filteredUsers = users;
        this.isLoading = false;
        this.cdr.detectChanges();
      },
      error: () => {
        this.errorMessage = 'Impossible de charger la liste des utilisateurs.';
        this.isLoading = false;
        this.cdr.detectChanges();
      },
    });
  }

  applyFilters(): void {
    const q = this.searchQuery.toLowerCase().trim();
    this.filteredUsers = this.allUsers.filter(user => {
      const matchSearch = !q || user.username?.toLowerCase().includes(q) || user.email?.toLowerCase().includes(q);
      const matchPlan = !this.selectedPlan || user.plan_id === Number(this.selectedPlan);
      return matchSearch && matchPlan;
    });
  }

  getPlanName(planId: number): string {
    return this.plans.find(p => p.id === planId)?.name ?? `Plan ${planId}`;
  }

  getPlanQuota(planId: number): number {
    return this.plans.find(p => p.id === planId)?.quota ?? 0;
  }

  getQuotaPercent(user: any): number {
    const quota = this.getPlanQuota(user.plan_id);
    if (!quota) return 0;
    return Math.min(100, Math.round((user.quota_used / quota) * 100));
  }

  // ─── Upgrade plan ─────────────────────────────────────────────────────────

  startEditPlan(user: any): void {
    this.editingPlanUserId = user.id;
    this.editingPlanValue = user.plan_id;
    this.planFeedback = null;
    this.cdr.detectChanges();
  }

  cancelEditPlan(): void {
    this.editingPlanUserId = null;
    this.editingPlanValue = null;
    this.cdr.detectChanges();
  }

  savePlan(user: any): void {
    if (this.planSaving || this.editingPlanValue === null) return;
    if (this.editingPlanValue === user.plan_id) { this.cancelEditPlan(); return; }
    const token = localStorage.getItem('admin_access_token') ?? '';
    this.planSaving = true;
    this.apiService.updateUserPlan(token, user.id, this.editingPlanValue).subscribe({
      next: (updated) => {
        const idx = this.allUsers.findIndex(u => u.id === user.id);
        if (idx !== -1) this.allUsers[idx] = updated;
        this.applyFilters();
        this.planFeedback = { userId: user.id, ok: true, message: 'Plan mis à jour.' };
        this.editingPlanUserId = null;
        this.editingPlanValue = null;
        this.planSaving = false;
        this.cdr.detectChanges();
        setTimeout(() => { this.planFeedback = null; this.cdr.detectChanges(); }, 3000);
      },
      error: () => {
        this.planFeedback = { userId: user.id, ok: false, message: 'Erreur lors de la mise à jour.' };
        this.planSaving = false;
        this.cdr.detectChanges();
      },
    });
  }
}
