import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { catchError, map, of } from 'rxjs';
import { Api } from '../../shared/sevice/api';

export const dashboardGuard: CanActivateFn = (route, state) => {
  const router = inject(Router);
  const api = inject(Api);

  const token = localStorage.getItem('access_token');

  if (!token) {
    return router.createUrlTree(['/auth/login'], {
      queryParams: { returnUrl: state.url },
    });
  }

  return api.me(token).pipe(
    map(() => true),
    catchError(() => {
      localStorage.removeItem('access_token');
      localStorage.removeItem('user_email');
      return of(
        router.createUrlTree(['/auth/login'], {
          queryParams: { returnUrl: state.url },
        })
      );
    })
  );
};
