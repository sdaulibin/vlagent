import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import BankStatement from '../views/BankStatement.vue'
import ContractCompare from '../views/ContractCompare.vue'
import ConfirmationLetter from '../views/ConfirmationLetter.vue'
import FormatCompare from '../views/FormatCompare.vue'
import InvoiceRecognition from '../views/InvoiceRecognition.vue'
import CredentialRecognition from '../views/CredentialRecognition.vue'
import PdfExtract from '../views/PdfExtract.vue'
import AuthError from '../views/AuthError.vue'
import { isAuthenticated } from '../composables/useAuth'

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
        name: 'ContractCompare',
        component: ContractCompare
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

// 路由守卫：未认证时重定向到错误页面
router.beforeEach((to, _from, next) => {
    if (to.meta.public) {
        next()
    } else if (!isAuthenticated()) {
        next({ name: 'AuthError' })
    } else {
        next()
    }
})

export default router
