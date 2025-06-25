# 📚 gimme_ai Documentation Guide

Welcome to gimme_ai - the production-ready API gateway and workflow orchestration platform for AI services.

## 🚀 Quick Start

**New Users**: Start with [README.md](README.md) for overview and examples  
**Production Setup**: Follow [PRODUCTION_READY_SETUP.md](PRODUCTION_READY_SETUP.md) for complete deployment  
**Developers**: Check [CLAUDE.md](CLAUDE.md) for development commands and architecture

## 📋 Documentation Structure

### Primary Documentation
| File | Purpose | Audience |
|------|---------|----------|
| [README.md](README.md) | Project overview, features, examples | All users |
| [PRODUCTION_READY_SETUP.md](PRODUCTION_READY_SETUP.md) | Complete production deployment guide | DevOps, Production users |
| [CLAUDE.md](CLAUDE.md) | Development commands, architecture, CLI reference | Developers, Contributors |

### Archive
Historical documentation moved to `docs_archive/`:
- `derivativ_integration/` - Original Derivativ integration specs (now implemented)
- `SETUP_GUIDE.md` - Legacy content creation setup guide (superseded by main docs)

## 🎯 What's New (Latest Implementation)

### ✅ Advanced Workflow Engine
- **Singapore Timezone Scheduler**: Automatic SGT to UTC conversion for Cloudflare Workers
- **Derivativ Templates**: Cambridge IGCSE question generation workflows
- **Multi-API Orchestration**: OpenAI, Replicate, ElevenLabs, R2 storage integration
- **Dependency Management**: Sequential and parallel execution with proper error handling

### ✅ CLI Enhancements
- `gimme-ai wf` - Advanced workflow commands
- `gimme-ai secrets` - Multi-environment secrets management  
- Comprehensive testing suite with 75+ passing tests

### ✅ Production Features
- File upload/download operations
- Response transformation with Jinja2 templates
- Async job polling (Replicate-style APIs)
- Configurable retry logic with exponential backoff

## 🧭 Navigation Guide

**I want to...**

- **Get started quickly** → [README.md](README.md) Quick Start section
- **Deploy to production** → [PRODUCTION_READY_SETUP.md](PRODUCTION_READY_SETUP.md)
- **Understand the architecture** → [CLAUDE.md](CLAUDE.md) Architecture Overview
- **See workflow examples** → [README.md](README.md) Workflow Examples section
- **Set up Derivativ integration** → [PRODUCTION_READY_SETUP.md](PRODUCTION_READY_SETUP.md) Workflow Management section
- **Contribute to development** → [CLAUDE.md](CLAUDE.md) Development Commands
- **Troubleshoot issues** → [PRODUCTION_READY_SETUP.md](PRODUCTION_READY_SETUP.md) Troubleshooting section

## 🔧 Quick Reference

### Most Common Commands
```bash
# Project setup
gimme-ai init
gimme-ai deploy

# Workflow management
gimme-ai wf init --name my-workflow --template content-creation
gimme-ai wf execute workflow.yaml --env-file .env

# Testing
gimme-ai test-all
python -m pytest tests/unit/utils/test_singapore_scheduler.py -v
```

### Key Files & Locations
- **Main CLI**: `gimme_ai/cli/commands.py`
- **Workflow Engine**: `gimme_ai/workflows/execution_engine.py`
- **Singapore Scheduler**: `gimme_ai/utils/singapore_scheduler.py`
- **Derivativ Templates**: `gimme_ai/config/derivativ_templates.py`
- **Examples**: `examples/` directory
- **Tests**: `tests/unit/` and `tests/integration/`

---

**Status**: All features implemented and production-ready ✅  
**Last Updated**: Current implementation (Singapore scheduler + Derivativ templates completed)  
**Test Coverage**: 75+ tests passing with comprehensive coverage