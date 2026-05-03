import { Component, ChangeDetectorRef } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { Header } from '../../../shared/component/header/header';
import { Api } from '../../../shared/sevice/api';
import { Token } from '../../../shared/model/interfaces';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-login',
  imports: [Header, FormsModule, RouterLink, CommonModule],
  templateUrl: './login.html',
  styleUrl: './login.scss',
})
export class Login {
  email = '';
  password = '';
  isLoading = false;
  errorMessage = '';

  constructor(private api: Api, private router: Router, private cdr: ChangeDetectorRef) {}

  onSubmit(): void {
    if (!this.email || !this.password) return;

    this.isLoading = true;
    this.errorMessage = '';

    this.api.login(this.email, this.password).subscribe({
      next: (token: Token) => {
        localStorage.setItem('access_token', token.access_token);
        localStorage.setItem('user_email', this.email);
        this.isLoading = false;
        this.cdr.detectChanges();
        this.router.navigate(['/dashboard']);
      },
      error: (err) => {
        const detail = err?.error?.detail;
        if (typeof detail === 'string') {
          this.errorMessage = detail;
        } else if (Array.isArray(detail)) {
          this.errorMessage = detail.map((e: any) => e.msg ?? e).join(' · ');
        } else {
          this.errorMessage = 'Une erreur est survenue. Veuillez réessayer.';
        }
        this.isLoading = false;
        this.cdr.detectChanges();
      },
    });
  }
}
