export interface DemoScenario {
  id: string
  label: string
  customerRequest: string
  customerId: string
  orderId: string
}

export const DEMO_SCENARIOS: DemoScenario[] = [
  {
    id: 'replacement',
    label: 'Damaged laptop → replacement',
    customerRequest: 'My laptop arrived damaged and I need a replacement before Friday.',
    customerId: 'CUST-1001',
    orderId: 'ORD-5001',
  },
  {
    id: 'refund-approval',
    label: 'High-value refund → approval',
    customerRequest: 'I want a refund for my damaged laptop.',
    customerId: 'CUST-1002',
    orderId: 'ORD-5002',
  },
  {
    id: 'out-of-stock',
    label: 'Damaged monitor → out of stock',
    customerRequest: 'My monitor arrived damaged. Send a replacement.',
    customerId: 'CUST-1003',
    orderId: 'ORD-5003',
  },
  {
    id: 'expired',
    label: 'Refund from 3 years ago → declined',
    customerRequest: 'Refund my order from three years ago.',
    customerId: 'CUST-1004',
    orderId: 'ORD-5004',
  },
]
