"""
Derivativ-specific workflow templates for Cambridge IGCSE question generation.
Provides pre-built templates, topic management, and validation for educational workflows.
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import uuid
from gimme_ai.utils.singapore_scheduler import SingaporeScheduler


class CambridgeIGCSETopics:
    """
    Cambridge IGCSE curriculum topics and subject management.
    Provides validated topics, grade levels, and difficulty mappings.
    """
    
    def __init__(self):
        """Initialize with Cambridge IGCSE curriculum structure."""
        self._subjects = {
            "mathematics": {
                "topics": [
                    "algebra", "geometry", "statistics", "probability",
                    "number_theory", "calculus_basics", "trigonometry"
                ],
                "difficulties": {
                    "algebra": "intermediate",
                    "geometry": "intermediate", 
                    "statistics": "basic",
                    "probability": "intermediate",
                    "number_theory": "basic",
                    "calculus_basics": "advanced",
                    "trigonometry": "advanced"
                }
            },
            "physics": {
                "topics": [
                    "mechanics", "waves", "electricity", "magnetism",
                    "thermal_physics", "atomic_physics", "energy"
                ],
                "difficulties": {
                    "mechanics": "intermediate",
                    "waves": "intermediate",
                    "electricity": "basic",
                    "magnetism": "intermediate",
                    "thermal_physics": "basic",
                    "atomic_physics": "advanced",
                    "energy": "basic"
                }
            },
            "chemistry": {
                "topics": [
                    "atomic_structure", "bonding", "stoichiometry", "acids_bases",
                    "organic_chemistry", "reaction_kinetics", "equilibrium"
                ],
                "difficulties": {
                    "atomic_structure": "basic",
                    "bonding": "intermediate",
                    "stoichiometry": "intermediate",
                    "acids_bases": "basic",
                    "organic_chemistry": "advanced",
                    "reaction_kinetics": "advanced",
                    "equilibrium": "advanced"
                }
            },
            "biology": {
                "topics": [
                    "cell_biology", "genetics", "evolution", "ecology",
                    "human_physiology", "plant_biology", "molecular_biology"
                ],
                "difficulties": {
                    "cell_biology": "basic",
                    "genetics": "intermediate",
                    "evolution": "intermediate",
                    "ecology": "basic",
                    "human_physiology": "intermediate",
                    "plant_biology": "basic",
                    "molecular_biology": "advanced"
                }
            },
            "english": {
                "topics": [
                    "literature_analysis", "creative_writing", "grammar",
                    "reading_comprehension", "essay_writing", "poetry", "drama"
                ],
                "difficulties": {
                    "literature_analysis": "intermediate",
                    "creative_writing": "intermediate",
                    "grammar": "basic",
                    "reading_comprehension": "basic",
                    "essay_writing": "intermediate",
                    "poetry": "advanced",
                    "drama": "intermediate"
                }
            },
            "computer_science": {
                "topics": [
                    "programming_basics", "algorithms", "data_structures",
                    "computer_systems", "databases", "networks", "cybersecurity"
                ],
                "difficulties": {
                    "programming_basics": "basic",
                    "algorithms": "intermediate",
                    "data_structures": "intermediate", 
                    "computer_systems": "basic",
                    "databases": "intermediate",
                    "networks": "advanced",
                    "cybersecurity": "advanced"
                }
            }
        }
        
        # IGCSE grade levels (typically 9-11)
        self._valid_grade_levels = [9, 10, 11]
        
        # Recommended questions per topic based on difficulty
        self._questions_recommendations = {
            "basic": 6,
            "intermediate": 8,
            "advanced": 10
        }
    
    def get_all_subjects(self) -> List[str]:
        """Get list of all available IGCSE subjects."""
        return list(self._subjects.keys())
    
    def get_subject_topics(self, subject: str) -> List[str]:
        """Get topics for a specific subject."""
        if subject not in self._subjects:
            raise ValueError(f"Unknown subject: {subject}")
        return self._subjects[subject]["topics"]
    
    def validate_grade_level(self, grade_level: int) -> bool:
        """Validate if grade level is appropriate for IGCSE."""
        return grade_level in self._valid_grade_levels
    
    def get_topic_difficulty(self, subject: str, topic: str) -> str:
        """Get difficulty level for a specific topic."""
        if subject not in self._subjects:
            raise ValueError(f"Unknown subject: {subject}")
        
        difficulties = self._subjects[subject]["difficulties"]
        if topic not in difficulties:
            raise ValueError(f"Unknown topic {topic} for subject {subject}")
        
        return difficulties[topic]
    
    def get_questions_per_topic_recommendation(self, subject: str, topic: str) -> int:
        """Get recommended number of questions for a topic."""
        difficulty = self.get_topic_difficulty(subject, topic)
        return self._questions_recommendations[difficulty]


class DerivativTemplateGenerator:
    """
    Main generator for Derivativ workflow templates.
    Creates Cambridge IGCSE question generation workflows with Singapore scheduling.
    """
    
    def __init__(
        self,
        grade_level: int = 9,
        questions_per_topic: int = 8,
        quality_threshold: float = 0.75,
        schedule_time: str = "02:00"
    ):
        """
        Initialize template generator.
        
        Args:
            grade_level: Default IGCSE grade level (9-11)
            questions_per_topic: Default questions per topic
            quality_threshold: Quality threshold for generated questions (0.0-1.0)
            schedule_time: Daily schedule time in SGT (e.g., "02:00")
        """
        self.default_grade_level = grade_level
        self.default_questions_per_topic = questions_per_topic
        self.default_quality_threshold = quality_threshold
        self.schedule_time = schedule_time
        
        self.topics_manager = CambridgeIGCSETopics()
        self.scheduler = SingaporeScheduler()
        
        # Validate initialization parameters
        if not self.topics_manager.validate_grade_level(grade_level):
            raise ValueError(f"Invalid grade level: {grade_level}")
        if not (0.0 <= quality_threshold <= 1.0):
            raise ValueError(f"Quality threshold must be 0.0-1.0: {quality_threshold}")
    
    def generate_daily_workflow(
        self,
        subjects: List[str],
        grade_level: Optional[int] = None,
        questions_per_topic: Optional[int] = None,
        quality_threshold: Optional[float] = None,
        api_base: str = "{{ api_base_url }}",
        api_key: str = "{{ derivativ_api_key }}"
    ) -> Dict[str, Any]:
        """
        Generate daily Cambridge IGCSE question workflow.
        
        Args:
            subjects: List of subjects to generate questions for
            grade_level: Override default grade level
            questions_per_topic: Override default questions per topic
            quality_threshold: Override default quality threshold
            api_base: API base URL
            api_key: API authentication key
            
        Returns:
            Complete workflow configuration dictionary
        """
        # Use defaults if not specified
        grade_level = grade_level or self.default_grade_level
        questions_per_topic = questions_per_topic or self.default_questions_per_topic
        quality_threshold = quality_threshold or self.default_quality_threshold
        
        # Validate inputs
        for subject in subjects:
            if subject not in self.topics_manager.get_all_subjects():
                raise ValueError(f"Unknown subject: {subject}")
        
        if not self.topics_manager.validate_grade_level(grade_level):
            raise ValueError(f"Invalid grade level: {grade_level}")
        
        # Generate UTC cron from Singapore time
        utc_cron = self.scheduler.convert_time_to_utc_cron(self.schedule_time, "daily")
        
        # Calculate total target questions
        total_target = len(subjects) * questions_per_topic
        
        # Generate unique request ID
        request_id = f"daily-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8]}"
        
        # Base workflow structure
        workflow = {
            "name": "derivativ_cambridge_igcse_daily",
            "description": "Daily Cambridge IGCSE question generation for multiple topics",
            "schedule": utc_cron,
            "timezone": "Asia/Singapore",
            "api_base": api_base,
            "auth": {
                "type": "bearer",
                "token": api_key
            },
            "variables": {
                "topics": subjects,
                "questions_per_topic": questions_per_topic,
                "grade_level": grade_level,
                "quality_threshold": quality_threshold,
                "total_target": total_target,
                "request_id": request_id,
                "workflow_date": "{{ now().strftime('%Y-%m-%d') }}"
            },
            "steps": [],
            "monitoring": {
                "webhook_url": "{{ webhook_url | default('https://api.derivativ.ai/webhooks/workflow_complete') }}",
                "alerts": {
                    "on_failure": True,
                    "on_long_duration": "30m"
                }
            }
        }
        
        # Generate question generation steps (parallel)
        for subject in subjects:
            step = {
                "name": f"generate_{subject}_questions",
                "description": f"Generate {questions_per_topic} {subject} questions",
                "endpoint": "/api/questions/generate",
                "method": "POST",
                "parallel_group": "question_generation",
                "retry": {
                    "limit": 3,
                    "delay": "10s",
                    "backoff": "exponential",
                    "timeout": "5m"
                },
                "payload_template": self._generate_question_payload_template(
                    subject, questions_per_topic, grade_level, quality_threshold
                ),
                "output_key": f"{subject}_results"
            }
            workflow["steps"].append(step)
        
        # Generate document creation steps (sequential, depends on questions)
        question_step_names = [f"generate_{subject}_questions" for subject in subjects]
        
        # Worksheet generation
        worksheet_step = {
            "name": "create_worksheet",
            "description": "Create student worksheet with all generated questions",
            "endpoint": "/api/documents/generate",
            "method": "POST",
            "depends_on": question_step_names,
            "retry": {
                "limit": 2,
                "delay": "5s",
                "backoff": "exponential",
                "timeout": "10m"
            },
            "payload_template": self._generate_worksheet_payload_template(subjects),
            "output_key": "worksheet_result"
        }
        workflow["steps"].append(worksheet_step)
        
        # Answer key generation
        answer_key_step = {
            "name": "create_answer_key",
            "description": "Create answer key with detailed solutions",
            "endpoint": "/api/documents/generate",
            "method": "POST",
            "depends_on": question_step_names,
            "retry": {
                "limit": 2,
                "delay": "5s",
                "backoff": "exponential",
                "timeout": "10m"
            },
            "payload_template": self._generate_answer_key_payload_template(subjects),
            "output_key": "answer_key_result"
        }
        workflow["steps"].append(answer_key_step)
        
        # Storage step
        storage_step = {
            "name": "store_documents",
            "description": "Store all generated documents with dual versions",
            "endpoint": "/api/documents/store",
            "method": "POST",
            "depends_on": ["create_worksheet", "create_answer_key"],
            "payload_template": self._generate_storage_payload_template()
        }
        workflow["steps"].append(storage_step)
        
        return workflow
    
    def _generate_question_payload_template(
        self, 
        subject: str, 
        questions_per_topic: int, 
        grade_level: int, 
        quality_threshold: float
    ) -> str:
        """Generate payload template for question generation."""
        return f'''{{
  "subject": "{subject}",
  "count": {questions_per_topic},
  "grade_level": {grade_level},
  "quality_threshold": {quality_threshold},
  "request_id": "{{{{ request_id }}}}-{subject}",
  "workflow_date": "{{{{ workflow_date }}}}"
}}'''
    
    def _generate_worksheet_payload_template(self, subjects: List[str]) -> str:
        """Generate payload template for worksheet creation."""
        return '''{
  "document_type": "worksheet",
  "question_ids": {{ steps | collect_question_ids | tojson }},
  "detail_level": "medium",
  "include_solutions": false,
  "metadata": {
    "generated_date": "{{ workflow_date }}",
    "topics": {{ topics | tojson }},
    "total_questions": {{ total_target }}
  }
}'''
    
    def _generate_answer_key_payload_template(self, subjects: List[str]) -> str:
        """Generate payload template for answer key creation."""
        return '''{
  "document_type": "answer_key",
  "question_ids": {{ steps | collect_question_ids | tojson }},
  "include_solutions": true,
  "include_marking_schemes": true,
  "metadata": {
    "generated_date": "{{ workflow_date }}",
    "topics": {{ topics | tojson }}
  }
}'''
    
    def _generate_storage_payload_template(self) -> str:
        """Generate payload template for document storage."""
        return '''{
  "documents": [
    {
      "id": "worksheet-{{ workflow_date }}",
      "type": "worksheet",
      "formats": ["pdf", "docx", "html"]
    },
    {
      "id": "answer-key-{{ workflow_date }}",
      "type": "answer_key",
      "formats": ["pdf", "docx"]
    }
  ],
  "create_dual_versions": true,
  "metadata": {
    "workflow_id": "{{ request_id }}",
    "generation_date": "{{ workflow_date }}",
    "total_questions": {{ total_target }}
  }
}'''


# Template configurations for different Derivativ use cases
DERIVATIV_TEMPLATE_CONFIGS = {
    "derivativ_daily": {
        "description": "Daily multi-subject question generation for comprehensive practice",
        "default_subjects": ["mathematics", "physics", "chemistry", "biology", "english"],
        "default_grade_level": 9,
        "default_questions_per_topic": 8,
        "schedule_frequency": "daily",
        "schedule_time": "02:00"
    },
    "cambridge_igcse_mathematics": {
        "description": "Mathematics-focused question generation with all core topics",
        "default_subjects": ["mathematics"],
        "default_grade_level": 10,
        "default_questions_per_topic": 12,
        "schedule_frequency": "daily",
        "schedule_time": "02:00"
    },
    "cambridge_igcse_sciences": {
        "description": "Science subjects comprehensive question generation",
        "default_subjects": ["physics", "chemistry", "biology"],
        "default_grade_level": 9,
        "default_questions_per_topic": 10,
        "schedule_frequency": "daily",
        "schedule_time": "02:30"
    },
    "cambridge_igcse_languages": {
        "description": "Language arts and literature question generation",
        "default_subjects": ["english"],
        "default_grade_level": 10,
        "default_questions_per_topic": 15,
        "schedule_frequency": "daily",
        "schedule_time": "01:30"
    },
    "multi_subject_daily": {
        "description": "Balanced daily practice across all core subjects",
        "default_subjects": ["mathematics", "physics", "chemistry", "english", "computer_science"],
        "default_grade_level": 9,
        "default_questions_per_topic": 8,
        "schedule_frequency": "daily",
        "schedule_time": "02:00"
    },
    "single_subject_focused": {
        "description": "Intensive single-subject practice sessions",
        "default_subjects": ["mathematics"],
        "default_grade_level": 11,
        "default_questions_per_topic": 20,
        "schedule_frequency": "daily",
        "schedule_time": "03:00"
    },
    "exam_preparation": {
        "description": "Exam-focused question generation with higher difficulty",
        "default_subjects": ["mathematics", "physics", "chemistry"],
        "default_grade_level": 11,
        "default_questions_per_topic": 15,
        "schedule_frequency": "daily",
        "schedule_time": "01:00"
    },
    "practice_test_generation": {
        "description": "Full practice test creation with mixed subjects",
        "default_subjects": ["mathematics", "physics", "chemistry", "biology"],
        "default_grade_level": 10,
        "default_questions_per_topic": 12,
        "schedule_frequency": "weekly",
        "schedule_time": "02:00"
    }
}


def generate_derivativ_daily_workflow(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate Derivativ daily workflow from configuration.
    
    Args:
        config: Configuration dictionary with required fields:
            - subjects: List of subjects
            - grade_level: IGCSE grade level
            - questions_per_topic: Questions per topic
            - api_base: API base URL
            - api_key: API authentication key
            
    Returns:
        Complete workflow configuration
    """
    generator = DerivativTemplateGenerator(
        grade_level=config.get("grade_level", 9),
        questions_per_topic=config.get("questions_per_topic", 8),
        quality_threshold=config.get("quality_threshold", 0.75)
    )
    
    return generator.generate_daily_workflow(
        subjects=config["subjects"],
        api_base=config.get("api_base", "{{ api_base_url }}"),
        api_key=config.get("api_key", "{{ derivativ_api_key }}")
    )


