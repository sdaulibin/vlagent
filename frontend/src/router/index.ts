import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import BankStatement from '../views/BankStatement.vue'
import DocumentCompare from '../views/DocumentCompare.vue'
import ConfirmationLetter from '../views/ConfirmationLetter.vue'
import FormatCompare from '../views/FormatCompare.vue'
import InvoiceRecognition from '../views/InvoiceRecognition.vue'
import CredentialRecognition from '../views/CredentialRecognition.vue'
import PdfExtract from '../views/PdfExtract.vue'
import AuthError from '../views/AuthError.vue'
import { isAuthenticated } from '../composables/useAuth'
import { useUser } from '../composables/useUser'

const routes = [
    {
        path: '/auth-error',
        name: 'AuthError',
        component: AuthError,
        meta: { public: true }
    },
    {
        path: '/',
        name: 'Home',
        component: Home
    },
    {
        path: '/bank-statement',
        name: 'BankStatement',
        component: BankStatement
    },
    {
        path: '/contract-compare',
        redirect: '/document-compare'
    },
    {
        path: '/document-compare',
        name: 'DocumentCompare',
        component: DocumentCompare
    },
    {
        path: '/confirmation-letter',
        name: 'ConfirmationLetter',
        component: ConfirmationLetter
    },
    {
        path: '/format-compare',
        name: 'FormatCompare',
        component: FormatCompare
    },
    {
        path: '/invoice-recognition',
        name: 'InvoiceRecognition',
        component: InvoiceRecognition
    },
    {
        path: '/credential-recognition',
        name: 'CredentialRecognition',
        component: CredentialRecognition
    },
    {
        path: '/pdf-extract',
        name: 'PdfExtract',
        component: PdfExtract
    }
]

const router = createRouter({
    history: createWebHistory(),
    routes
})

// 路由守卫：未认证时重定向到错误页面，无权限时重定向到首页
router.beforeEach((to, _from, next) => {
    if (to.meta.public) {
        next()
    } else if (!isAuthenticated()) {
        // 跳转前先把 URL 中的 token 存入 sessionStorage，防止路由跳转后丢失
        const tokenParam = to.query.token as string | undefined
        if (tokenParam) {
            sessionStorage.setItem('vlagent_token', tokenParam)
        }
        next({ name: 'AuthError' })
    } else {
        const { hasPermission, permissionsLoaded } = useUser()
        const moduleKey = to.path.slice(1)
        if (permissionsLoaded.value && moduleKey && moduleKey !== '' && !hasPermission(moduleKey)) {
            next({ name: 'Home' })
        } else {
            next()
        }
    }
})

export default router
