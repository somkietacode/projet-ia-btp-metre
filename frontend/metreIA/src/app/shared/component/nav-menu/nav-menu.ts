import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { Router, RouterLink, RouterLinkActive } from '@angular/router';

export interface NavMenuItem {
  name: string;
  icon: string;
  route: string;
}

@Component({
  selector: 'app-nav-menu',
  imports: [CommonModule, RouterLink, RouterLinkActive],
  templateUrl: './nav-menu.html',
  styleUrl: './nav-menu.scss',
})
export class NavMenu {
  public isCollapsed: boolean = false;

  constructor(public router: Router) {}

  @Input() menuItems: NavMenuItem[] = [
    { name : 'acceuil', icon: 'fa-solid fa-house', route: '/dashboard/home' },
    { name : 'projet', icon: 'fa-solid fa-diagram-project', route: '/dashboard/projects' },
    { name : 'questions', icon: 'fa-solid fa-circle-question', route: '/dashboard/questions' },
    { name : 'documents', icon: 'fa-solid fa-book', route: '/dashboard/knowledge-base' },
    { name : 'materiaux', icon: 'fa-solid fa-cubes', route: '/dashboard/materials' },
    { name : 'parametres', icon: 'fa-solid fa-gear', route: '/dashboard/settings' },
  ];

  toggleMenu(): void {
    this.isCollapsed = !this.isCollapsed;
  }
}
