"""
TDD tests for Derivativ-specific workflow templates.
Tests template generation, validation, and Cambridge IGCSE question workflows.
"""

import pytest
from datetime import datetime
from gimme_ai.config.derivativ_templates import (
    DerivativTemplateGenerator,
    CambridgeIGCSETopics,
    generate_derivativ_daily_workflow,
    generate_cambridge_question_workflow,
    validate_derivativ_config,
    get_available_templates,
    DERIVATIV_TEMPLATE_CONFIGS
)


class TestCambridgeIGCSETopics:
    """Test Cambridge IGCSE topics and grade level validation."""
    
    def test_available_topics_structure(self):
        """Test that Cambridge IGCSE topics are properly structured."""
        topics = CambridgeIGCSETopics()
        
        # Test core subjects are available
        assert "mathematics" in topics.get_all_subjects()
        assert "english" in topics.get_all_subjects()
        assert "physics" in topics.get_all_subjects()
        assert "chemistry" in topics.get_all_subjects()
        assert "biology" in topics.get_all_subjects()
    
    def test_mathematics_topics(self):
        """Test mathematics topic structure."""
        topics = CambridgeIGCSETopics()
        math_topics = topics.get_subject_topics("mathematics")
        
        # Expected core mathematics topics
        expected_topics = [
            "algebra", "geometry", "statistics", "probability",
            "number_theory", "calculus_basics", "trigonometry"
        ]
        
        for topic in expected_topics:
            assert topic in math_topics
    
    def test_grade_level_validation(self):
        """Test grade level validation for IGCSE."""
        topics = CambridgeIGCSETopics()
        
        # Valid IGCSE grade levels (typically 9-11)
        assert topics.validate_grade_level(9) == True
        assert topics.validate_grade_level(10) == True
        assert topics.validate_grade_level(11) == True
        
        # Invalid grade levels
        assert topics.validate_grade_level(7) == False
        assert topics.validate_grade_level(8) == False
        assert topics.validate_grade_level(12) == False
    
    def test_topic_difficulty_mapping(self):
        """Test topic difficulty is properly mapped."""
        topics = CambridgeIGCSETopics()
        
        # Test difficulty levels exist for mathematics
        math_topics = topics.get_subject_topics("mathematics")
        for topic in math_topics:
            difficulty = topics.get_topic_difficulty("mathematics", topic)
            assert difficulty in ["basic", "intermediate", "advanced"]
    
    def test_questions_per_topic_recommendations(self):
        """Test recommended questions per topic."""
        topics = CambridgeIGCSETopics()
        
        # Default recommendations should exist
        recommendation = topics.get_questions_per_topic_recommendation("mathematics", "algebra")
        assert isinstance(recommendation, int)
        assert 5 <= recommendation <= 15  # Reasonable range


