import { Component } from '@angular/core';
import { Layout } from '../../shared/component/layout/layout';
import { NavMenu } from '../../shared/component/nav-menu/nav-menu';
import { RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-dashboard',
  imports: [Layout, NavMenu, RouterOutlet],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.scss',
})
export class Dashboard {}
