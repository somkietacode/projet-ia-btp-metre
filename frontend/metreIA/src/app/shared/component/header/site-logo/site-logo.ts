import { Component } from '@angular/core';

@Component({
  selector: 'app-site-logo',
  imports: [],
  templateUrl: './site-logo.html',
  styleUrl: './site-logo.scss',
})
export class SiteLogo {
    gotoHome() {
        window.location.href = '/';
    }
}
