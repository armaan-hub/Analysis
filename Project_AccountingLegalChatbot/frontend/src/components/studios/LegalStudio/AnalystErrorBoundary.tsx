import React from 'react';

interface State { hasError: boolean; error: Error | null; }
interface Props { children: React.ReactNode; onReset?: () => void; }

export class AnalystErrorBoundary extends React.Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('[AnalystErrorBoundary]', error, info);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
    this.props.onReset?.();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="analyst-error-boundary" role="alert" style={{ padding: 24 }}>
          <h3 style={{ color: '#9b2226', marginBottom: 8 }}>Analyst mode crashed</h3>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12, color: '#555', marginBottom: 16 }}>
            {this.state.error?.message}
          </pre>
          <button type="button" onClick={this.handleReset} className="btn-secondary">
            Reset Analyst
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
