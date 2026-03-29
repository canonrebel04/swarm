# LLM Instructions for Swarm Project

## Positive Instructions (What TO DO)

### 1. Project Understanding
- Read the README.md and index_database_plan.md thoroughly
- Understand the multi-agent orchestration architecture
- Familiarize yourself with the supported runtimes and agent roles
- Review the existing code structure before making changes

### 2. Coding Standards
- Follow Python best practices and PEP 8 guidelines
- Use type hints consistently
- Write clear, descriptive docstrings
- Maintain consistent code style with existing codebase
- Use meaningful variable and function names

### 3. Implementation Approach
- Implement features incrementally
- Write tests for new functionality
- Document your code changes
- Follow the existing project structure
- Use the provided configuration system

### 4. User Experience
- Ensure the TUI is responsive and user-friendly
- Provide clear error messages
- Maintain consistent keyboard shortcuts
- Make the setup process intuitive
- Ensure the model selector is easy to use

### 5. Configuration Management
- Use config.yaml for all configuration
- Support environment variables for sensitive data
- Provide sensible defaults
- Validate configuration inputs
- Handle configuration errors gracefully

## Negative Instructions (What NOT TO DO)

### 1. Project Scope
- Don't add new agent roles without discussion
- Don't change the core architecture without approval
- Don't remove existing functionality
- Don't add dependencies without justification
- Don't change the supported runtime list arbitrarily

### 2. Coding Practices
- Don't write untested code
- Don't ignore type hints
- Don't use unclear variable names
- Don't write overly complex code
- Don't ignore error handling

### 3. User Interface
- Don't change existing keyboard shortcuts
- Don't make the TUI less responsive
- Don't remove existing features from the UI
- Don't make configuration more complicated
- Don't break existing workflows

### 4. Configuration
- Don't store sensitive data in config.yaml
- Don't remove existing configuration options
- Don't break backward compatibility
- Don't make configuration less secure
- Don't ignore environment variables

### 5. Project Structure
- Don't reorganize files without reason
- Don't remove existing documentation
- Don't break existing imports
- Don't ignore the existing code style
- Don't remove existing tests

## Specific Implementation Guidelines

### For the Setup CLI:
- Make it work headless (SSH-friendly)
- Support all listed providers
- Write to .env file securely
- Validate API keys when possible
- Provide clear feedback

### For the Model Selector:
- Keep it keyboard-navigable
- Support search/filter functionality
- Allow custom provider entries
- Write changes to config.yaml
- Provide immediate feedback

### For the TUI:
- Maintain the existing layout
- Keep the overseer chat focused
- Support the 'M' key binding
- Make agent status visible
- Keep the interface clean

### For Configuration:
- Use YAML format consistently
- Support nested configuration
- Provide validation
- Handle missing files gracefully
- Support environment overrides

## Decision Making

When in doubt about any implementation detail:
1. Check existing code patterns
2. Review the README and documentation
3. Consider user experience impact
4. Think about maintainability
5. Ask for clarification if needed

Remember: The goal is to create a robust, user-friendly multi-agent orchestration system that works across different providers and runtimes.