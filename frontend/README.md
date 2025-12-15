# SDP Frontend

A React application with shadcn-style components, Tailwind CSS, and JSX.

## Project Structure

This project follows the shadcn/ui structure:
- `/src/components/ui` - Reusable UI components (shadcn-style)
- `/src/lib` - Utility functions
- `/src/components` - Application components

## Setup Instructions

### 1. Install Dependencies

```bash
cd frontend
npm install
```

### 2. Run Development Server

```bash
npm run dev
```

The app will be available at `http://localhost:5173`

### 3. Build for Production

```bash
npm run build
```

## Components

### PromptSuggestion Component

Located at `/src/components/ui/prompt-suggestion.jsx`

A flexible button component that supports:
- Regular button mode with outline variant
- Highlight mode for search/filter functionality
- Customizable variants and sizes

### PromptInput Component

Located at `/src/components/ui/prompt-input.jsx`

A composable input component with:
- Textarea input
- Action buttons area
- Enter key submission support

## Dependencies

- **React** - UI library
- **Tailwind CSS** - Styling
- **class-variance-authority** - Component variant management
- **@radix-ui/react-slot** - Polymorphic component support
- **lucide-react** - Icons
- **clsx** & **tailwind-merge** - Utility for className merging

## Why `/components/ui` Folder?

The `/components/ui` folder is the standard location for shadcn/ui components. This structure:
- Keeps UI components separate from application-specific components
- Makes it easy to add more shadcn components in the future
- Follows the shadcn CLI convention
- Improves code organization and maintainability

