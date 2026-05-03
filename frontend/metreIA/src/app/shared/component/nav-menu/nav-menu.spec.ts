import { ComponentFixture, TestBed } from '@angular/core/testing';

import { NavMenu } from './nav-menu';

describe('NavMenu', () => {
  let component: NavMenu;
  let fixture: ComponentFixture<NavMenu>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [NavMenu],
    }).compileComponents();

    fixture = TestBed.createComponent(NavMenu);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
