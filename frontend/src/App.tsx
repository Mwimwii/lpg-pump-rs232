import { useEffect, useState } from 'react'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

interface Transaction {
  id: number
  scale_id: number
  operator_id: number
  initial_mass: number
  tare_mass: number
  fill_mass: number
  last_measurement: number
  fill_sequence: number
  status_code: number
  created_at: string
}

const STATUS_CODES: Record<number, string> = {
  8: 'Idle',
  16: 'Tare Entered',
  24: 'Tare Error',
  32: 'Fill Entered',
  40: 'Pumping',
  48: 'Fill Error',
  56: 'Fill Complete',
  64: 'Zeroing',
}

function getStatusText(code: number): string {
  const base = code & 0xf8
  return STATUS_CODES[base] || `Unknown (${code})`
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString()
}

function App() {
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchTransactions = async () => {
    try {
      const res = await fetch('/transactions')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setTransactions(data)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchTransactions()
    const interval = setInterval(fetchTransactions, 5000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="container mx-auto p-4">
      <h1 className="text-2xl font-bold mb-4">LPG Transactions</h1>

      {loading && <p className="text-muted-foreground">Loading...</p>}
      {error && <p className="text-destructive">Error: {error}</p>}

      {!loading && !error && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>ID</TableHead>
              <TableHead>Date</TableHead>
              <TableHead>Operator</TableHead>
              <TableHead>Initial (kg)</TableHead>
              <TableHead>Tare (kg)</TableHead>
              <TableHead>Fill (kg)</TableHead>
              <TableHead>Last (kg)</TableHead>
              <TableHead>Seq</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {transactions.length === 0 ? (
              <TableRow>
                <TableCell colSpan={9} className="text-center text-muted-foreground">
                  No transactions
                </TableCell>
              </TableRow>
            ) : (
              transactions.map((t) => (
                <TableRow key={t.id}>
                  <TableCell>{t.id}</TableCell>
                  <TableCell>{formatDate(t.created_at)}</TableCell>
                  <TableCell>{t.operator_id}</TableCell>
                  <TableCell>{t.initial_mass.toFixed(2)}</TableCell>
                  <TableCell>{t.tare_mass.toFixed(2)}</TableCell>
                  <TableCell>{t.fill_mass.toFixed(2)}</TableCell>
                  <TableCell>{t.last_measurement.toFixed(2)}</TableCell>
                  <TableCell>{t.fill_sequence}</TableCell>
                  <TableCell>{getStatusText(t.status_code)}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      )}
    </div>
  )
}

export default App
