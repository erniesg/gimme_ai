/**
 * GenericAPIWorkflow - Enhanced gimme_ai workflow engine for generic API orchestration
 * 
 * This module provides a configurable workflow engine that can orchestrate
 * any REST API through YAML configuration with support for:
 * - Step dependencies and parallel execution
 * - Retry strategies with exponential backoff
 * - Jinja2-style templating for dynamic payloads
 * - Singapore timezone cron scheduling
 * - Comprehensive error handling and state persistence
 */

import { WorkflowEntrypoint, WorkflowStep } from 'cloudflare:workers';
import { NonRetryableError } from 'cloudflare:workflows';

// Type definitions for workflow configuration
export interface WorkflowConfig {
  name: string;
  description?: string;
  schedule?: string;
  timezone?: string;
  api_base: string;
  auth?: AuthConfig;
  variables?: Record<string, any>;
  steps: StepConfig[];
  monitoring?: MonitoringConfig;
}

export interface StepConfig {
  name: string;
  description?: string;
  endpoint: string;
  method?: HttpMethod;
  
  // Execution Control
  depends_on?: string[];
  parallel_group?: string;
  max_parallel?: number;
  
  // Request Configuration
  headers?: Record<string, string>;
  payload_template?: string;
  payload?: any;
  
  // Error Handling
  retry?: RetryConfig;
  timeout?: string;
  continue_on_error?: boolean;
  
  // Response Processing
  response_transform?: string;
  output_key?: string;
}

export interface AuthConfig {
  type: 'none' | 'bearer' | 'api_key' | 'basic' | 'custom';
  token?: string;
  api_key?: string;
  username?: string;
  password?: string;
  header_name?: string;
  custom_headers?: Record<string, string>;
}

export interface RetryConfig {
  limit: number;
  delay: string;
  backoff: 'constant' | 'linear' | 'exponential';
  timeout?: string;
}

export interface MonitoringConfig {
  webhook_url?: string;
  alerts?: {
    on_failure?: boolean;
    on_long_duration?: string;
  };
}

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';

export interface ExecutionPhase {
  sequential_steps: StepConfig[];
  parallel_groups: StepGroup[];
}

export interface StepGroup {
  group_name: string;
  steps: StepConfig[];
  max_parallel?: number;
}

export interface ExecutionPlan {
  phases: ExecutionPhase[];
  total_steps: number;
}

export interface StepResult {
  step_name: string;
  status: 'success' | 'failure' | 'skipped';
  result?: any;
  error?: string;
  duration_ms: number;
  attempts: number;
}

export interface WorkflowState {
  config: WorkflowConfig;
  step_results: Record<string, StepResult>;
  global_variables: Record<string, any>;
  start_time: number;
  current_phase: number;
}

/**
 * Generic API Workflow Engine
 * 
 * Orchestrates multi-step API workflows with support for complex dependency
 * graphs, parallel execution, retry strategies, and template-based payloads.
 */
export class GenericAPIWorkflow extends WorkflowEntrypoint {
  private config: WorkflowConfig;
  private state: WorkflowState;
  
  constructor() {
    super();
  }
  
  /**
   * Main workflow execution entry point
   */
  async run(event: any, step: WorkflowStep): Promise<any> {
    console.log('GenericAPIWorkflow started with event:', JSON.stringify(event));
    
    // Initialize workflow state
    const initResult = await step.do('initialize_workflow', async () => {
      return this.initializeWorkflow(event);
    });
    
    this.config = initResult.config;
    this.state = initResult.state;
    
    console.log(`Initialized workflow: ${this.config.name} with ${this.config.steps.length} steps`);
    
    // Build execution plan from step dependencies
    const executionPlan = this.buildExecutionPlan(this.config.steps);
    console.log(`Execution plan: ${executionPlan.phases.length} phases, ${executionPlan.total_steps} total steps`);
    
    // Execute workflow phases
    for (let phaseIndex = 0; phaseIndex < executionPlan.phases.length; phaseIndex++) {
      const phase = executionPlan.phases[phaseIndex];
      
      await step.do(`execute_phase_${phaseIndex}`, async () => {
        return this.executePhase(phase, step, phaseIndex);
      });
    }
    
    // Finalize workflow
    const finalResult = await step.do('finalize_workflow', async () => {
      return this.finalizeWorkflow();
    });
    
    // Send monitoring notifications if configured
    if (this.config.monitoring?.webhook_url) {
      await step.do('send_completion_notification', async () => {
        return this.sendCompletionNotification(finalResult);
      });
    }
    
    return finalResult;
  }
  
