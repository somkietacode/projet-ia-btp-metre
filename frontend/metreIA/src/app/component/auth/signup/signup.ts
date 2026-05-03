import { Component, ChangeDetectorRef } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { Header } from '../../../shared/component/header/header';
import { Api } from '../../../shared/sevice/api';
import { Token } from '../../../shared/model/interfaces';

@Component({
  selector: 'app-signup',
  imports: [Header, FormsModule, RouterLink, CommonModule],
  templateUrl: './signup.html',
  styleUrl: './signup.scss',
})
export class Signup {
  email = '';
  password = '';
  confirmPassword = '';
  isLoading = false;
  errorMessage = '';

  constructor(private api: Api, private router: Router, private cdr: ChangeDetectorRef) {}

  onSubmit(): void {
    if (!this.email || !this.password || !this.confirmPassword) return;

    if (this.password !== this.confirmPassword) {
      this.errorMessage = 'Les mots de passe ne correspondent pas.';
      this.cdr.detectChanges();
      return;
    }

    this.isLoading = true;
    this.errorMessage = '';

    this.api.register({ email: this.email, password: this.password }).subscribe({
      next: (token: Token) => {
        localStorage.setItem('access_token', token.access_token);
        localStorage.setItem('user_email', this.email);
        this.isLoading = false;
        this.cdr.detectChanges();
        this.router.navigate(['/']);
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
