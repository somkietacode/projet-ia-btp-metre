import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Header } from '../../shared/component/header/header';

@Component({
  selector: 'app-landing-page',
  imports: [Header, RouterLink],
  templateUrl: './landing-page.html',
  styleUrl: './landing-page.scss',
})
export class LandingPage {}
