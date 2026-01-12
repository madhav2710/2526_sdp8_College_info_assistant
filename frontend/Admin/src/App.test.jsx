import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import App from './App';
import { vi } from 'vitest';

global.fetch = vi.fn();

describe('Admin Dashboard', () => {
  beforeEach(() => {
    fetch.mockClear();
    // Mock localStorage
    const localStorageMock = (function() {
      let store = {};
      return {
        getItem: function(key) {
          return store[key] || null;
        },
        setItem: function(key, value) {
          store[key] = value.toString();
        },
        clear: function() {
          store = {};
        },
        removeItem: function(key) {
          delete store[key];
        }
      };
    })();
    Object.defineProperty(window, 'localStorage', { value: localStorageMock });
    
    // Set mock token to bypass login
    window.localStorage.setItem('admin_token', 'mock-token');

    // Default mock for the initial fetchDocuments call
    fetch.mockResolvedValue({
      ok: true,
      json: async () => [],
    });
  });

  test('renders login screen when not authenticated', () => {
    window.localStorage.removeItem('admin_token');
    render(<App />);
    expect(screen.getByText('Welcome Back')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('admin@college.edu')).toBeInTheDocument();
  });

  test('renders dashboard and navigates to documents tab', () => {
    render(<App />);
    expect(screen.getByText('Admin Overview')).toBeInTheDocument();
    
    // Use regex to be more flexible
    const docsTab = screen.getAllByText(/Documents/i).find(el => el.tagName === 'BUTTON');
    fireEvent.click(docsTab);
    
    expect(screen.getByText('Document Management')).toBeInTheDocument();
  });

  test('calls API on file upload', async () => {
    render(<App />);
    const docsTab = screen.getAllByText(/Documents/i).find(el => el.tagName === 'BUTTON');
    fireEvent.click(docsTab);
    
    const file = new File(['dummy content'], 'test.pdf', { type: 'application/pdf' });
    // Input is inside the component
    // We can find it by type="file"
    const fileInput = document.querySelector('input[type="file"]');
    
    if (!fileInput) throw new Error("File input not found");

    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: 'Upload successful', document_id: '123' }),
    });

        fireEvent.change(fileInput, { target: { files: [file] } });

    

        await waitFor(() => {

            expect(fetch).toHaveBeenCalledWith(

                expect.stringContaining('/admin/upload'),

                expect.objectContaining({

                    method: 'POST',

                    // body should be FormData

                })

            );

        });

      });

    

      test('renders document list with correct status', async () => {

        const mockDocs = [

          { id: '1', filename: 'doc1.pdf', file_type: 'application/pdf', status: 'completed', created_at: '2023-12-01T10:00:00Z' },

          { id: '2', filename: 'doc2.pdf', file_type: 'application/pdf', status: 'pending', created_at: '2023-12-02T10:00:00Z' },

        ];

    

        fetch.mockResolvedValueOnce({

          ok: true,

          json: async () => mockDocs,

        });

    

        render(<App />);

    

        // Switch to documents tab

        const docsTab = screen.getAllByText(/Documents/i).find(el => el.tagName === 'BUTTON');

        fireEvent.click(docsTab);

    

        await waitFor(() => {

          expect(screen.getByText('doc1.pdf')).toBeInTheDocument();

          expect(screen.getByText('doc2.pdf')).toBeInTheDocument();

          expect(screen.getByText('Completed')).toBeInTheDocument();

          expect(screen.getByText('Pending')).toBeInTheDocument();

        });

      });

      test('verifies table layout integrity without action buttons', async () => {
        const mockDocs = [
          { id: '1', filename: 'doc1.pdf', file_type: 'application/pdf', status: 'completed', created_at: '2023-12-01T10:00:00Z' },
          { id: '2', filename: 'doc2.pdf', file_type: 'application/pdf', status: 'pending', created_at: '2023-12-02T10:00:00Z' },
          { id: '3', filename: 'doc3.pdf', file_type: 'application/pdf', status: 'failed', created_at: '2023-12-03T10:00:00Z' },
        ];

        fetch.mockResolvedValueOnce({
          ok: true,
          json: async () => mockDocs,
        });

        render(<App />);

        // Switch to documents tab
        const docsTab = screen.getAllByText(/Documents/i).find(el => el.tagName === 'BUTTON');
        fireEvent.click(docsTab);

        await waitFor(() => {
          // Verify table structure exists
          const table = screen.getByRole('table');
          expect(table).toBeInTheDocument();

          // Verify all expected column headers are present
          expect(screen.getByText('Document Name')).toBeInTheDocument();
          expect(screen.getByText('Type')).toBeInTheDocument();
          expect(screen.getByText('Size')).toBeInTheDocument();
          expect(screen.getByText('Status')).toBeInTheDocument();
          expect(screen.getByText('Upload Date')).toBeInTheDocument();
          expect(screen.getByText('Action')).toBeInTheDocument();

          // Verify table rows are rendered
          const tableRows = screen.getAllByRole('row');
          expect(tableRows).toHaveLength(4); // 1 header + 3 data rows

          // Verify no delete buttons (Trash2 icons) are present by checking for lucide-trash-2 class
          const deleteButtons = document.querySelectorAll('.lucide-trash-2');
          expect(deleteButtons).toHaveLength(0);

          // Verify no action menu buttons (MoreVertical icons) are present by checking for lucide-more-vertical class
          const actionMenuButtons = document.querySelectorAll('.lucide-more-vertical');
          expect(actionMenuButtons).toHaveLength(0);

          // Verify ingest button is present only for pending documents by checking for lucide-refresh-cw class
          const ingestButtons = document.querySelectorAll('.lucide-refresh-cw');
          expect(ingestButtons.length).toBeGreaterThan(0); // Should have at least one for pending document

          // Verify table layout integrity - action column should still exist but only contain ingest buttons for pending docs
          const actionCells = document.querySelectorAll('td:last-child');
          expect(actionCells).toHaveLength(3); // One for each document row
        });
      });

      test('verifies hover states work correctly for remaining buttons', async () => {
        const mockDocs = [
          { id: '1', filename: 'doc1.pdf', file_type: 'application/pdf', status: 'pending', created_at: '2023-12-01T10:00:00Z' },
        ];

        fetch.mockResolvedValueOnce({
          ok: true,
          json: async () => mockDocs,
        });

        render(<App />);

        // Switch to documents tab
        const docsTab = screen.getAllByText(/Documents/i).find(el => el.tagName === 'BUTTON');
        fireEvent.click(docsTab);

        await waitFor(() => {
          // Find the ingest button by looking for the refresh icon and its parent button
          const ingestIcon = document.querySelector('.lucide-refresh-cw');
          expect(ingestIcon).toBeInTheDocument();
          
          const ingestButton = ingestIcon?.closest('button');
          expect(ingestButton).toBeInTheDocument();

          // Verify button has hover classes
          expect(ingestButton).toHaveClass('hover:bg-indigo-50');
          
          // Test hover interaction
          fireEvent.mouseEnter(ingestButton);
          fireEvent.mouseLeave(ingestButton);
          
          // Button should still be functional after hover
          expect(ingestButton).toBeInTheDocument();
        });
      });

      test('verifies table responsive behavior', async () => {
        const mockDocs = [
          { id: '1', filename: 'very-long-document-name-that-might-cause-layout-issues.pdf', file_type: 'application/pdf', status: 'pending', created_at: '2023-12-01T10:00:00Z' },
        ];

        fetch.mockResolvedValueOnce({
          ok: true,
          json: async () => mockDocs,
        });

        render(<App />);

        // Switch to documents tab
        const docsTab = screen.getAllByText(/Documents/i).find(el => el.tagName === 'BUTTON');
        fireEvent.click(docsTab);

        await waitFor(() => {
          // Verify table has overflow handling
          const tableContainer = document.querySelector('.overflow-x-auto');
          expect(tableContainer).toBeInTheDocument();

          // Verify table maintains structure with long content
          const table = screen.getByRole('table');
          expect(table).toHaveClass('w-full');

          // Verify document name is displayed (even if truncated)
          expect(screen.getByText(/very-long-document-name/)).toBeInTheDocument();
        });
      });

      test('verifies search functionality works correctly', async () => {
        const mockDocs = [
          { id: '1', filename: 'syllabus.pdf', file_type: 'application/pdf', status: 'completed', created_at: '2023-12-01T10:00:00Z' },
          { id: '2', filename: 'placement_report.pdf', file_type: 'application/pdf', status: 'pending', created_at: '2023-12-02T10:00:00Z' },
          { id: '3', filename: 'exam_schedule.pdf', file_type: 'application/pdf', status: 'failed', created_at: '2023-12-03T10:00:00Z' },
        ];

        fetch.mockResolvedValueOnce({
          ok: true,
          json: async () => mockDocs,
        });

        render(<App />);

        // Switch to documents tab
        const docsTab = screen.getAllByText(/Documents/i).find(el => el.tagName === 'BUTTON');
        fireEvent.click(docsTab);

        await waitFor(() => {
          // Verify all documents are initially displayed
          expect(screen.getByText('syllabus.pdf')).toBeInTheDocument();
          expect(screen.getByText('placement_report.pdf')).toBeInTheDocument();
          expect(screen.getByText('exam_schedule.pdf')).toBeInTheDocument();
        });

        // Test search functionality
        const searchInput = screen.getByPlaceholderText('Search documents...');
        expect(searchInput).toBeInTheDocument();

        // Search for "syllabus"
        fireEvent.change(searchInput, { target: { value: 'syllabus' } });

        // Only syllabus document should be visible
        expect(screen.getByText('syllabus.pdf')).toBeInTheDocument();
        expect(screen.queryByText('placement_report.pdf')).not.toBeInTheDocument();
        expect(screen.queryByText('exam_schedule.pdf')).not.toBeInTheDocument();

        // Clear search
        fireEvent.change(searchInput, { target: { value: '' } });

        // All documents should be visible again
        await waitFor(() => {
          expect(screen.getByText('syllabus.pdf')).toBeInTheDocument();
          expect(screen.getByText('placement_report.pdf')).toBeInTheDocument();
          expect(screen.getByText('exam_schedule.pdf')).toBeInTheDocument();
        });

        // Test case-insensitive search
        fireEvent.change(searchInput, { target: { value: 'PLACEMENT' } });
        expect(screen.getByText('placement_report.pdf')).toBeInTheDocument();
        expect(screen.queryByText('syllabus.pdf')).not.toBeInTheDocument();
        expect(screen.queryByText('exam_schedule.pdf')).not.toBeInTheDocument();
      });

      test('verifies filter functionality is available', async () => {
        const mockDocs = [
          { id: '1', filename: 'doc1.pdf', file_type: 'application/pdf', status: 'completed', created_at: '2023-12-01T10:00:00Z' },
        ];

        fetch.mockResolvedValueOnce({
          ok: true,
          json: async () => mockDocs,
        });

        render(<App />);

        // Switch to documents tab
        const docsTab = screen.getAllByText(/Documents/i).find(el => el.tagName === 'BUTTON');
        fireEvent.click(docsTab);

        await waitFor(() => {
          // Verify filter button is present
          const filterButton = screen.getByText('Filters');
          expect(filterButton).toBeInTheDocument();
          expect(filterButton.closest('button')).toHaveClass('hover:bg-slate-50');
        });
      });

      test('verifies status badges display correctly for all statuses', async () => {
        const mockDocs = [
          { id: '1', filename: 'completed_doc.pdf', file_type: 'application/pdf', status: 'completed', created_at: '2023-12-01T10:00:00Z' },
          { id: '2', filename: 'pending_doc.pdf', file_type: 'application/pdf', status: 'pending', created_at: '2023-12-02T10:00:00Z' },
          { id: '3', filename: 'failed_doc.pdf', file_type: 'application/pdf', status: 'failed', created_at: '2023-12-03T10:00:00Z' },
          { id: '4', filename: 'processing_doc.pdf', file_type: 'application/pdf', status: 'processing', created_at: '2023-12-04T10:00:00Z' },
        ];

        fetch.mockResolvedValueOnce({
          ok: true,
          json: async () => mockDocs,
        });

        render(<App />);

        // Switch to documents tab
        const docsTab = screen.getAllByText(/Documents/i).find(el => el.tagName === 'BUTTON');
        fireEvent.click(docsTab);

        await waitFor(() => {
          // Verify all status badges are displayed with correct text
          expect(screen.getByText('Completed')).toBeInTheDocument();
          expect(screen.getByText('Pending')).toBeInTheDocument();
          expect(screen.getByText('Failed')).toBeInTheDocument();
          expect(screen.getByText('Processing')).toBeInTheDocument();

          // Verify status badges have correct styling classes
          const completedBadge = screen.getByText('Completed').closest('span');
          expect(completedBadge).toHaveClass('bg-green-100', 'text-green-700', 'border-green-200');

          const pendingBadge = screen.getByText('Pending').closest('span');
          expect(pendingBadge).toHaveClass('bg-yellow-100', 'text-yellow-700', 'border-yellow-200');

          const failedBadge = screen.getByText('Failed').closest('span');
          expect(failedBadge).toHaveClass('bg-red-100', 'text-red-700', 'border-red-200');

          const processingBadge = screen.getByText('Processing').closest('span');
          expect(processingBadge).toHaveClass('bg-blue-100', 'text-blue-700', 'border-blue-200', 'animate-pulse');
        });
      });

      test('verifies ingest functionality for pending documents', async () => {
        const mockDocs = [
          { id: '1', filename: 'pending_doc.pdf', file_type: 'application/pdf', status: 'pending', created_at: '2023-12-01T10:00:00Z' },
          { id: '2', filename: 'completed_doc.pdf', file_type: 'application/pdf', status: 'completed', created_at: '2023-12-02T10:00:00Z' },
        ];

        fetch.mockResolvedValueOnce({
          ok: true,
          json: async () => mockDocs,
        });

        render(<App />);

        // Switch to documents tab
        const docsTab = screen.getAllByText(/Documents/i).find(el => el.tagName === 'BUTTON');
        fireEvent.click(docsTab);

        await waitFor(() => {
          // Verify ingest button is only present for pending documents
          const ingestButtons = document.querySelectorAll('.lucide-refresh-cw');
          expect(ingestButtons).toHaveLength(1); // Only one pending document

          // Find the ingest button and verify it's clickable
          const ingestButton = ingestButtons[0].closest('button');
          expect(ingestButton).toBeInTheDocument();
          expect(ingestButton).toHaveAttribute('title', 'Ingest into ChromaDB');

          // Verify completed document doesn't have ingest button
          const completedRow = screen.getByText('completed_doc.pdf').closest('tr');
          const completedActionCell = completedRow.querySelector('td:last-child');
          const completedIngestButton = completedActionCell.querySelector('.lucide-refresh-cw');
          expect(completedIngestButton).toBeNull();
        });
      });

      test('verifies ingest button functionality and status change', async () => {
        const mockDocs = [
          { id: '1', filename: 'pending_doc.pdf', file_type: 'application/pdf', status: 'pending', created_at: '2023-12-01T10:00:00Z' },
        ];

        fetch.mockResolvedValueOnce({
          ok: true,
          json: async () => mockDocs,
        });

        render(<App />);

        // Switch to documents tab
        const docsTab = screen.getAllByText(/Documents/i).find(el => el.tagName === 'BUTTON');
        fireEvent.click(docsTab);

        await waitFor(() => {
          expect(screen.getByText('Pending')).toBeInTheDocument();
        });

        // Click the ingest button
        const ingestButton = document.querySelector('.lucide-refresh-cw').closest('button');
        fireEvent.click(ingestButton);

        // Verify status changes to "Ingesting" immediately
        await waitFor(() => {
          expect(screen.getByText('Ingesting')).toBeInTheDocument();
        });

        // Wait for the simulated ingestion to complete (3 seconds in the code)
        await waitFor(() => {
          expect(screen.getByText('Ingested')).toBeInTheDocument();
        }, { timeout: 4000 });
      });

      test('verifies document upload functionality is preserved', async () => {
        render(<App />);

        // Switch to documents tab
        const docsTab = screen.getAllByText(/Documents/i).find(el => el.tagName === 'BUTTON');
        fireEvent.click(docsTab);

        // Verify upload area is present and functional - check the parent container with border-dashed
        const uploadContainer = document.querySelector('.border-dashed.border-indigo-200');
        expect(uploadContainer).toBeInTheDocument();

        // Verify upload input is present
        const fileInput = document.querySelector('input[type="file"]');
        expect(fileInput).toBeInTheDocument();
        expect(fileInput).toHaveAttribute('multiple');

        // Verify upload text and instructions
        expect(screen.getByText('Upload College Documents')).toBeInTheDocument();
        expect(screen.getByText(/Drag and drop your syllabus, placement PDFs/)).toBeInTheDocument();
      });

    });

    