  /**
   * Initialize workflow state and validate configuration
   */
  private async initializeWorkflow(event: any): Promise<{ config: WorkflowConfig; state: WorkflowState }> {
    // Extract configuration from event or use provided config
    let config: WorkflowConfig;
    
    if (event.workflow_config) {
      config = event.workflow_config;
    } else {
      // Default configuration for testing
      config = {
        name: 'default-workflow',
        api_base: event.api_base || 'https://api.example.com',
        steps: event.steps || []
      };
    }
    
    // Validate configuration
    this.validateConfig(config);
    
    // Initialize state
    const state: WorkflowState = {
      config,
      step_results: {},
      global_variables: {
        ...config.variables,
        ...event.variables,
        workflow_start_time: Date.now(),
        request_id: event.requestId || crypto.randomUUID()
      },
      start_time: Date.now(),
      current_phase: 0
    };
    
    return { config, state };
  }
  
  /**
   * Build execution plan with dependency resolution and parallel grouping
   */
  private buildExecutionPlan(steps: StepConfig[]): ExecutionPlan {
    const stepMap = new Map<string, StepConfig>();
    const dependencyGraph = new Map<string, string[]>();
    const parallelGroups = new Map<string, StepConfig[]>();
    
    // Build step map and dependency graph
    for (const step of steps) {
      stepMap.set(step.name, step);
      dependencyGraph.set(step.name, step.depends_on || []);
      
      // Group parallel steps
      if (step.parallel_group) {
        if (!parallelGroups.has(step.parallel_group)) {
          parallelGroups.set(step.parallel_group, []);
        }
        parallelGroups.get(step.parallel_group)!.push(step);
      }
    }
    
    // Topological sort with parallel group awareness
    const phases: ExecutionPhase[] = [];
    const completed = new Set<string>();
    const remaining = new Set(steps.map(s => s.name));
    
    while (remaining.size > 0) {
      const phase: ExecutionPhase = {
        sequential_steps: [],
        parallel_groups: []
      };
      
      // Find steps that can execute (all dependencies completed)
      const ready = Array.from(remaining).filter(stepName => {
        const deps = dependencyGraph.get(stepName) || [];
        return deps.every(dep => completed.has(dep));
      });
      
      if (ready.length === 0) {
        throw new Error('Circular dependency detected in workflow steps');
      }
      
      // Group ready steps by parallel groups vs sequential
      const sequentialSteps: StepConfig[] = [];
      const groupedSteps = new Map<string, StepConfig[]>();
      
      for (const stepName of ready) {
        const step = stepMap.get(stepName)!;
        
        if (step.parallel_group) {
          if (!groupedSteps.has(step.parallel_group)) {
            groupedSteps.set(step.parallel_group, []);
          }
          groupedSteps.get(step.parallel_group)!.push(step);
        } else {
          sequentialSteps.push(step);
        }
      }
      
      // Add sequential steps to phase
      phase.sequential_steps = sequentialSteps;
      
      // Add parallel groups to phase
      for (const [groupName, groupSteps] of groupedSteps) {
        // Only add complete parallel groups (all members ready)
        const allGroupSteps = parallelGroups.get(groupName) || [];
        const readyGroupSteps = groupSteps.filter(step => ready.includes(step.name));
        
        if (readyGroupSteps.length === allGroupSteps.length) {
          phase.parallel_groups.push({
            group_name: groupName,
            steps: readyGroupSteps,
            max_parallel: readyGroupSteps[0]?.max_parallel
          });
          
          // Mark all group steps as handled
          for (const step of readyGroupSteps) {
            completed.add(step.name);
            remaining.delete(step.name);
          }
        }
      }
      
      // Mark sequential steps as completed
      for (const step of sequentialSteps) {
        completed.add(step.name);
        remaining.delete(step.name);
      }
      
      phases.push(phase);
    }
    
    return {
      phases,
      total_steps: steps.length
    };
  }
  
