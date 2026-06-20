# Examples

The "example sequences" folder contains example JSON sequence files that demonstrate all the available sequence step types. Each file is organized to focus on specific functionality, making it easy to understand how to use each step type.

## Examples Overview

### 01_basic_operations.json
**Demonstrates:** Set, Label, Report, Wait, and Expression (basic usage)

A simple sequence that shows fundamental operations:
- Using Set to initialize and modify variables
- Using Label for code organization
- Using Report to log test progress
- Using Wait for timing control
- Variable interpolation with `${variable_name}` syntax
- Expression computation with variable handling

### 02_conditional_logic.json
**Demonstrates:** If/Then/Else, While, Do While, and Break

Advanced control flow structures:
- Conditional branching with If statements and true/false SubSequences
- While loops that continue until a condition is met
- Do While loops that execute at least once
- Break statements to exit loops early
- Using expressions in conditions

### 03_loop_operations.json
**Demonstrates:** For, While, Iterator variables, and Break in loops

Iteration patterns:
- Basic For loops with fixed iteration counts
- For loops with Index variables that track the current iteration
- While loops with explicit counter and condition checks
- For Each loops with array consumption
- Accumulation of values across iterations
- Breaking out of loops based on conditions
- Complex loop control patterns

### 04_module_communication.json
**Demonstrates:** Action and Request step types

PyQMH message-driven communication:
- Sending Action messages to modules (fire-and-forget style)
- Sending Request messages and waiting for responses
- Passing Arguments to module actions
- Capturing return values in variables
- Timeout handling with OnTimeout SubSequences
- Conditional logic based on module responses

## Module API Expectations

Some examples assume common module command names for clarity. If your module APIs use different names, update the sequence steps accordingly.

- `power_supply` module:
	- Action `configure_output` with arguments: `voltage`, `current_limit`
	- Action `enable_output` with argument: `enabled`
- `power_meter` module:
	- Request `measure` with argument: `channel`
	- Expected response fields used by examples: `voltage`, `current`

These names are intentionally descriptive placeholders for demonstration. The sequence patterns remain the same even if your concrete action/request names differ.

### 05_user_interaction.json
**Demonstrates:** Prompt step type with all prompt types

User input collection:
- CONFIRM prompts for simple acknowledgment
- OK/CANCEL prompts for yes/no decisions
- STRING prompts for text input
- NUMBER prompts for numeric input
- Conditional logic based on user responses
- Input validation patterns

### 06_system_commands.json
**Demonstrates:** CLI step type for system command execution

Command-line integration:
- Executing system commands (dir, systeminfo, etc.)
- Running PowerShell commands
- Capturing command output in variables
- Conditional execution based on command results
- File system checks
- System information retrieval

### 07_sequence_calls.json
**Demonstrates:** Call step type for sequence composition

Sequence modularization:
- Calling other sequences inline (blocking execution)
- Calling sequences in new threads (non-blocking)
- Passing arguments to called sequences
- Sharing variables between parent and child sequences
- Waiting for threaded operations to complete

**Helper sequences:**
- `subscripts/helper_sequence.json`: Example of an inline-called sequence that processes inputs and modifies shared variables
- `subscripts/worker_sequence.json`: Example of a threaded sequence that performs independent work

### 08_comprehensive_test.json
**Demonstrates:** Multiple step types working together in a realistic scenario

A complete test sequence that combines:
- Initialization and status tracking
- User interaction and confirmation
- Module communication (Action and Request)
- Retry logic with While loops
- Measurement loops with For
- Conditional branching for decision-making
- Error handling and result reporting
- Cleanup and final reporting

This example shows how to build a realistic, production-like test sequence.

### 09_goto_control_flow.json
**Demonstrates:** Goto and Label for advanced control flow

Advanced flow control:
- Label definitions as jump targets
- Goto jumps to specific steps by ID
- Implementing retry loops using Goto
- Success and failure paths
- Error handling with conditional Goto
- Complex branching that's easier to manage with Labels

### test_suite.json
**demonstrates:** in-line calling of sequences

The complete test suite that calls all examples:
- Call in-line all examples in order

## Step Type Reference

### Control Flow Steps
- **Label**: Marks a location for Goto jumps
- **Goto**: Jumps to a labeled step
- **If**: Conditional execution with OnTrue and OnFalse branches
- **For**: Loop with fixed iteration count and optional Iterator variable
- **While**: Loop that continues while condition is true
- **Do While**: Loop that executes at least once, then continues while condition is true
- **Break**: Exits a loop or SubSequence

### Communication Steps
- **Action**: Sends a fire-and-forget message to a PyQMH module
- **Request**: Sends a message to a module and waits for a response
- **Call**: Calls another sequence file inline or in a new thread

### Data and System Steps
- **Set**: Sets or modifies a variable value
- **Expression**: Computes an expression modifying variable values
- **CLI**: Executes a system command and captures output
- **Prompt**: Displays a user prompt (CONFIRM, OK/CANCEL, STRING, or NUMBER)

### Reporting and Timing
- **Report**: Adds an entry to the sequence report with timestamp
- **Wait**: Pauses execution for specified seconds

## Variable Syntax

Variables are defined in the `variables` section and referenced using the syntax: `${variable_name}`

Examples:
- `${counter}` - retrieves the value of counter variable
- `${counter + 1}` - expressions are evaluated at runtime
- `${name == "John"}` - comparisons in conditions

## Usage Tips

1. **Start with simple examples**: Begin with `01_basic_operations.json` to understand the syntax
2. **Build incrementally**: Each example builds on concepts from previous ones
3. **Mix and match**: Combine techniques from different examples in your own sequences
4. **Use Labels and Goto**: For complex control flow, Labels and Goto can make logic clearer
5. **Modularize with Call**: For large sequences, use Call to split into smaller, reusable sequences
6. **Error handling**: Use If/Goto patterns to handle errors and implement retries
7. **Test reporting**: Use Report steps throughout to create comprehensive test logs

## JSON Structure Notes

- All JSON must be valid according to the sequence schema
- Variable names are case-sensitive
- Conditions are evaluated as Python expressions
- SubSequences are arrays of step objects
- Each step must have an ID, Description, and Type
