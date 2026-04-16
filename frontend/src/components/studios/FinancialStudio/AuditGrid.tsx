import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  createColumnHelper,
} from '@tanstack/react-table';
import { AlertTriangle, XCircle, CheckCircle } from 'lucide-react';

export interface AuditRow {
  id: string;
  account: string;
  mappedTo: string;
  amount: number;
  status: 'valid' | 'warning' | 'error';
  flagMessage?: string;
  source?: 'ai' | 'user';
}

interface Props {
  rows: AuditRow[];
  onRowsChange: (rows: AuditRow[]) => void;
  onAdvance: () => void;
}

const columnHelper = createColumnHelper<AuditRow>();

export function AuditGrid({ rows, onRowsChange, onAdvance }: Props) {
  // Accept AI suggestion — applies AI's recommended mappedTo value and marks valid
  const acceptSuggestion = (id: string) => {
    onRowsChange(rows.map(r =>
      r.id === id ? { ...r, status: 'valid' as const, flagMessage: undefined, source: 'ai' as const } : r
    ));
  };

  // Override — user manually clears the issue; tracked separately from AI acceptance
  const override = (id: string) => {
    onRowsChange(rows.map(r =>
      r.id === id ? { ...r, status: 'valid' as const, flagMessage: undefined, source: 'user' as const } : r
    ));
  };

  const columns = [
    columnHelper.accessor('account', {
      header: 'Account',
      cell: info => <span style={{ fontFamily: 'var(--s-font-ui)' }}>{info.getValue()}</span>,
    }),
    columnHelper.accessor('mappedTo', {
      header: 'Mapped To',
      cell: info => (
        <span style={{ fontFamily: 'var(--s-font-ui)', color: 'var(--s-text-2)' }}>
          {info.getValue()}
        </span>
      ),
    }),
    columnHelper.accessor('amount', {
      header: 'Amount (AED)',
      cell: info => (
        <span className="audit-amount">
          {info.getValue() === 0
            ? '—'
            : info.getValue().toLocaleString('en-AE', { minimumFractionDigits: 2 })}
        </span>
      ),
    }),
    columnHelper.accessor('status', {
      header: 'Status',
      cell: info => {
        const row = info.row.original;
        if (row.status === 'error') {
          return (
            <div className="audit-flag audit-flag--error">
              <XCircle size={13} />
              <span>{row.flagMessage}</span>
            </div>
          );
        }
        if (row.status === 'warning') {
          return (
            <div className="audit-flag audit-flag--warning">
              <AlertTriangle size={13} />
              <span>{row.flagMessage}</span>
            </div>
          );
        }
        return (
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <CheckCircle size={13} className="audit-ok" />
            {row.source === 'ai' && (
              <span style={{
                fontSize: '10px', fontFamily: 'var(--s-font-ui)', fontWeight: 600,
                color: 'var(--s-success)', background: 'rgba(52,211,153,0.12)',
                border: '1px solid rgba(52,211,153,0.3)',
                borderRadius: '4px', padding: '1px 5px', lineHeight: 1.4,
              }}>AI</span>
            )}
            {row.source === 'user' && (
              <span style={{
                fontSize: '10px', fontFamily: 'var(--s-font-ui)', fontWeight: 600,
                color: 'var(--s-text-2)', background: 'rgba(255,255,255,0.06)',
                border: '1px solid var(--s-border)',
                borderRadius: '4px', padding: '1px 5px', lineHeight: 1.4,
              }}>Manual</span>
            )}
          </div>
        );
      },
    }),
    columnHelper.display({
      id: 'action',
      header: 'Action',
      cell: info => {
        const row = info.row.original;
        if (row.status === 'valid') return null;
        return (
          <div className="audit-actions">
            <button
              className="audit-btn audit-btn--accept"
              onClick={() => acceptSuggestion(row.id)}
            >
              Accept AI
            </button>
            <button
              className="audit-btn audit-btn--override"
              onClick={() => override(row.id)}
            >
              Override
            </button>
          </div>
        );
      },
    }),
  ];

  const table = useReactTable({
    data: rows,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  const errorCount = rows.filter(r => r.status === 'error').length;
  const issueCount = rows.filter(r => r.status !== 'valid').length;

  return (
    <div className="audit-grid-wrap">
      <div className="audit-grid-header">
        <h2 className="audit-grid-title">Validation Grid</h2>
        <span className={`audit-issue-count ${issueCount === 0 ? 'audit-issue-count--none' : ''}`}>
          {issueCount === 0 ? 'All valid' : `${issueCount} issue${issueCount > 1 ? 's' : ''}`}
        </span>
      </div>

      <div className="audit-grid-scroll">
        <table className="audit-table">
          <thead>
            {table.getHeaderGroups().map(hg => (
              <tr key={hg.id}>
                {hg.headers.map(h => (
                  <th key={h.id} className="audit-th">
                    {flexRender(h.column.columnDef.header, h.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map(row => (
              <tr key={row.id} className={`audit-row audit-row--${row.original.status}`}>
                {row.getVisibleCells().map(cell => (
                  <td key={cell.id} className="audit-td">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="audit-grid-footer">
        <button
          className="btn-primary"
          disabled={errorCount > 0}
          onClick={onAdvance}
          title={errorCount > 0 ? 'Resolve all errors before proceeding' : undefined}
        >
          {errorCount > 0 ? `Resolve ${errorCount} error${errorCount > 1 ? 's' : ''} first` : 'Proceed to Export'}
        </button>
      </div>
    </div>
  );
}
