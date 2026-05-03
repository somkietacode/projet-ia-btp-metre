import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { Api } from '../../../shared/sevice/api';
import { PlanResponse } from '../../../shared/model/interfaces';

@Component({
  selector: 'app-admin-home',
  imports: [CommonModule, RouterLink],
  templateUrl: './admin-home.html',
  styleUrl: './admin-home.scss',
})
export class AdminHome implements OnInit {
  public users: any[] = [];
  public plans: PlanResponse[] = [];
  public isLoading = true;
  public errorMessage = '';

  get totalUsers(): number { return this.users.length; }
  get totalQuotaUsed(): number { return this.users.reduce((s, u) => s + (u.quota_used ?? 0), 0); }
  get recentUsers(): any[] { return [...this.users].slice(-5).reverse(); }

  getPlanName(planId: number): string {
    return this.plans.find(p => p.id === planId)?.name ?? `Plan ${planId}`;
  }

  constructor(private apiService: Api, private cdr: ChangeDetectorRef) {}

  ngOnInit(): void {
    const token = localStorage.getItem('admin_access_token') ?? '';
    this.apiService.getPlans().subscribe({
      next: (plans) => { this.plans = plans; this.cdr.detectChanges(); }
    });
    this.apiService.getAdminUsers(token).subscribe({
      next: (users) => {
        this.users = users;
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
}
