import { Component, OnInit } from '@angular/core';
import { SiteLogo } from './site-logo/site-logo';
import { DesktopMenu } from './desktop-menu/desktop-menu';
import { HeaderCta } from './header-cta/header-cta';
import { CommonModule } from '@angular/common';
import { Api } from '../../sevice/api';
import { Profile } from './profile/profile';

@Component({
  selector: 'app-header',
  imports: [SiteLogo, DesktopMenu, HeaderCta, CommonModule, Profile],
  templateUrl: './header.html',
  styleUrl: './header.scss',
})
export class Header implements OnInit {

  constructor(private apiService: Api) {};

  private token: string | null = null;
  private adminToken: string | null = null;
  public isLoginPage: boolean = false;
  public hasAValidToken: boolean = false;
  public isDashboardPage: boolean = false;
  public isAdmin: boolean = false;
  public adminEmail: string = '';
  public planId: number = 0;
  public email: string = '';

  ngOnInit(): void {
    const path = window.location.pathname;
    this.isLoginPage = path === '/auth/login' || path === '/auth/signup';
    this.isDashboardPage = path.startsWith('/dashboard') || path.startsWith('/admin/dashboard');

    this.token = localStorage.getItem('access_token');
    this.adminToken = localStorage.getItem('admin_access_token');

    // Vérification synchrone admin : évite le flash CTA si token admin présent
    if (this.adminToken) {
      this.isAdmin = true;
      this.hasAValidToken = true;
      this.adminEmail = localStorage.getItem('admin_email') ?? '';
      this.planId = 999;
    }

    this.apiService.meAdmin(this.adminToken ?? '').subscribe({
      next: (response: any) => {
        this.isAdmin = true;
        this.adminEmail = response.email;
        this.hasAValidToken = true;
        localStorage.setItem('plan_id', '999'); // Plan admin fictif pour badge spécifique
      },
      error: () => {
        this.isAdmin = false;
        this.adminEmail = '';
        localStorage.removeItem('admin_access_token');
        localStorage.removeItem('admin_email');
      }
    });


    // Vérification synchrone : si un token existe, on l'affiche immédiatement
    // sans attendre la réponse réseau (évite le flash CTA → profil)
    if (this.token) {
      this.hasAValidToken = true;
      this.email = localStorage.getItem('user_email') ?? '';
      this.planId = Number(localStorage.getItem('plan_id') ?? null);
    }

    // Appel réseau uniquement si pas de session admin active
    if (!this.adminToken) {
      this.apiService.me(this.token ?? '').subscribe({
        next: (reponse: any) => {
          this.hasAValidToken = true;
          this.email = reponse.email;
          localStorage.setItem('plan_id', reponse.plan_id.toString());
          if (this.planId === null) {
            this.planId = reponse.plan_id;
          }
        },
        error: () => {
          // Token invalide ou expiré : on nettoie et on bascule vers CTA
          localStorage.removeItem('access_token');
          localStorage.removeItem('user_email');
          this.hasAValidToken = false;
          this.email = '';
          localStorage.removeItem('plan_id');
        }
      });
    }
  }
}
