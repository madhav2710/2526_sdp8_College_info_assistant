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

    });

    