def generate_cambridge_question_workflow(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate Cambridge IGCSE question workflow for specific subject and topics.
    
    Args:
        config: Configuration with subject, topics, grade_level, question_count
        
    Returns:
        Subject-specific workflow configuration
    """
    subject = config["subject"]
    topics = config.get("topics", [])
    grade_level = config.get("grade_level", 9)
    question_count = config.get("question_count", 20)
    api_base = config.get("api_base", "{{ api_base_url }}")
    
    # Calculate questions per topic
    questions_per_topic = question_count // len(topics) if topics else question_count
    
    workflow = {
        "name": f"cambridge_igcse_{subject}_questions",
        "description": f"Cambridge IGCSE {subject} question generation",
        "api_base": api_base,
        "variables": {
            "subject": subject,
            "topics": topics,
            "grade_level": grade_level,
            "question_count": question_count,
            "questions_per_topic": questions_per_topic
        },
        "steps": []
    }
    
    # Generate steps for each topic
    for topic in topics:
        step = {
            "name": f"generate_{topic}_questions",
            "description": f"Generate {questions_per_topic} {topic} questions",
            "endpoint": "/api/questions/generate",
            "method": "POST",
            "payload_template": f'''{{
  "subject": "{subject}",
  "topic": "{topic}",
  "count": {questions_per_topic},
  "grade_level": {grade_level}
}}'''
        }
        workflow["steps"].append(step)
    
    return workflow


def validate_derivativ_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate Derivativ workflow configuration.
    
    Args:
        config: Configuration dictionary to validate
        
    Returns:
        Validation result with valid flag and error list
    """
    errors = []
    topics_manager = CambridgeIGCSETopics()
    
    # Check required fields
    required_fields = ["subjects", "grade_level", "api_base"]
    for field in required_fields:
        if field not in config:
            errors.append(f"Missing required field: {field}")
    
    # Validate subjects
    if "subjects" in config:
        available_subjects = topics_manager.get_all_subjects()
        for subject in config["subjects"]:
            if subject not in available_subjects:
                errors.append(f"Unknown subject: {subject}")
    
    # Validate grade level
    if "grade_level" in config:
        if not topics_manager.validate_grade_level(config["grade_level"]):
            errors.append(f"Invalid grade level: {config['grade_level']}. Must be 9, 10, or 11.")
    
    # Validate optional numeric fields
    if "questions_per_topic" in config:
        if not isinstance(config["questions_per_topic"], int) or config["questions_per_topic"] < 1:
            errors.append("questions_per_topic must be a positive integer")
    
    if "quality_threshold" in config:
        threshold = config["quality_threshold"]
        if not isinstance(threshold, (int, float)) or not (0.0 <= threshold <= 1.0):
            errors.append("quality_threshold must be a number between 0.0 and 1.0")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors
    }


def get_available_templates() -> List[str]:
    """
    Get list of available Derivativ workflow templates.
    
    Returns:
        List of template names
    """
    return list(DERIVATIV_TEMPLATE_CONFIGS.keys())