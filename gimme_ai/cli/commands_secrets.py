"""CLI commands for secrets management."""

import os
import sys
import click
import json
from typing import Optional
from pathlib import Path

from ..config.secrets import get_secrets_manager, SecretBackend, SecretsManager


@click.group(name="secrets")
def secrets_group():
    """Manage secrets and credentials for gimme_ai workflows."""
    pass


@secrets_group.command(name="validate")
@click.option("--environment", "-e", default=None, help="Environment to validate (development/staging/production)")
@click.option("--backend", type=click.Choice(["env_file", "environment", "aws_secrets"]), default="env_file", help="Secret backend to use")
@click.option("--required-only", is_flag=True, help="Only validate required secrets")
@click.option("--quiet", "-q", is_flag=True, help="Only show errors")
def validate_secrets(environment: Optional[str], backend: str, required_only: bool, quiet: bool):
    """Validate all required secrets for current environment."""
    try:
        # Determine environment
        if environment is None:
            environment = os.getenv("GIMME_ENVIRONMENT", "development")
        
        if not quiet:
            click.echo(f"🔍 Validating secrets for environment: {environment}")
            click.echo(f"🔧 Using backend: {backend}")
        
        # Initialize secrets manager
        secrets_manager = get_secrets_manager(
            backend=SecretBackend(backend),
            environment=environment
        )
        
        # Validate secrets
        report = secrets_manager.validate_secrets(required_only=required_only)
        
        if report["valid"]:
            if not quiet:
                click.echo("✅ All required secrets are valid!")
                
                # Show available secrets
                if report["available_secrets"]:
                    click.echo(f"\n📋 Available secrets ({len(report['available_secrets'])}):")
                    for secret in report["available_secrets"]:
                        click.echo(f"  ✅ {secret['name']}: {secret['value']}")
                
                # Show optional missing secrets
                if report["missing_optional"] and not required_only:
                    click.echo(f"\n⚠️  Optional secrets not configured ({len(report['missing_optional'])}):")
                    for secret in report["missing_optional"]:
                        click.echo(f"  • {secret['name']}: {secret['description']}")
        else:
            click.echo("❌ Secret validation failed!")
            
            # Show missing required secrets
            if report["missing_required"]:
                click.echo(f"\n❌ Missing required secrets ({len(report['missing_required'])}):")
                for secret in report["missing_required"]:
                    click.echo(f"  • {secret['name']}: {secret['description']}")
            
            # Show invalid format secrets
            if report["invalid_format"]:
                click.echo(f"\n❌ Invalid secret formats ({len(report['invalid_format'])}):")
                for secret in report["invalid_format"]:
                    click.echo(f"  • {secret['name']}: Expected format {secret['expected_format']}")
            
            sys.exit(1)
    
    except Exception as e:
        click.echo(f"❌ Error validating secrets: {e}", err=True)
        sys.exit(1)


@secrets_group.command(name="template")
@click.option("--environment", "-e", default="development", help="Environment to generate template for")
@click.option("--output", "-o", help="Output file path (default: .env.{environment})")
@click.option("--force", is_flag=True, help="Overwrite existing file")
def generate_template(environment: str, output: Optional[str], force: bool):
    """Generate .env template file for specified environment."""
    try:
        # Determine output file
        if output is None:
            output = f".env.{environment}"
        
        output_path = Path(output)
        
        # Check if file exists
        if output_path.exists() and not force:
            if not click.confirm(f"File {output} already exists. Overwrite?"):
                click.echo("Template generation cancelled.")
                return
        
        click.echo(f"📝 Generating environment template for: {environment}")
        
        # Initialize secrets manager to get template
        secrets_manager = SecretsManager(
            backend=SecretBackend.ENV_FILE,
            environment=environment
        )
        
        # Generate template
        template_content = secrets_manager.generate_env_template(environment)
        
        # Write template file
        with open(output_path, 'w') as f:
            f.write(template_content)
        
        click.echo(f"✅ Template generated: {output_path}")
        click.echo(f"\n📋 Next steps:")
        click.echo(f"   1. Edit {output_path} and add your API keys")
        click.echo(f"   2. Run: gimme-ai secrets validate --environment {environment}")
        click.echo(f"   3. Test workflows: gimme-ai workflow test")
        
    except Exception as e:
        click.echo(f"❌ Error generating template: {e}", err=True)
        sys.exit(1)


