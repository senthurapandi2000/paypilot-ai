
# PayPilot AI

An AI-powered payment operations assistant built for
the PayPal AI Hackathon 2026.

## Overview
PayPilot AI aims to help small businesses manage
invoices, understand transactions, and automate
payment workflows using conversational AI.

## Tech Stack
- Frontend: React + Vite
- Backend: Python + FastAPI
- Payments: PayPal Sandbox REST API

## Current Progress
- [x] React dashboard
- [x] FastAPI backend
- [x] PayPal Sandbox authentication
- [ ] Invoice creation
- [ ] AI agent integration
- [ ] Cloud deployment

## Running Locally

Backend:
cd backend
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload

Frontend:
cd frontend
npm install
npm run dev

Create backend/.env with your own PayPal Sandbox
credentials before testing the integration.

## Status
Under active development. Sandbox testing only.
