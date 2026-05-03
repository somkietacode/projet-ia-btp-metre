import { Routes } from '@angular/router';
import { dashboardGuard } from './security/guard/dashboard-guard';
import { adminGuard } from './security/guard/admin-guard';
import { LandingPage } from './component/landing-page/landing-page';
import { Login } from './component/auth/login/login';
import { Signup } from './component/auth/signup/signup';
import { Dashboard } from './component/dashboard/dashboard';
import { TableauDeBord } from './component/dashboard/tableau-de-bord/tableau-de-bord';
import { Projet } from './component/dashboard/projet/projet';
import { ProjetNew } from './component/dashboard/projet/projet-new/projet-new';
import { ProjetDetail } from './component/dashboard/projet/projet-detail/projet-detail';
import { AdimLogin } from './component/auth/adim-login/adim-login';
import { AdminDashboard } from './component/admin-dashboard/admin-dashboard';
import { AdminHome } from './component/admin-dashboard/admin-home/admin-home';
import { AdminUsers } from './component/admin-dashboard/admin-users/admin-users';
import { AdminKnowledgeBase } from './component/admin-dashboard/admin-knowledge-base/admin-knowledge-base';
import { UserKnowledgeBase } from './component/dashboard/user-knowledge-base/user-knowledge-base';
import { Questions } from './component/dashboard/questions/questions';

export const routes: Routes = [
    {
        path: '',
        component: LandingPage
    }, {
        path: 'auth/login',
        component: Login
    }, {
        path: 'auth/signup',
        component: Signup
    }, {
        path: 'auth/admin-login',
        component: AdimLogin
    }, {
        path: 'dashboard',
        redirectTo: 'dashboard/home',
        pathMatch: 'full'
    },
    {
        path: 'dashboard',
        component: Dashboard,
        canActivate: [dashboardGuard],
        children: [
            {
                path: 'home',
                component: TableauDeBord
            }, {
                path: 'projects',
                component: Projet
            }, {
                path: 'projects/new',
                component: ProjetNew
            }, {
                path: 'projects/:id',
                component: ProjetDetail
            }, {
                path: 'knowledge-base',
                component: UserKnowledgeBase
            }, {
                path: 'questions',
                component: Questions
            }
        ]
    }, {
        path: 'admin/dashboard',
        redirectTo: 'admin/dashboard/home',
        pathMatch: 'full'
    },
    {
        path: 'admin/dashboard',
        component: AdminDashboard,
        canActivate: [adminGuard],
        children: [
            {
                path: 'home',
                component: AdminHome
            }, {
                path: 'users',
                component: AdminUsers
            }, {
                path: 'knowledge-base',
                component: AdminKnowledgeBase
            }
        ]
    }
];
