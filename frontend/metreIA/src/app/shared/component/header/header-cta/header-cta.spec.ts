import { ComponentFixture, TestBed } from '@angular/core/testing';

import { HeaderCta } from './header-cta';

describe('HeaderCta', () => {
  let component: HeaderCta;
  let fixture: ComponentFixture<HeaderCta>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HeaderCta],
    }).compileComponents();

    fixture = TestBed.createComponent(HeaderCta);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
