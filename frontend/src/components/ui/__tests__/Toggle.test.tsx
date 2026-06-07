import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Toggle } from '../Toggle';

describe('Toggle', () => {
  it('renders with role="switch"', () => {
    render(<Toggle active={false} onToggle={() => {}} label="Test toggle" />);
    expect(screen.getByRole('switch')).toBeInTheDocument();
  });

  it('has aria-checked=false when inactive', () => {
    render(<Toggle active={false} onToggle={() => {}} label="Test toggle" />);
    expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'false');
  });

  it('has aria-checked=true when active', () => {
    render(<Toggle active={true} onToggle={() => {}} label="Test toggle" />);
    expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'true');
  });

  it('has aria-label for accessibility', () => {
    render(<Toggle active={false} onToggle={() => {}} label="Enable OCR" />);
    expect(screen.getByRole('switch')).toHaveAttribute('aria-label', 'Enable OCR');
  });

  it('calls onToggle when clicked', async () => {
    const user = userEvent.setup();
    let toggled = false;
    render(<Toggle active={false} onToggle={() => { toggled = true; }} label="Test" />);
    await user.click(screen.getByRole('switch'));
    expect(toggled).toBe(true);
  });

  it('applies active style when active', () => {
    render(<Toggle active={true} onToggle={() => {}} label="Test" />);
    expect(screen.getByRole('switch').className).toContain('bg-brand-maroon');
  });

  it('applies inactive style when inactive', () => {
    render(<Toggle active={false} onToggle={() => {}} label="Test" />);
    expect(screen.getByRole('switch').className).toContain('bg-gray-300');
  });

  it('has type="button" to prevent form submission', () => {
    render(<Toggle active={false} onToggle={() => {}} label="Test" />);
    expect(screen.getByRole('switch')).toHaveAttribute('type', 'button');
  });

  it('has focus-visible ring for accessibility', () => {
    render(<Toggle active={false} onToggle={() => {}} label="Test" />);
    expect(screen.getByRole('switch').className).toContain('focus-visible:ring');
  });
});
