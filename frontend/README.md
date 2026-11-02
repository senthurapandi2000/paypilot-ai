# PayPilot AI — Frontend

React and Vite frontend for the PayPilot AI
conversational invoice assistant.

## Features

- AI-powered invoice preparation
- Invoice preview with human approval
- Advisory duplicate and unusual-amount warnings
- PayPal Sandbox invoice creation
- Invoice history dashboard
- Demo passphrase access

## Technology

- React 19
- Vite
- JavaScript
- CSS
- FastAPI backend integration

## Local Setup

1. Install dependencies:

   npm install

2. Copy .env.example to .env.

3. Set VITE_API_BASE_URL to your backend URL.

4. Start the development server:

   npm run dev

## Validation

Run:

    npm run lint
    npm run build

## Demo

https://paypilot-ai-icx7.onrender.com

This application uses PayPal Sandbox only.
No real payments are processed.

See the repository root README for architecture,
backend setup, evaluation results, and limitations.