class TestDerivativTemplateGenerator:
    """Test the main Derivativ template generator."""
    
    def test_generator_initialization(self):
        """Test generator initializes with correct defaults."""
        generator = DerivativTemplateGenerator()
        
        assert generator.default_grade_level == 9
        assert generator.default_questions_per_topic == 8
        assert generator.default_quality_threshold == 0.75
        assert generator.schedule_time == "02:00"  # 2 AM SGT
    
    def test_generator_custom_initialization(self):
        """Test generator with custom parameters."""
        generator = DerivativTemplateGenerator(
            grade_level=10,
            questions_per_topic=12,
            quality_threshold=0.8,
            schedule_time="03:00"
        )
        
        assert generator.default_grade_level == 10
        assert generator.default_questions_per_topic == 12
        assert generator.default_quality_threshold == 0.8
        assert generator.schedule_time == "03:00"
    
    def test_generate_daily_workflow_basic(self):
        """Test basic daily workflow generation."""
        generator = DerivativTemplateGenerator()
        
        # Generate workflow for 3 subjects
        subjects = ["mathematics", "physics", "chemistry"]
        workflow = generator.generate_daily_workflow(subjects)
        
        # Basic structure validation
        assert workflow["name"] == "derivativ_cambridge_igcse_daily"
        assert workflow["schedule"] == "0 18 * * *"  # 2 AM SGT = 6 PM UTC
        assert workflow["timezone"] == "Asia/Singapore"
        assert "api_base" in workflow
        assert "auth" in workflow
        assert "variables" in workflow
        assert "steps" in workflow
        assert "monitoring" in workflow
    
    def test_generate_daily_workflow_variables(self):
        """Test workflow variables are properly set."""
        generator = DerivativTemplateGenerator()
        subjects = ["mathematics", "physics"]
        
        workflow = generator.generate_daily_workflow(subjects)
        variables = workflow["variables"]
        
        assert variables["topics"] == subjects
        assert variables["questions_per_topic"] == 8
        assert variables["grade_level"] == 9
        assert variables["quality_threshold"] == 0.75
        assert "total_target" in variables
        assert "request_id" in variables
        assert "workflow_date" in variables
    
    def test_generate_daily_workflow_steps_structure(self):
        """Test workflow steps are properly structured."""
        generator = DerivativTemplateGenerator()
        subjects = ["mathematics", "physics", "chemistry"]
        
        workflow = generator.generate_daily_workflow(subjects)
        steps = workflow["steps"]
        
        # Should have steps for each subject + document generation + storage
        expected_step_count = len(subjects) + 3  # subjects + worksheet + answer_key + storage
        assert len(steps) >= expected_step_count
        
        # Check for parallel question generation steps
        question_steps = [step for step in steps if step["name"].startswith("generate_")]
        assert len(question_steps) == len(subjects)
        
        for step in question_steps:
            assert step.get("parallel_group") == "question_generation"
            assert "retry" in step
            assert step["method"] == "POST"
            assert step["endpoint"] == "/api/questions/generate"
    
    def test_generate_daily_workflow_dependencies(self):
        """Test workflow dependencies are correctly set."""
        generator = DerivativTemplateGenerator()
        subjects = ["mathematics", "physics"]
        
        workflow = generator.generate_daily_workflow(subjects)
        steps = workflow["steps"]
        
        # Find document generation steps
        worksheet_step = next(step for step in steps if step["name"] == "create_worksheet")
        answer_key_step = next(step for step in steps if step["name"] == "create_answer_key")
        storage_step = next(step for step in steps if step["name"] == "store_documents")
        
        # Document steps should depend on all question generation
        expected_deps = [f"generate_{subject}_questions" for subject in subjects]
        assert set(worksheet_step["depends_on"]) >= set(expected_deps)
        assert set(answer_key_step["depends_on"]) >= set(expected_deps)
        
        # Storage should depend on document creation
        assert "create_worksheet" in storage_step["depends_on"]
        assert "create_answer_key" in storage_step["depends_on"]


