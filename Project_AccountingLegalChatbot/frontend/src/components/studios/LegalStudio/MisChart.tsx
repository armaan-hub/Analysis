import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts';

export interface ChartDataPoint {
  period: string;
  revenue?: number;
  expenses?: number;
  profit?: number;
}

interface Props {
  data: ChartDataPoint[];
  type: 'bar' | 'line';
}

export function MisChart({ data, type }: Props) {
  if (!data.length) return null;

  if (type === 'line') {
    return (
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="period" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip />
          <Legend />
          {data.some(d => d.revenue !== undefined) && <Line type="monotone" dataKey="revenue" stroke="#4299e1" />}
          {data.some(d => d.expenses !== undefined) && <Line type="monotone" dataKey="expenses" stroke="#e53e3e" />}
          {data.some(d => d.profit !== undefined) && <Line type="monotone" dataKey="profit" stroke="#38a169" />}
        </LineChart>
      </ResponsiveContainer>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="period" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} />
        <Tooltip />
        <Legend />
        {data.some(d => d.revenue !== undefined) && <Bar dataKey="revenue" fill="#4299e1" />}
        {data.some(d => d.expenses !== undefined) && <Bar dataKey="expenses" fill="#e53e3e" />}
      </BarChart>
    </ResponsiveContainer>
  );
}