@secrets_group.command(name="list")
@click.option("--environment", "-e", default=None, help="Environment to list secrets for")
@click.option("--backend", type=click.Choice(["env_file", "environment", "aws_secrets"]), default="env_file", help="Secret backend to use")
@click.option("--show-values", is_flag=True, help="Show secret values (masked)")
def list_secrets(environment: Optional[str], backend: str, show_values: bool):
    """List all available secrets."""
    try:
        # Determine environment
        if environment is None:
            environment = os.getenv("GIMME_ENVIRONMENT", "development")
        
        click.echo(f"📋 Listing secrets for environment: {environment}")
        
        # Initialize secrets manager
        secrets_manager = get_secrets_manager(
            backend=SecretBackend(backend),
            environment=environment
        )
        
        # Get validation report to show available secrets
        report = secrets_manager.validate_secrets()
        
        if report["available_secrets"]:
            click.echo(f"\n✅ Available secrets ({len(report['available_secrets'])}):")
            for secret in report["available_secrets"]:
                if show_values:
                    click.echo(f"  • {secret['name']}: {secret['value']}")
                else:
                    click.echo(f"  • {secret['name']}: [configured]")
        else:
            click.echo("\n⚠️  No secrets configured")
        
        # Show backend health
        if secrets_manager.health_check():
            click.echo(f"\n🟢 Backend ({backend}) is healthy")
        else:
            click.echo(f"\n🔴 Backend ({backend}) is unhealthy")
        
    except Exception as e:
        click.echo(f"❌ Error listing secrets: {e}", err=True)
        sys.exit(1)


@secrets_group.command(name="test")
@click.option("--environment", "-e", default=None, help="Environment to test")
@click.option("--backend", type=click.Choice(["env_file", "environment", "aws_secrets"]), default="env_file", help="Secret backend to use")
def test_secrets(environment: Optional[str], backend: str):
    """Test secret backend connectivity and basic functionality."""
    try:
        # Determine environment
        if environment is None:
            environment = os.getenv("GIMME_ENVIRONMENT", "development")
        
        click.echo(f"🧪 Testing secrets backend: {backend}")
        click.echo(f"🌍 Environment: {environment}")
        
        # Initialize secrets manager
        secrets_manager = get_secrets_manager(
            backend=SecretBackend(backend),
            environment=environment
        )
        
        # Test health check
        if secrets_manager.health_check():
            click.echo("✅ Backend health check: PASSED")
        else:
            click.echo("❌ Backend health check: FAILED")
            sys.exit(1)
        
        # Test secret retrieval
        test_secret = "OPENAI_API_KEY"
        value = secrets_manager.get_secret(test_secret)
        if value:
            masked_value = f"{value[:4]}***{value[-4:]}" if len(value) > 8 else "***"
            click.echo(f"✅ Secret retrieval test: {test_secret} = {masked_value}")
        else:
            click.echo(f"⚠️  Secret retrieval test: {test_secret} not found (this is OK for testing)")
        
        # Test validation
        report = secrets_manager.validate_secrets()
        click.echo(f"✅ Validation test: {len(report['available_secrets'])} secrets available")
        
        click.echo("\n🎉 All tests passed!")
        
    except Exception as e:
        click.echo(f"❌ Error testing secrets: {e}", err=True)
        sys.exit(1)


