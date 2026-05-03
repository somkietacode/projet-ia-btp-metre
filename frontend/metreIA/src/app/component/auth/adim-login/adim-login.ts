import { Component, ChangeDetectorRef } from '@angular/core';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { Header } from '../../../shared/component/header/header';
import { Api } from '../../../shared/sevice/api';
import { Token } from '../../../shared/model/interfaces';

@Component({
  selector: 'app-adim-login',
  imports: [Header, FormsModule, CommonModule],
  templateUrl: './adim-login.html',
  styleUrl: './adim-login.scss',
})
export class AdimLogin {
  email = '';
  password = '';
  isLoading = false;
  errorMessage = '';

  constructor(private api: Api, private router: Router, private cdr: ChangeDetectorRef) {}

  onSubmit(): void {
    if (!this.email || !this.password) return;

    this.isLoading = true;
    this.errorMessage = '';

    this.api.loginAdmin(this.email, this.password).subscribe({
      next: (token: Token) => {
        localStorage.setItem('admin_access_token', token.access_token);
        localStorage.setItem('admin_email', this.email);
        this.isLoading = false;
        this.cdr.detectChanges();
        this.router.navigate(['/admin/dashboard']);
      },
      error: (err) => {
        const detail = err?.error?.detail;
        if (typeof detail === 'string') {
          this.errorMessage = detail;
        } else if (Array.isArray(detail)) {
          this.errorMessage = detail.map((e: any) => e.msg ?? e).join(' · ');
        } else {
          this.errorMessage = 'Email ou mot de passe administrateur invalide.';
        }
        this.isLoading = false;
        this.cdr.detectChanges();
      },
    });
  }
}
