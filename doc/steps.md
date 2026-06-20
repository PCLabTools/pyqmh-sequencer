# Steps

## Introduction

This file details the steps available to use in a test sequence. Steps are commands that perform actions. Steps are written in json format.

## Step Structure

```json
{
    "ID": <StepID>,
    "Description": <Description>,
    "Type": <Step Type>,
    "Parameter1": <Parameter>,
    "Parameter2": <Parameter>,
    "Parameter3": <Parameter>,
    ...
}
```

## Step Types

All commands have the following parameters:

- Step ID: String -> Unique ID of the step
- Description: String -> User defined description for the step

### Set

This command sets a variable value. The variable can be of any type, although typically json format is preferred.

**Parameters**

```md
Variable: VariableID -> ID of variable for which the value will be set
Value: Any -> Value the variable needs to be set to
```

### Expression

This command can compute expressions which may use variables and values to perform calculations and such.

**Parameters**

```md
Expression: String -> String containing expression to compute
```

**Example Expressions**

```md
${Variable_A} = ${Variable_B} * 2 + 32

${Variable_A}++

${Variable_A} = sqrt(${Variable_A})

${Variabel_A} = 12 ; ${Variable_B} = 14
```

### Goto

This command sends the sequence executive to the referenced step by id or step number.

**Parameters**

```md
Step: String (Step ID) or Number (Step Index) -> The unique Step ID or step index the sequencer should jump to
```

### Action

This command sends an "action" type of pyqmh message to a module specified.

**Parameters**

```md
Module ID: String -> ID of the module the message is sent to
Action: String -> The action to be called from the module
Arguments: JSON -> Argument names and values used in the action (optional)
```

### Request

This command sends a "request" type of pyqmh message to a module specified and returns the response which can be assigned to a variable.

**Parameters**

```md
Module ID: String -> ID of the module the message is sent to
Action: String -> The request to be called from the module
Arguments [optional]: JSON -> Argument names and values used in the request
Return: JSON -> Return value names and variable names in which to store return value
Timeout [optoinal]: Number -> Timeout in milliseconds for the module to respond (defaults to pyqmh default request timeout if not set)
OnTimeout [optional]: SubSequence -> A sub sequence of commands to be ran if timeout occurs
```

### For

This command runs a SubSequence a specified number of times.

**Parameters**

```md
Iterations: Number -> The number of iterations the for loop should run the SubSequence
Index [optional]: VariableID -> The variable in which to store the current iteration value as the for loop iterates
```

### For Each

This command runs a SubSequence for each element of an array type.

**Parameters**

```md
Array: Array -> The array to iterate over
Element: VariableID -> The variable in which to store the current iteration's array element for use within the SubSequence
Index [optional]: VariableID -> The variable in which to store the current iteration value as the for loop iterates
```

### While

This command runs a SubSequence repeatedly until a condition is met.

**Parameters**

```md
Condition: Expression -> Expression containing variables which computed true (or non-zero) result in the loop breaking out of the loop before running the SubSequence
Index [optional]: VariableID -> The variable in which to store the current iteration value as the for loop iterates
```

### Do While

This command runs a SubSequence repeatedly until a condition is met.

**Parameters**

```md
Condition: Expression -> Expression containing variables which computed true (or non-zero) after running the SubSequence result in the loop breaking
Index [optional]: VariableID -> The variable in which to store the current iteration value as the for loop iterates
```

### Break

This command can be used from a for, while, do while and SubSequence to break out of them.

### If

This command can be used to provide conditional logic to a sequence with a true/false branch.

**Parameters**

```md
Condition: Expression -> Expression containing variables which is computer as true (or non-zero) or false (0)
OnTrue: SubSequence -> Sequence of steps to take on true condition (may be empty)
OnFalse: SubSequence -> Sequence of steps to take on false condition (may be empty)
```

### Call

This command is capable of calling another sequence and can do so in-line (blocking) or as a new thread.  When calling sequences in-line or in new threads, all input argument variables share context with the parent variable assigned so that the parent has a mechanism to share data with the thread or read the result of an in-line sequence.

**Parameters**

```md
Sequence: Path -> Path to the sequence to execute
Threaded: Boolean -> Whether to call the sequence in-line or as a new thread
Arguments [optional]: JSON -> Variable assignments from parent, or scalar values, to be assigned to called sequence variables
```

### Report

This command instructs the sequencer to add and entry to the sequence report (a markdown report generated by the sequence when a sequence has completed execution).

**Parameters**

```md
Entry: String -> The entry to place in the report, which will be automatically time stamped and placed in the correct location. Information on the report can be found in the report.md file
```

### Report Result

This command instructs the sequencer to add and entry to the sequence report in the "Tests" section mapping a test name to a result.

**Parameters**

```md
Test: String -> The name of the test
Result: Any -> The assigned value of the test result
```

### Wait

This command instructs the sequencer to wait for the specified number of seconds in the current sequence thread.

**Parameters**

```md
Time: Number -> Seconds to wait
```

### Label

This command does not do anything, it is a way of commenting in a sequence. It can be used as a method to give an anchor point for a "Go To" command as Labels have a Step ID like all other commands.

### Prompt

This command tells the sequencer to present a prompt to the user for input or selection. Prompts are blocking in their current thread. The prompt types are:

- CONFIRM: This prompt simply has 1 button to confirm a message
- OK/CANCEL: This prompt provides 2 buttons "OK" and "Cancel" which return true or false
- STRING: This prompt presents the user with a string input box and an "OK" button
- NUMBER: This prompt presents the user with a number input box and an "OK" button

**Parameters**
```md
Title [optional]: String -> The prompt window title
Message [optional]: String -> The message to display in the prompt
PromptType: String -> The prompt type to display (types listed above)
Return: VariableID -> The variable in which to store the user input
```

### CLI

This command writes the user input to the OS command line (terminal) and returns the result.

**Parameters**

```md
Command: String -> The command to run in the terminal
Return: VariableID -> The variable in which to store the return from the command
```


## Parameter Types

Parameters can be simple values, json structures, conditional and mathematical expressions and variable assignments (through the ${} escape)

### String

Simple string or variable assignment

### Number

Numeric which can be an integer or floating point number or a variable assignment

### VariableID

String corresponding to the name of a variable in the sequence

### Any

This is a variant data type which can be of any type (even a structure like JSON)

### JSON

A json string typically used as a dictionary for assigning key value pairs

### Expression

String expression which is always computed at run-time

### SubSequence

A sequence of steps. This is a JSON structure that resembles a sequence that is called from a parent sequence.

### Path

Simple string or variable assignment that is used as a relative path for calling sequences

### Boolean

Simple boolean value or variable assignment

### Array

Array data types like lists