  /**
   * Execute a single phase (sequential steps + parallel groups)
   */
  private async executePhase(phase: ExecutionPhase, step: WorkflowStep, phaseIndex: number): Promise<void> {
    console.log(`Executing phase ${phaseIndex}: ${phase.sequential_steps.length} sequential steps, ${phase.parallel_groups.length} parallel groups`);
    
    // Execute sequential steps first
    for (const stepConfig of phase.sequential_steps) {
      await step.do(`step_${stepConfig.name}`, async () => {
        return this.executeStep(stepConfig);
      });
    }
    
    // Execute parallel groups
    for (const group of phase.parallel_groups) {
      await step.do(`parallel_group_${group.group_name}`, async () => {
        return this.executeParallelGroup(group);
      });
    }
  }
  
  /**
   * Execute a parallel group of steps
   */
  private async executeParallelGroup(group: StepGroup): Promise<StepResult[]> {
    console.log(`Executing parallel group: ${group.group_name} with ${group.steps.length} steps`);
    
    // Execute all steps in parallel with optional concurrency limit
    const maxConcurrent = group.max_parallel || group.steps.length;
    const results: StepResult[] = [];
    
    // Simple parallel execution (could be enhanced with semaphore for concurrency control)
    const promises = group.steps.map(stepConfig => this.executeStep(stepConfig));
    const groupResults = await Promise.all(promises);
    
    results.push(...groupResults);
    
    // Store results in state
    for (const result of results) {
      this.state.step_results[result.step_name] = result;
    }
    
    return results;
  }
  
  /**
   * Execute a single workflow step with retry logic
   */
  private async executeStep(stepConfig: StepConfig): Promise<StepResult> {
    const startTime = Date.now();
    let attempts = 0;
    let lastError: Error | null = null;
    
    const maxAttempts = (stepConfig.retry?.limit || 0) + 1;
    
    console.log(`Executing step: ${stepConfig.name} (max attempts: ${maxAttempts})`);
    
    while (attempts < maxAttempts) {
      attempts++;
      
      try {
        // Build request configuration
        const requestConfig = this.buildRequestConfig(stepConfig);
        
        // Execute HTTP request
        const response = await this.executeHttpRequest(requestConfig);
        
        // Process response
        const result = await this.processStepResponse(stepConfig, response);
        
        // Success
        const stepResult: StepResult = {
          step_name: stepConfig.name,
          status: 'success',
          result,
          duration_ms: Date.now() - startTime,
          attempts
        };
        
        this.state.step_results[stepConfig.name] = stepResult;
        console.log(`Step ${stepConfig.name} completed successfully in ${attempts} attempts`);
        
        return stepResult;
        
      } catch (error) {
        lastError = error as Error;
        console.log(`Step ${stepConfig.name} attempt ${attempts} failed: ${error}`);
        
        // Check if we should retry
        if (attempts < maxAttempts && stepConfig.retry) {
          const delay = this.calculateRetryDelay(stepConfig.retry, attempts);
          console.log(`Retrying step ${stepConfig.name} in ${delay}ms`);
          await this.sleep(delay);
        }
      }
    }
    
    // All attempts failed
    const stepResult: StepResult = {
      step_name: stepConfig.name,
      status: stepConfig.continue_on_error ? 'skipped' : 'failure',
      error: lastError?.message || 'Unknown error',
      duration_ms: Date.now() - startTime,
      attempts
    };
    
    this.state.step_results[stepConfig.name] = stepResult;
    
    if (!stepConfig.continue_on_error) {
      throw new NonRetryableError(`Step ${stepConfig.name} failed after ${attempts} attempts: ${lastError?.message}`);
    }
    
    console.log(`Step ${stepConfig.name} failed but marked as continue_on_error`);
    return stepResult;
  }
  
