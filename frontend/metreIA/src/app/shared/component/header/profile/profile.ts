import { Component, Input, OnInit } from '@angular/core';
import { Badges } from '../badges/badges';

@Component({
  selector: 'app-profile',
  imports: [Badges],
  templateUrl: './profile.html',
  styleUrl: './profile.scss',
})
export class Profile implements OnInit {
  @Input() email: string = '';
  @Input() planId: number = 0;
  public userInitials: string = '';
  ngOnInit(): void {
    this.userInitials = this.getUserInitials();
  }
  getUserInitials(): string {
    if (!this.email) return '…';
    const namePart = this.email.split('@')[0];
    const initials = namePart.split('.').map(part => part.charAt(0).toUpperCase()).join('');
    return initials.slice(0, 2);
  }
  goTohome(): void {
    if (this.planId !== 999) {
      window.location.href = '/dashboard';
    } else {
      window.location.href = '/admin/dashboard';
    }
  }

  logout(): void {
    if (this.planId === 999) {
      localStorage.removeItem('admin_access_token');
      localStorage.removeItem('admin_email');
      window.location.href = '/auth/admin-login';
    } else {
      localStorage.removeItem('access_token');
      localStorage.removeItem('user_email');
      localStorage.removeItem('plan_id');
      window.location.href = '/auth/login';
    }
  }
}
