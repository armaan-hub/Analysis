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
          {data[0].revenue !== undefined && <Line type="monotone" dataKey="revenue" stroke="#4299e1" />}
          {data[0].expenses !== undefined && <Line type="monotone" dataKey="expenses" stroke="#e53e3e" />}
          {data[0].profit !== undefined && <Line type="monotone" dataKey="profit" stroke="#38a169" />}
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
        {data[0].revenue !== undefined && <Bar dataKey="revenue" fill="#4299e1" />}
        {data[0].expenses !== undefined && <Bar dataKey="expenses" fill="#e53e3e" />}
      </BarChart>
    </ResponsiveContainer>
  );
}