  /**
   * Build HTTP request configuration from step config and templates
   */
  private buildRequestConfig(stepConfig: StepConfig): any {
    const url = `${this.config.api_base}${stepConfig.endpoint}`;
    const method = stepConfig.method || 'POST';
    
    // Build headers
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...stepConfig.headers
    };
    
    // Add authentication headers
    if (this.config.auth) {
      this.addAuthHeaders(headers, this.config.auth);
    }
    
    // Build payload from template or direct payload
    let body: string | undefined;
    if (stepConfig.payload_template) {
      const renderedPayload = this.renderTemplate(stepConfig.payload_template, {
        variables: this.state.global_variables,
        steps: this.state.step_results
      });
      body = renderedPayload;
    } else if (stepConfig.payload) {
      body = JSON.stringify(stepConfig.payload);
    }
    
    return {
      url,
      method,
      headers,
      body,
      timeout: this.parseTimeoutMs(stepConfig.timeout || '30s')
    };
  }
  
  /**
   * Add authentication headers based on auth configuration
   */
  private addAuthHeaders(headers: Record<string, string>, auth: AuthConfig): void {
    switch (auth.type) {
      case 'bearer':
        if (auth.token) {
          headers['Authorization'] = `Bearer ${auth.token}`;
        }
        break;
      
      case 'api_key':
        if (auth.api_key) {
          const headerName = auth.header_name || 'X-API-Key';
          headers[headerName] = auth.api_key;
        }
        break;
      
      case 'basic':
        if (auth.username && auth.password) {
          const credentials = btoa(`${auth.username}:${auth.password}`);
          headers['Authorization'] = `Basic ${credentials}`;
        }
        break;
      
      case 'custom':
        if (auth.custom_headers) {
          Object.assign(headers, auth.custom_headers);
        }
        break;
    }
  }
  
  /**
   * Execute HTTP request with timeout
   */
  private async executeHttpRequest(config: any): Promise<Response> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), config.timeout);
    
    try {
      const response = await fetch(config.url, {
        method: config.method,
        headers: config.headers,
        body: config.body,
        signal: controller.signal
      });
      
      clearTimeout(timeoutId);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      return response;
    } catch (error) {
      clearTimeout(timeoutId);
      throw error;
    }
  }
  
  /**
   * Process step response and apply transformations
   */
  private async processStepResponse(stepConfig: StepConfig, response: Response): Promise<any> {
    let result = await response.json();
    
    // Apply response transformation if configured
    if (stepConfig.response_transform) {
      const transformedResult = this.renderTemplate(stepConfig.response_transform, {
        response: result,
        variables: this.state.global_variables,
        steps: this.state.step_results
      });
      
      try {
        result = JSON.parse(transformedResult);
      } catch {
        result = transformedResult; // Keep as string if not valid JSON
      }
    }
    
    // Store result in global variables if output_key specified
    if (stepConfig.output_key) {
      this.state.global_variables[stepConfig.output_key] = result;
    }
    
    return result;
  }
  
  /**
   * Simple template rendering (Jinja2-style variable substitution)
   */
  private renderTemplate(template: string, context: any): string {
    let rendered = template;
    
    // Replace {{ variable }} patterns
    rendered = rendered.replace(/\{\{\s*([^}]+)\s*\}\}/g, (match, path) => {
      const value = this.getNestedValue(context, path.trim());
      return value !== undefined ? JSON.stringify(value) : match;
    });
    
    return rendered;
  }
  
  /**
   * Get nested value from object using dot notation
   */
  private getNestedValue(obj: any, path: string): any {
    return path.split('.').reduce((current, key) => {
      return current && current[key] !== undefined ? current[key] : undefined;
    }, obj);
  }
  
  /**
   * Calculate retry delay with backoff strategy
   */
  private calculateRetryDelay(retry: RetryConfig, attempt: number): number {
    const baseDelay = this.parseTimeoutMs(retry.delay);
    
    switch (retry.backoff) {
      case 'constant':
        return baseDelay;
      
      case 'linear':
        return baseDelay * attempt;
      
      case 'exponential':
        return baseDelay * Math.pow(2, attempt - 1);
      
      default:
        return baseDelay;
    }
  }
  
  /**
   * Parse timeout string to milliseconds
   */
  private parseTimeoutMs(timeout: string): number {
    const match = timeout.match(/^(\d+)([smh])$/);
    if (!match) return 30000; // Default 30 seconds
    
    const [, value, unit] = match;
    const num = parseInt(value, 10);
    
    switch (unit) {
      case 's': return num * 1000;
      case 'm': return num * 60 * 1000;
      case 'h': return num * 60 * 60 * 1000;
      default: return 30000;
    }
  }
  
  /**
   * Sleep for specified milliseconds
   */
  private async sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
  
  /**
   * Validate workflow configuration
   */
  private validateConfig(config: WorkflowConfig): void {
    if (!config.name) {
      throw new Error('Workflow name is required');
    }
    
    if (!config.api_base) {
      throw new Error('API base URL is required');
    }
    
    if (!config.steps || config.steps.length === 0) {
      throw new Error('At least one workflow step is required');
    }
    
    // Validate step names are unique
    const stepNames = new Set<string>();
    for (const step of config.steps) {
      if (stepNames.has(step.name)) {
        throw new Error(`Duplicate step name: ${step.name}`);
      }
      stepNames.add(step.name);
    }
    
    // Validate dependencies exist
    for (const step of config.steps) {
      if (step.depends_on) {
        for (const dep of step.depends_on) {
          if (!stepNames.has(dep)) {
            throw new Error(`Step ${step.name} depends on non-existent step: ${dep}`);
          }
        }
      }
    }
  }
  
  /**
   * Finalize workflow and return summary
   */
  private async finalizeWorkflow(): Promise<any> {
    const endTime = Date.now();
    const duration = endTime - this.state.start_time;
    
    const summary = {
      workflow_name: this.config.name,
      total_duration_ms: duration,
      total_steps: Object.keys(this.state.step_results).length,
      successful_steps: Object.values(this.state.step_results).filter(r => r.status === 'success').length,
      failed_steps: Object.values(this.state.step_results).filter(r => r.status === 'failure').length,
      skipped_steps: Object.values(this.state.step_results).filter(r => r.status === 'skipped').length,
      step_results: this.state.step_results,
      final_variables: this.state.global_variables
    };
    
    console.log(`Workflow ${this.config.name} completed:`, summary);
    return summary;
  }
  
  /**
   * Send completion notification via webhook
   */
  private async sendCompletionNotification(result: any): Promise<void> {
    if (!this.config.monitoring?.webhook_url) {
      return;
    }
    
    const notification = {
      workflow_name: this.config.name,
      status: result.failed_steps > 0 ? 'failed' : 'completed',
      timestamp: new Date().toISOString(),
      summary: result
    };
    
    try {
      await fetch(this.config.monitoring.webhook_url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(notification)
      });
      
      console.log('Completion notification sent');
    } catch (error) {
      console.error('Failed to send completion notification:', error);
    }
  }
}