import { ComponentFixture, TestBed } from '@angular/core/testing';

import { DesktopMenu } from './desktop-menu';

describe('DesktopMenu', () => {
  let component: DesktopMenu;
  let fixture: ComponentFixture<DesktopMenu>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DesktopMenu],
    }).compileComponents();

    fixture = TestBed.createComponent(DesktopMenu);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
