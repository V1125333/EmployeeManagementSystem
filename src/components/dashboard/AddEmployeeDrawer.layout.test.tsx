import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { AddEmployeeDrawer } from '@/components/dashboard/AddEmployeeDrawer';
import { ToastProvider } from '@/components/ui/Toast';

describe('AddEmployeeDrawer layout', () => {
  it('keeps the form inside the drawer without horizontal scrolling', () => {
    const { container } = render(
      <ToastProvider>
        <AddEmployeeDrawer open onClose={vi.fn()} />
      </ToastProvider>,
    );

    const title = screen.getByRole('heading', { name: 'Add Employee' });
    const panel = title.closest('.relative');
    expect(panel).toHaveClass('w-[680px]', 'h-[100dvh]', 'max-w-full', 'overflow-hidden', 'max-sm:!w-full');

    const content = panel?.querySelector('.overflow-y-auto');
    expect(content).toHaveClass('min-w-0', 'overflow-x-hidden');

    const phone = screen.getByPlaceholderText('Enter phone number');
    expect(phone).toHaveClass('min-w-0', 'flex-1');
    expect(phone.parentElement).toHaveClass('min-w-0');

    const responsiveRows = Array.from(container.querySelectorAll('div')).filter((element) =>
      element.className.includes('sm:grid-cols-2'),
    );
    expect(responsiveRows).toHaveLength(6);
    responsiveRows.forEach((row) => expect(row).toHaveClass('grid-cols-1', '[&>*]:min-w-0'));
  });
});
