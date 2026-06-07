import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Badge } from '../Badge';

describe('Badge', () => {
  it('renders children correctly', () => {
    render(<Badge>Status</Badge>);
    expect(screen.getByText('Status')).toBeInTheDocument();
  });

  it('applies default variant', () => {
    render(<Badge>Default</Badge>);
    const badge = screen.getByText('Default');
    expect(badge.className).toContain('text-brand-text-maroon');
  });

  it('applies warning variant', () => {
    render(<Badge variant="warning">Warning</Badge>);
    const badge = screen.getByText('Warning');
    expect(badge.className).toContain('text-brand-text-goldDark');
  });

  it('applies ghost variant', () => {
    render(<Badge variant="ghost">Ghost</Badge>);
    const badge = screen.getByText('Ghost');
    expect(badge.className).toContain('text-brand-maroon');
  });

  it('merges custom className', () => {
    render(<Badge className="uppercase">Custom</Badge>);
    expect(screen.getByText('Custom').className).toContain('uppercase');
  });

  it('renders as span element', () => {
    render(<Badge>Span</Badge>);
    expect(screen.getByText('Span').tagName).toBe('SPAN');
  });
});
