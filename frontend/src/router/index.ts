import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import BankStatement from '../views/BankStatement.vue'
import ContractCompare from '../views/ContractCompare.vue'

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
    }
]

const router = createRouter({
    history: createWebHistory(),
    routes
})

export default router