@secrets_group.command(name="sync-cloudflare")
@click.option("--environment", "-e", default="production", help="Environment to sync from")
@click.option("--project-name", help="Project name (overrides config)")
@click.option("--secrets", help="Comma-separated list of specific secrets to sync")
@click.option("--dry-run", is_flag=True, help="Show what would be synced without doing it")
@click.option("--force", is_flag=True, help="Skip confirmation prompts")
def sync_cloudflare_secrets(environment: str, project_name: Optional[str], secrets: Optional[str], dry_run: bool, force: bool):
    """Sync local secrets to Cloudflare Workers."""
    try:
        from ..deploy.cloudflare_secrets import CloudflareSecretsManager
        
        # Determine project name
        if not project_name:
            # Try to get from config
            try:
                from ..config import load_config
                config = load_config(".gimme-config.json")
                project_name = config.project_name
            except Exception:
                click.echo("❌ Project name not found. Use --project-name or run from project directory", err=True)
                sys.exit(1)
        
        click.echo(f"🔄 Syncing secrets from {environment} to Cloudflare Workers")
        click.echo(f"📦 Project: {project_name}")
        
        # Parse secrets filter
        secrets_filter = None
        if secrets:
            secrets_filter = [s.strip() for s in secrets.split(",")]
            click.echo(f"🔍 Filtering secrets: {secrets_filter}")
        
        # Initialize manager
        manager = CloudflareSecretsManager(project_name, environment)
        
        # Check wrangler availability
        if not manager.check_wrangler_available():
            click.echo("❌ wrangler CLI not available. Install with: npm install -g wrangler", err=True)
            sys.exit(1)
        
        # Confirm action unless force or dry run
        if not dry_run and not force:
            if not click.confirm(f"Sync secrets from {environment} environment to Cloudflare Workers?"):
                click.echo("Sync cancelled.")
                return
        
        # Perform sync
        results, errors = manager.sync_secrets(secrets_filter, dry_run)
        
        if errors:
            click.echo("\n❌ Errors occurred:")
            for error in errors:
                click.echo(f"  • {error}")
        
        # Show results
        success_count = sum(1 for success in results.values() if success)
        total_count = len(results)
        
        if dry_run:
            click.echo(f"\n📋 Dry run results: {total_count} secrets would be synced")
            for secret_name in results.keys():
                click.echo(f"  • {secret_name}")
        else:
            click.echo(f"\n📊 Sync results: {success_count}/{total_count} successful")
            for secret_name, success in results.items():
                status = "✅" if success else "❌"
                click.echo(f"  {status} {secret_name}")
        
        if errors:
            sys.exit(1)
    
    except Exception as e:
        click.echo(f"❌ Error syncing secrets: {e}", err=True)
        sys.exit(1)


@secrets_group.command(name="check-api")
@click.option("--api", type=click.Choice(["openai", "replicate", "elevenlabs", "all"]), default="all", help="Which API to test")
@click.option("--environment", "-e", default=None, help="Environment to use")
def check_api_keys(api: str, environment: Optional[str]):
    """Test API key validity by making actual API calls."""
    import asyncio
    from ..testing.fixtures import WorkflowTestFixture
    
    async def _test_apis():
        try:
            # Determine environment
            if environment is None:
                env = os.getenv("GIMME_ENVIRONMENT", "development")
            else:
                env = environment
            
            click.echo(f"🔑 Testing API keys for environment: {env}")
            
            # Set up test fixture with real APIs
            fixture = WorkflowTestFixture(
                environment=env,
                use_mock_apis=False,
                use_real_secrets=True
            )
            
            async with fixture.setup():
                apis_to_test = []
                if api in ["openai", "all"]:
                    apis_to_test.append("openai")
                if api in ["replicate", "all"]:
                    apis_to_test.append("replicate")
                if api in ["elevenlabs", "all"]:
                    apis_to_test.append("elevenlabs")
                
                results = {}
                
                for api_name in apis_to_test:
                    click.echo(f"\n🧪 Testing {api_name.upper()} API...")
                    
                    try:
                        if api_name == "openai":
                            workflow = fixture.create_test_workflow("minimal")
                            result = await fixture.execute_workflow(workflow)
                            if result.success:
                                click.echo(f"✅ {api_name.upper()}: API key valid")
                                results[api_name] = "valid"
                            else:
                                click.echo(f"❌ {api_name.upper()}: {result.error}")
                                results[api_name] = "invalid"
                        else:
                            # For other APIs, we'd need specific test workflows
                            click.echo(f"⚠️  {api_name.upper()}: Test not implemented yet")
                            results[api_name] = "not_tested"
                    
                    except Exception as e:
                        click.echo(f"❌ {api_name.upper()}: Error - {e}")
                        results[api_name] = "error"
                
                # Summary
                click.echo(f"\n📊 API Key Test Results:")
                for api_name, status in results.items():
                    status_icon = {"valid": "✅", "invalid": "❌", "error": "💥", "not_tested": "⚠️"}[status]
                    click.echo(f"  {status_icon} {api_name.upper()}: {status}")
                
                # Exit with error if any APIs failed
                if any(status in ["invalid", "error"] for status in results.values()):
                    sys.exit(1)
        
        except Exception as e:
            click.echo(f"❌ Error testing API keys: {e}", err=True)
            sys.exit(1)
    
    # Run async test
    asyncio.run(_test_apis())