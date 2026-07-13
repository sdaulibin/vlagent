import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import BankStatement from '../views/BankStatement.vue'
import DocumentCompare from '../views/DocumentCompare.vue'
import ConfirmationLetter from '../views/ConfirmationLetter.vue'
import FormatCompare from '../views/FormatCompare.vue'
import InvoiceRecognition from '../views/InvoiceRecognition.vue'
import CredentialRecognition from '../views/CredentialRecognition.vue'
import PdfExtract from '../views/PdfExtract.vue'
import FinancialCompare from '../views/FinancialCompare.vue'
import CreditComparisonHome from '../credit_comparison/views/CreditComparisonHome.vue'
import CreditComparisonDetail from '../credit_comparison/views/CreditComparisonDetail.vue'
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
    },
    {
        path: '/financial-compare',
        name: 'FinancialCompare',
        component: FinancialCompare
    },
    {
        path: '/credit-comparison',
        name: 'credit-comparison',
        component: CreditComparisonHome
    },
    {
        path: '/credit-comparison/detail',
        name: 'credit-comparison-detail',
        component: CreditComparisonDetail
    }
]

const router = createRouter({
    history: createWebHistory(import.meta.env.BASE_URL),
    routes
})

// 路由守卫：未认证时重定向到错误页面，无权限时重定向到首页
router.beforeEach(async (to, _from, next) => {
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
        const { hasPermission, loadPermissions } = useUser()
        await loadPermissions()
        const moduleKey = to.path.split('/')[1]
        if (moduleKey && moduleKey !== '' && !hasPermission(moduleKey)) {
            next({ name: 'Home' })
        } else {
            next()
        }
    }
})

export default router
