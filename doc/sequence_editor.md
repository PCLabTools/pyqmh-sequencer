# Sequence Editor

The sequence editor is a module for pyqmh that serves an editing environment for the user in which they can create, edit and manage sequence files using a drag-and-drop interface that builds sequence files in a flow chart manner.

## Layout

### Canvas

The main part of the webui interface is to serve a canvas which fills the entire workspace. All other elements will float on top of the canvas. The canvas will hold dropped test steps, linking them together into a sequence. The canvas is pannable and zoomable to allow the user to see what is important in a sequence as it may become complex and large.

### Tools

The tools panel should float in from the left and provide the suite of tools (step types) that the user can drag and drop onto the canvas which connects it to the nearest node.

### Parameters

The parameters panel should float in from the right when a step on the canvas is selected to provide an interface for the user to set the parameters of the step.

### Toolbar

The toolbar panel floats in from the top and provides the controls necessary to load sequence files and save them with the option to override or save as new

### Variables

The variables panel should also float in from the right, underneath the parameters panel and provide a list of variables the sequence contains. The panel needs to provide a button to add variables to the sequence. Variables should be able to be dragged and dropped onto parameter fields to auto-populate them with the variable name (properly escaped as per the pyqmh sequence spec).

## GUI Tools

Possible web tools that could help in creating this interface could be:

- d3.js