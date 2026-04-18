export type OutputType =
  | 'audit_report'
  | 'profit_loss'
  | 'balance_sheet'
  | 'cash_flow'
  | 'tax_schedule'
  | 'management_report'
  | 'custom';

export interface AuditProfile {
  id: string;
  engagement_name: string;
  created_at: string;
}

export interface ProfileVersion {
  id: string;
  branch_name: string;
  is_current: boolean;
  created_at: string;
}

export interface SourceDoc {
  id: string;
  document_type: string;
  original_filename: string;
  confidence: number | null;
  status: 'uploaded' | 'extracting' | 'ready' | 'failed' | 'extracted' | 'error';
}

export interface ChatCitation { doc_id: string; page?: number; excerpt?: string; }

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations: ChatCitation[];
  created_at: string;
}

export interface GeneratedOutput {
  id: string;
  output_type: OutputType;
  status: 'pending' | 'processing' | 'ready' | 'failed';
  download_url: string | null;
  error_message: string | null;
  created_at: string;
}

export type WorkflowStep = 1 | 2 | 3 | 4 | 5;
