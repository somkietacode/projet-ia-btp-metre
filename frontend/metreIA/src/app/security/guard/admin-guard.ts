import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { catchError, map, of } from 'rxjs';
import { Api } from '../../shared/sevice/api';

export const adminGuard: CanActivateFn = (route, state) => {
  const router = inject(Router);
  const api = inject(Api);

  const token = localStorage.getItem('admin_access_token');

  if (!token) {
    return router.createUrlTree(['/auth/admin-login'], {
      queryParams: { returnUrl: state.url },
    });
  }

  return api.meAdmin(token).pipe(
    map(() => true),
    catchError(() => {
      localStorage.removeItem('admin_access_token');
      localStorage.removeItem('admin_email');
      return of(
        router.createUrlTree(['/auth/admin-login'], {
          queryParams: { returnUrl: state.url },
        })
      );
    })
  );
};
