# Sequence

## Introduction

A sequence is a json file that contains a sequence of operations called "Steps" which operate in order with the ability to multi-thread, provide conditional logic and operate on variables to perform various functions. The sequence is specifically designed to center around the "Action" and "Request" step types which are designed to send pyqmh messages to modules in the application. See [steps.md] for more information on step types and parameters.

## Sequence Structure

The following is the high level sequence structure

```json
{
    "metadata": 
    {
        "sequence id": <sequence id>,
        "description": <description>,
        "version": <version>,
        "author": <author>
    },
    "variables":
    {
        <variable>: null,
        <variable>: <value>,
        ...
    },
    "sequence":
    [
        <step json>,
        <step json>,
        ...
    ]
}
```

## metadata

The metadata of the sequence file to help version and describe the intent of the sequence. The above metadata is present in all sequences but any sequence can have any number of extra fields of metadata which can be used by other programs to help filter through files and perform searching.

## variables

Variables are a list of key value pairs that hold some data. Variables can be accessed by steps using the syntax ${VariableID}. All fields within sequence steps should be able to access variables.

## sequence

The sequence is the ordered list of steps that need to be executed by the test executive.
