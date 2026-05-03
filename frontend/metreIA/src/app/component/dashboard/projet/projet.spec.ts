import { ComponentFixture, TestBed } from '@angular/core/testing';

import { Projet } from './projet';

describe('Projet', () => {
  let component: Projet;
  let fixture: ComponentFixture<Projet>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Projet],
    }).compileComponents();

    fixture = TestBed.createComponent(Projet);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
