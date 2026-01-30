# SynonymSeeker

A LinkedIn-style word puzzle game built with AWS Strands multi-agent system for learning purposes.

## Architecture

- **Frontend**: Vue.js 3 with TypeScript
- **Backend**: Python Lambda functions using AWS Strands agents
- **Communication**: Agent2Agent (A2A) protocol
- **Deployment**: S3 + CloudFront + Lambda Function URLs

## Project Structure

```
├── frontend/           # Vue.js frontend application
├── backend/           # Python Lambda functions
├── infrastructure/    # AWS SAM templates
└── docs/             # Documentation
```

## Development Setup

### Prerequisites

- Node.js 22+
- Python 3.11+
- AWS CLI configured

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### Backend Setup

```bash
cd backend
pip install -r requirements.txt
```

### Testing

```bash
# Frontend tests
cd frontend
npm test

# Backend tests
cd backend
pytest
```

## AWS Commands Needed

*Will be documented as deployment infrastructure is created*

## Learning Objectives

This project demonstrates:
- AWS Strands multi-agent coordination
- Agent2Agent (A2A) protocol usage
- Property-based testing for correctness
- Cost-effective serverless architecture