import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import BankStatement from '../views/BankStatement.vue'
import ContractCompare from '../views/ContractCompare.vue'
import ConfirmationLetter from '../views/ConfirmationLetter.vue'
import FormatCompare from '../views/FormatCompare.vue'
import InvoiceRecognition from '../views/InvoiceRecognition.vue'
import CredentialRecognition from '../views/CredentialRecognition.vue'

const routes = [
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
    }
]

const router = createRouter({
    history: createWebHistory(),
    routes
})

export default router