class TestWorkflowGeneration:
    """Test specific workflow generation functions."""
    
    def test_generate_derivativ_daily_workflow_function(self):
        """Test the standalone daily workflow generation function."""
        config = {
            "subjects": ["mathematics", "physics"],
            "grade_level": 10,
            "questions_per_topic": 6,
            "api_base": "https://api.derivativ.ai",
            "api_key": "test-key-123"
        }
        
        workflow = generate_derivativ_daily_workflow(config)
        
        assert workflow["name"] == "derivativ_cambridge_igcse_daily"
        assert workflow["variables"]["grade_level"] == 10
        assert workflow["variables"]["questions_per_topic"] == 6
        assert workflow["api_base"] == "https://api.derivativ.ai"
        assert workflow["auth"]["token"] == "test-key-123"
    
    def test_generate_cambridge_question_workflow(self):
        """Test Cambridge-specific question workflow generation."""
        config = {
            "subject": "mathematics",
            "topics": ["algebra", "geometry"],
            "grade_level": 9,
            "question_count": 20,
            "api_base": "https://api.derivativ.ai"
        }
        
        workflow = generate_cambridge_question_workflow(config)
        
        assert workflow["name"] == "cambridge_igcse_mathematics_questions"
        assert workflow["variables"]["subject"] == "mathematics"
        assert workflow["variables"]["topics"] == ["algebra", "geometry"]
        assert workflow["variables"]["question_count"] == 20
        
        # Should have steps for each topic
        steps = workflow["steps"]
        topic_steps = [step for step in steps if "algebra" in step["name"] or "geometry" in step["name"]]
        assert len(topic_steps) == 2
    
    def test_validate_derivativ_config_valid(self):
        """Test config validation with valid parameters."""
        valid_config = {
            "subjects": ["mathematics", "physics"],
            "grade_level": 9,
            "questions_per_topic": 8,
            "quality_threshold": 0.75,
            "api_base": "https://api.derivativ.ai",
            "api_key": "derivativ-key-123"
        }
        
        result = validate_derivativ_config(valid_config)
        assert result["valid"] == True
        assert len(result["errors"]) == 0
    
    def test_validate_derivativ_config_invalid_subjects(self):
        """Test config validation with invalid subjects."""
        invalid_config = {
            "subjects": ["invalid_subject", "nonexistent"],
            "grade_level": 9,
            "api_base": "https://api.derivativ.ai"
        }
        
        result = validate_derivativ_config(invalid_config)
        assert result["valid"] == False
        assert len(result["errors"]) > 0
        assert any("subject" in error.lower() for error in result["errors"])
    
    def test_validate_derivativ_config_invalid_grade(self):
        """Test config validation with invalid grade level."""
        invalid_config = {
            "subjects": ["mathematics"],
            "grade_level": 15,  # Too high
            "api_base": "https://api.derivativ.ai"
        }
        
        result = validate_derivativ_config(invalid_config)
        assert result["valid"] == False
        assert any("grade" in error.lower() for error in result["errors"])
    
    def test_validate_derivativ_config_missing_required(self):
        """Test config validation with missing required fields."""
        incomplete_config = {
            "subjects": ["mathematics"]
            # Missing grade_level, api_base
        }
        
        result = validate_derivativ_config(incomplete_config)
        assert result["valid"] == False
        assert len(result["errors"]) >= 2  # Missing grade_level and api_base


class TestTemplateLibrary:
    """Test the template library and available templates."""
    
    def test_get_available_templates(self):
        """Test getting list of available Derivativ templates."""
        templates = get_available_templates()
        
        expected_templates = [
            "derivativ_daily",
            "cambridge_igcse_mathematics",
            "cambridge_igcse_sciences",
            "cambridge_igcse_languages",
            "multi_subject_daily",
            "single_subject_focused",
            "exam_preparation",
            "practice_test_generation"
        ]
        
        for template in expected_templates:
            assert template in templates
    
    def test_derivativ_template_configs_structure(self):
        """Test template configurations are properly structured."""
        assert isinstance(DERIVATIV_TEMPLATE_CONFIGS, dict)
        
        for template_name, config in DERIVATIV_TEMPLATE_CONFIGS.items():
            # Each template should have required fields
            assert "description" in config
            assert "default_subjects" in config
            assert "default_grade_level" in config
            assert "default_questions_per_topic" in config
            assert "schedule_frequency" in config
            
            # Validate subjects are valid Cambridge IGCSE subjects
            topics = CambridgeIGCSETopics()
            for subject in config["default_subjects"]:
                assert subject in topics.get_all_subjects()
    
    def test_template_specific_configurations(self):
        """Test specific template configurations."""
        # Test daily template
        daily_config = DERIVATIV_TEMPLATE_CONFIGS["derivativ_daily"]
        assert daily_config["schedule_frequency"] == "daily"
        assert daily_config["default_grade_level"] in [9, 10, 11]
        assert len(daily_config["default_subjects"]) >= 3
        
        # Test mathematics-focused template
        math_config = DERIVATIV_TEMPLATE_CONFIGS["cambridge_igcse_mathematics"]
        assert "mathematics" in math_config["default_subjects"]
        assert math_config["default_questions_per_topic"] >= 5
        
        # Test sciences template
        sciences_config = DERIVATIV_TEMPLATE_CONFIGS["cambridge_igcse_sciences"]
        sciences_subjects = ["physics", "chemistry", "biology"]
        assert any(subj in sciences_config["default_subjects"] for subj in sciences_subjects)


