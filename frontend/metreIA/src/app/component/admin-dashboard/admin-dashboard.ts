import { Component } from '@angular/core';
import { Layout } from '../../shared/component/layout/layout';
import { NavMenu, NavMenuItem } from '../../shared/component/nav-menu/nav-menu';
import { RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-admin-dashboard',
  imports: [Layout, NavMenu, RouterOutlet],
  templateUrl: './admin-dashboard.html',
  styleUrl: './admin-dashboard.scss',
})
export class AdminDashboard {
  public adminMenuItems: NavMenuItem[] = [
    { name: 'accueil',          icon: 'fa-solid fa-house',       route: '/admin/dashboard/home' },
    { name: 'utilisateurs',     icon: 'fa-solid fa-users',       route: '/admin/dashboard/users' },
    { name: 'base documentaire',icon: 'fa-solid fa-book-open',   route: '/admin/dashboard/knowledge-base' },
    { name: 'paramètres',       icon: 'fa-solid fa-gear',        route: '/admin/dashboard/settings' },
  ];
}
