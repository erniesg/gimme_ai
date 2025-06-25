#!/usr/bin/env python3
"""
Example: User-defined transformation logic approach.
Shows how to keep gimme_ai as pure orchestration while users handle their own logic.
"""

import asyncio
import json
from typing import Dict, Any, List
from gimme_ai.config.workflow import WorkflowConfig, StepConfig, AuthConfig
from gimme_ai.http.workflow_client import WorkflowHTTPClient
from gimme_ai.workflows.execution_engine import WorkflowExecutionEngine


class ContentCreationTransforms:
    """User-defined transformation logic for content creation pipeline."""
    
    @staticmethod
    def parse_scenes_from_openai(openai_response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Transform OpenAI response into structured scene data."""
        try:
            # Extract the actual content
            content = openai_response['choices'][0]['message']['content']
            
            # User's custom parsing logic
            scenes = []
            if 'Scene 1:' in content:
                # Parse numbered scenes
                parts = content.split('Scene ')
                for i, part in enumerate(parts[1:], 1):
                    lines = part.strip().split('\n')
                    if lines:
                        description = lines[0].replace(f'{i}:', '').strip()
                        # Extract image prompt (user's custom logic)
                        image_prompt = f"Photorealistic image of {description}, cinematic lighting, high quality"
                        scenes.append({
                            'scene_number': i,
                            'description': description,
                            'image_prompt': image_prompt,
                            'duration': '5s'
                        })
            else:
                # Fallback: treat whole response as one scene
                scenes.append({
                    'scene_number': 1,
                    'description': content[:100],
                    'image_prompt': f"Visual representation of: {content[:50]}",
                    'duration': '10s'
                })
            
            return scenes
            
        except Exception as e:
            print(f"Error parsing scenes: {e}")
            return [{'scene_number': 1, 'description': 'Default scene', 'image_prompt': 'Default prompt', 'duration': '5s'}]
    
    @staticmethod
    def enhance_voiceover_script(scenes: List[Dict[str, Any]], original_text: str) -> str:
        """User's custom logic to create voiceover script from scenes."""
        try:
            # User-defined enhancement logic
            script_parts = []
            
            # Add intro
            script_parts.append("Welcome to this visual journey.")
            
            # Add scene narrations
            for scene in scenes:
                description = scene.get('description', '')
                # User's custom voice enhancement
                enhanced_desc = description.replace('shows', 'reveals').replace('depicts', 'captures')
                script_parts.append(f"Here we see {enhanced_desc}.")
            
            # Add outro
            script_parts.append("Thank you for watching.")
            
            return ' '.join(script_parts)
            
        except Exception as e:
            print(f"Error enhancing script: {e}")
            return original_text
    
    @staticmethod
    def process_replicate_response(replicate_response: Dict[str, Any]) -> Dict[str, Any]:
        """User's custom logic to handle Replicate API response."""
        try:
            # User defines how to extract the image URL
            if isinstance(replicate_response, dict):
                # Handle different response formats
                if 'output' in replicate_response and replicate_response['output']:
                    image_url = replicate_response['output'][0] if isinstance(replicate_response['output'], list) else replicate_response['output']
                elif 'urls' in replicate_response:
                    image_url = replicate_response['urls']['get']
                else:
                    image_url = None
                
                return {
                    'image_url': image_url,
                    'status': replicate_response.get('status', 'unknown'),
                    'processing_time': replicate_response.get('metrics', {}).get('predict_time', 0)
                }
            
            return {'image_url': None, 'status': 'error', 'processing_time': 0}
            
        except Exception as e:
            print(f"Error processing Replicate response: {e}")
            return {'image_url': None, 'status': 'error', 'processing_time': 0}
    
    @staticmethod
    def compile_final_output(scenes: List[Dict], voiceover: str, image_data: Dict, audio_url: str) -> Dict[str, Any]:
        """User's custom logic to compile all outputs into final format."""
        return {
            'content_package': {
                'metadata': {
                    'total_scenes': len(scenes),
                    'estimated_duration': sum(int(s.get('duration', '5s').replace('s', '')) for s in scenes),
                    'content_type': 'educational_video'
                },
                'narrative': {
                    'script': voiceover,
                    'audio_url': audio_url,
                    'style': 'professional_narration'
                },
                'visuals': {
                    'scene_breakdown': scenes,
                    'generated_image': image_data.get('image_url'),
                    'image_generation_time': image_data.get('processing_time', 0)
                },
                'delivery': {
                    'format': 'multi_asset_package',
                    'ready_for_editing': True,
                    'asset_urls': {
                        'voiceover': audio_url,
                        'scene_image': image_data.get('image_url')
                    }
                }
            }
        }


async def run_workflow_with_user_transforms():
    """Run workflow with user-defined transformations."""
    
    print("🎯 User-Defined Transform Logic Example")
    print("=" * 50)
    
    # 1. Define simple gimme_ai workflow (just API calls)
    workflow = WorkflowConfig(
        name="pure_api_orchestration",
        api_base="https://api.openai.com",
        auth=AuthConfig(type="bearer", token="${OPENAI_API_KEY}"),
        variables={
            'input_text': 'A morning routine: making coffee, checking emails, and watering plants.'
        },
        steps=[
            # Step 1: Raw OpenAI call
            StepConfig(
                name="raw_scene_analysis",
                endpoint="/v1/chat/completions",
                method="POST",
                headers={"Content-Type": "application/json"},
                payload={
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": "Break this into visual scenes: A morning routine: making coffee, checking emails, and watering plants."}],
                    "max_tokens": 200
                }
                # No extract_fields - return raw response
            ),
            
            # Step 2: Another raw OpenAI call for voiceover
            StepConfig(
                name="raw_voiceover_generation",
                endpoint="/v1/chat/completions",
                method="POST",
                headers={"Content-Type": "application/json"},
                payload={
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": "Create a 30-second voiceover script for: A morning routine: making coffee, checking emails, and watering plants."}],
                    "max_tokens": 150
                }
            )
        ]
    )
    
    # 2. Execute workflow (gimme_ai handles orchestration only)
    client = WorkflowHTTPClient(base_url=workflow.api_base)
    engine = WorkflowExecutionEngine(http_client=client)
    
    print("📡 Step 1: gimme_ai orchestrates API calls...")
    result = await engine.execute_workflow(workflow)
    
    if not result.success:
        print(f"❌ API orchestration failed: {result.error}")
        return
    
    print("✅ Raw API responses received")
    
    # 3. User applies their own transformation logic
    print("🔄 Step 2: User applies custom transformation logic...")
    
    transforms = ContentCreationTransforms()
    
    # Transform scene analysis
    raw_scenes_response = result.step_results["raw_scene_analysis"].response_data
    scenes = transforms.parse_scenes_from_openai(raw_scenes_response)
    print(f"   📽️  Parsed {len(scenes)} scenes from OpenAI response")
    
    # Transform voiceover
    raw_voiceover_response = result.step_results["raw_voiceover_generation"].response_data
    voiceover_content = raw_voiceover_response['choices'][0]['message']['content']
    enhanced_voiceover = transforms.enhance_voiceover_script(scenes, voiceover_content)
    print(f"   🎙️  Enhanced voiceover script ({len(enhanced_voiceover)} chars)")
    
    # Simulate image generation response (would come from another gimme_ai call)
    mock_image_response = {'output': ['https://example.com/generated_image.png'], 'status': 'succeeded'}
    image_data = transforms.process_replicate_response(mock_image_response)
    print(f"   🖼️  Processed image data: {image_data['status']}")
    
    # User compiles final output
    final_output = transforms.compile_final_output(
        scenes=scenes,
        voiceover=enhanced_voiceover,
        image_data=image_data,
        audio_url="https://example.com/voiceover.mp3"
    )
    
    print("✅ Step 3: User transformation complete")
    
    # 4. Show results
    print(f"\n🎯 Final Output Structure:")
    print(f"   📊 Metadata: {final_output['content_package']['metadata']}")
    print(f"   📝 Script length: {len(final_output['content_package']['narrative']['script'])} chars")
    print(f"   🎬 Scenes: {len(final_output['content_package']['visuals']['scene_breakdown'])}")
    print(f"   📦 Asset URLs: {len(final_output['content_package']['delivery']['asset_urls'])} files")
    
    print(f"\n💡 Key Benefits:")
    print(f"   ✅ gimme_ai: Pure API orchestration (auth, retry, async)")
    print(f"   ✅ User Logic: Custom transformation, business rules, data formatting")
    print(f"   ✅ Separation: Infrastructure vs. business logic cleanly separated")
    print(f"   ✅ Flexibility: User can change logic without touching gimme_ai")


def show_architecture_patterns():
    """Show different architecture patterns for user logic."""
    
    print("\n🏗️  Architecture Patterns for User Logic")
    print("=" * 50)
    
    print("\n1️⃣  PURE ORCHESTRATION (Recommended)")
    print("   gimme_ai: API calls only")
    print("   User App: All transformation logic")
    print("   Pros: Maximum flexibility, clean separation")
    print("   Cons: User handles more logic")
    
    print("\n2️⃣  HYBRID APPROACH")
    print("   gimme_ai: Basic transforms (extract_fields, response_transform)")
    print("   User App: Complex business logic")
    print("   Pros: Convenient for simple cases")
    print("   Cons: Some logic tied to gimme_ai")
    
    print("\n3️⃣  WEBHOOK PATTERN")
    print("   gimme_ai: Calls user webhooks between steps")
    print("   User App: Receives data, returns transformed data")
    print("   Pros: Real-time processing")
    print("   Cons: More complex deployment")
    
    print("\n📋 YAML Examples:")
    
    print("\n# Pure Orchestration")
    print("""
steps:
  - name: "raw_openai_call"
    endpoint: "/v1/chat/completions"
    # No extract_fields - return full response
    # User handles all parsing in their app
""")
    
    print("\n# Hybrid Approach")
    print("""
steps:
  - name: "openai_with_extraction"
    endpoint: "/v1/chat/completions"
    extract_fields:
      content: "choices.0.message.content"
    # gimme_ai extracts field, user handles rest
""")
    
    print("\n# Webhook Pattern")
    print("""
steps:
  - name: "call_user_transform"
    api_base: "https://your-app.com"
    endpoint: "/transform/scenes"
    method: "POST"
    payload_template: |
      {
        "raw_openai_response": {{ previous_step.response }},
        "user_context": "{{ context }}"
      }
""")


if __name__ == "__main__":
    print("🧪 Testing User-Defined Transform Logic")
    
    # Show architecture patterns first
    show_architecture_patterns()
    
    # Note: Actual API testing would require keys
    print(f"\n🔧 To test with real APIs:")
    print(f"   export OPENAI_API_KEY='sk-...'")
    print(f"   python {__file__}")
    
    # For demo, just run the example without API calls
    print(f"\n📋 Demo: User Transform Logic Structure")
    transforms = ContentCreationTransforms()
    
    # Mock OpenAI response
    mock_openai_response = {
        'choices': [{'message': {'content': 'Scene 1: Person making coffee in kitchen\nScene 2: Person checking emails at desk\nScene 3: Person watering plants on balcony'}}]
    }
    
    scenes = transforms.parse_scenes_from_openai(mock_openai_response)
    print(f"✅ Parsed {len(scenes)} scenes from mock response")
    
    enhanced_script = transforms.enhance_voiceover_script(scenes, "Original text")
    print(f"✅ Enhanced script: {len(enhanced_script)} characters")
    
    print(f"\n💡 This pattern gives you maximum flexibility:")
    print(f"   - gimme_ai handles API orchestration")
    print(f"   - Your app handles all business logic")
    print(f"   - Clean separation of concerns")