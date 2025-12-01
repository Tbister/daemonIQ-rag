# Data Directory

This directory contains source documents for the DaemonIQ RAG system.

## Purpose

Store Building Automation System (BAS) technical documentation here for ingestion into the vector database. The system supports:

- **PDF files** (.pdf) - Technical manuals, installation guides
- **Text files** (.txt) - Plain text documentation
- **Markdown files** (.md) - Formatted documentation

## Usage

### Adding Documents

1. Copy PDF/TXT/MD files into this directory
2. Run ingestion: `make ingest`
3. The system automatically detects and indexes new files only (incremental)

### Supported Content

- Product installation guides
- User manuals
- Technical reference documentation
- Function block guides
- Engineering tool documentation

## Important Notes

⚠️ **Files in this directory are NOT committed to version control**

- PDF files can be large (10-30MB each)
- They are automatically excluded via `.gitignore`
- Store source documents in:
  - Shared network drive
  - Cloud storage (S3, Azure Blob, etc.)
  - Separate documentation repository

## Current State

This directory is intentionally empty in the git repository. After cloning:

1. Add your BAS documentation files here
2. Run `make ingest` to populate the vector database
3. Query the system via API or web interface

## File Management

The ingestion system tracks which files have been indexed. You can:

- **Add new files** - Only new documents will be processed
- **Update files** - Run `make ingest-rebuild` to reprocess everything
- **Remove files** - Delete from directory, then rebuild if needed

For questions, see `QUICKSTART.md` or `README.md` in the project root.
