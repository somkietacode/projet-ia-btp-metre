import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';

@Component({
  selector: 'app-badges',
  imports: [ CommonModule ],
  templateUrl: './badges.html',
  styleUrl: './badges.scss',
})
export class Badges {
  @Input() badge_id: number = 0;



}
