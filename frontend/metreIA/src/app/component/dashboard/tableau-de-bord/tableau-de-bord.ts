import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Api } from '../../../shared/sevice/api';

@Component({
  selector: 'app-tableau-de-bord',
  imports: [CommonModule],
  templateUrl: './tableau-de-bord.html',
  styleUrl: './tableau-de-bord.scss',
})
export class TableauDeBord implements OnInit {

  public user_quota_used: number = 0;
  public user_plan_quota: number = 0;
  public token: string = '';
  public isLoading: boolean = true;

  get quotaRemaining(): number { return this.user_plan_quota - this.user_quota_used; }
  get quotaPercent(): number {
    if (!this.user_plan_quota) return 0;
    return Math.min(100, Math.round((this.user_quota_used / this.user_plan_quota) * 100));
  }

  constructor(private apiService: Api, private cdr: ChangeDetectorRef) {}

  ngOnInit(): void {
    this.token = localStorage.getItem('access_token') || '';
    this.apiService.me(this.token).subscribe({
      next: (response) => {
        this.user_quota_used = response.quota_used;
        this.user_plan_quota = response.plan_quota;
        this.isLoading = false;
        this.cdr.detectChanges();
      },
      error: (error) => {
        console.error('Error fetching user data:', error);
        this.isLoading = false;
        this.cdr.detectChanges();
      }
    });
  }
}