class TestRealWorldDerivativScenarios:
    """Test real-world Derivativ usage scenarios."""
    
    def test_daily_50_questions_scenario(self):
        """Test Derivativ's core requirement: 50 questions daily."""
        generator = DerivativTemplateGenerator()
        
        # Configuration to generate 50 questions across 6 subjects
        subjects = ["mathematics", "physics", "chemistry", "biology", "english", "computer_science"]
        questions_per_topic = 8  # 6 × 8 = 48, close to 50
        
        workflow = generator.generate_daily_workflow(
            subjects, 
            questions_per_topic=questions_per_topic
        )
        
        variables = workflow["variables"]
        expected_total = len(subjects) * questions_per_topic
        assert variables["total_target"] == expected_total
        assert 48 <= expected_total <= 52  # Close to 50 target
    
    def test_singapore_timezone_scheduling(self):
        """Test that workflows are properly scheduled for Singapore timezone."""
        generator = DerivativTemplateGenerator()
        workflow = generator.generate_daily_workflow(["mathematics"])
        
        # Should be scheduled for 2 AM SGT = 6 PM UTC previous day
        assert workflow["schedule"] == "0 18 * * *"
        assert workflow["timezone"] == "Asia/Singapore"
    
    def test_quality_threshold_application(self):
        """Test quality thresholds are applied correctly."""
        generator = DerivativTemplateGenerator(quality_threshold=0.85)
        workflow = generator.generate_daily_workflow(["mathematics", "physics"])
        
        # Check that quality threshold is passed to question generation steps
        question_steps = [step for step in workflow["steps"] if step["name"].startswith("generate_")]
        
        for step in question_steps:
            payload = step["payload_template"]
            assert "0.85" in payload or "quality_threshold" in payload
    
    def test_parallel_execution_optimization(self):
        """Test that workflows are optimized for parallel execution."""
        generator = DerivativTemplateGenerator()
        workflow = generator.generate_daily_workflow(["mathematics", "physics", "chemistry"])
        
        steps = workflow["steps"]
        
        # All question generation should be in parallel group
        question_steps = [step for step in steps if step["name"].startswith("generate_")]
        for step in question_steps:
            assert step.get("parallel_group") == "question_generation"
        
        # Document creation should wait for all questions
        doc_steps = [step for step in steps if "create_" in step["name"]]
        for step in doc_steps:
            assert "depends_on" in step
            assert len(step["depends_on"]) >= len(question_steps)
    
    def test_error_handling_and_retries(self):
        """Test that workflows include proper error handling."""
        generator = DerivativTemplateGenerator()
        workflow = generator.generate_daily_workflow(["mathematics"])
        
        steps = workflow["steps"]
        
        # Critical steps should have retry configuration
        for step in steps:
            if step["name"].startswith("generate_") or "create_" in step["name"]:
                assert "retry" in step
                retry_config = step["retry"]
                assert "limit" in retry_config
                assert retry_config["limit"] >= 2
                assert "delay" in retry_config
                assert "backoff" in retry_config
    
    def test_monitoring_and_alerting_setup(self):
        """Test that workflows include monitoring configuration."""
        generator = DerivativTemplateGenerator()
        workflow = generator.generate_daily_workflow(["mathematics"])
        
        assert "monitoring" in workflow
        monitoring = workflow["monitoring"]
        
        assert "webhook_url" in monitoring
        assert "alerts" in monitoring
        assert monitoring["alerts"]["on_failure"] == True
        assert "on_long_duration" in monitoring["alerts"]