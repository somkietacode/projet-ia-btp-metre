import { ComponentFixture, TestBed } from '@angular/core/testing';

import { AdimLogin } from './adim-login';

describe('AdimLogin', () => {
  let component: AdimLogin;
  let fixture: ComponentFixture<AdimLogin>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AdimLogin],
    }).compileComponents();

    fixture = TestBed.createComponent(AdimLogin);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
