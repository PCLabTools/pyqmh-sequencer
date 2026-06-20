(function () {
    const STEP_TEMPLATES = {
        Set: { Variable: "", Value: null },
        Expression: { Expression: "" },
        Goto: { Step: "" },
        Action: { "Module ID": "", Action: "", Arguments: {} },
        Request: { "Module ID": "", Action: "", Arguments: {}, Return: {}, Timeout: 1000, OnTimeout: [] },
        For: { Iterations: 1, Index: "", SubSequence: [] },
        "For Each": { Array: [], Element: "item", Index: "", SubSequence: [] },
        While: { Condition: "", SubSequence: [] },
        "Do While": { Condition: "", SubSequence: [] },
        Break: {},
        If: { Condition: "", OnTrue: [], OnFalse: [] },
        Call: { Sequence: "", Threaded: false, Arguments: {} },
        Report: { Entry: "" },
        "Report Result": { Test: "", Result: "" },
        Wait: { Time: 1 },
        Label: {},
        Prompt: { Title: "", Message: "", PromptType: "CONFIRM", Return: "" },
        CLI: { Command: "", Return: "" },
    };

    const STEP_TYPES = Object.keys(STEP_TEMPLATES);
    const STEP_TYPE_HELP = {
        Set: "Assigns a value to a variable.",
        Expression: "Evaluates an expression, often using variable substitutions.",
        Goto: "Jumps execution to another step by ID or index.",
        Action: "Sends a non-blocking action message to a module.",
        Request: "Sends a request message and optionally handles timeout behavior.",
        For: "Runs a SubSequence for a fixed number of iterations.",
        "For Each": "Runs a SubSequence for each element in an array.",
        While: "Repeats a SubSequence while a condition remains active.",
        "Do While": "Runs a SubSequence first, then repeats based on condition.",
        Break: "Breaks out of the current loop or nested SubSequence.",
        If: "Branches flow into OnTrue or OnFalse SubSequences.",
        Call: "Calls another sequence inline or on a separate thread.",
        Report: "Adds a timestamped entry to the sequence report.",
        "Report Result": "Records a named test result in the report.",
        Wait: "Pauses execution for a specified time.",
        Label: "Marks a location in flow, often used as a Goto target.",
        Prompt: "Prompts the user for confirmation or input.",
        CLI: "Runs a terminal command and optionally stores its output.",
    };
    const LAYOUT = {
        verticalGap: 120,
        branchGap: 280,
        nodeWidth: 190,
        nodeHeight: 92,
        startY: 130,
    };
    const NODE_DESCRIPTION_FONT = '10px "IBM Plex Mono", Consolas, monospace';
    const NODE_DESCRIPTION_MAX_LINES = 3;
    const NODE_TEXT_WIDTH = LAYOUT.nodeWidth - 24;
    const NODE_BASE_HEIGHT = 56;
    const NODE_DESC_LINE_HEIGHT = 12;

    const state = {
        sequence: createEmptySequence(),
        selectedStepRef: null,
        currentPath: "",
        currentDirectory: "",
        dirty: false,
        fileList: [],
        transform: d3.zoomIdentity,
        graphData: { nodes: [], edges: [] },
        dropPreview: null,
    };

    let svg;
    let world;
    let dropLayer;
    let tooltipTimer = null;
    let tooltipPending = null;
    let tooltipAnchor = null;

    function createEmptySequence() {
        return {
            metadata: {
                "sequence id": "untitled_sequence",
                description: "Created in pyqmh sequence editor",
                version: "1.0.0",
                author: "pyqmh-sequencer",
            },
            variables: {},
            sequence: [
                {
                    ID: "start",
                    Description: "Start label",
                    Type: "Label",
                },
            ],
        };
    }

    function deepClone(value) {
        return JSON.parse(JSON.stringify(value));
    }

    function sanitizeStepId(raw) {
        return String(raw || "step")
            .trim()
            .toLowerCase()
            .replace(/[^a-z0-9_]+/g, "_")
            .replace(/^_+|_+$/g, "") || "step";
    }

    function createStep(type) {
        const safeType = STEP_TYPES.includes(type) ? type : "Label";
        const sequence = state.sequence.sequence;
        const baseId = sanitizeStepId(safeType);
        let suffix = sequence.length + 1;
        let id = `${baseId}_${suffix}`;
        const existing = new Set(sequence.map((step) => step.ID));
        while (existing.has(id)) {
            suffix += 1;
            id = `${baseId}_${suffix}`;
        }

        return {
            ID: id,
            Description: `${safeType} step`,
            Type: safeType,
            ...deepClone(STEP_TEMPLATES[safeType]),
        };
    }

    function moduleBasePath() {
        const shell = document.querySelector(".editor-shell");
        return shell ? shell.dataset.moduleBase || "" : "";
    }

    async function apiRequest(action, argumentsPayload) {
        const base = moduleBasePath();
        const response = await fetch(`${base}/api/request`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                action,
                arguments: argumentsPayload || {},
                timeout_ms: 5000,
            }),
        });

        const body = await response.json();
        if (!response.ok || !body.ok) {
            throw new Error(body.error || `Request failed (${response.status})`);
        }

        const payload = body.response || {};
        if (payload.ok === false) {
            throw new Error(payload.error || "Operation failed");
        }
        return payload;
    }

    function setStatus(text, isError) {
        const el = document.getElementById("status-text");
        if (!el) {
            return;
        }
        el.textContent = text;
        el.style.color = isError ? "var(--danger)" : "var(--text-muted)";
    }

    function setDirty(isDirty) {
        state.dirty = Boolean(isDirty);
        const title = state.currentPath || "Untitled";
        document.title = `${state.dirty ? "* " : ""}${title} - pyqmh Sequence Editor`;
    }

    function getStepTypeHelp(type) {
        return STEP_TYPE_HELP[type] || "No description available for this step type.";
    }

    function getTextMeasureContext() {
        if (!getTextMeasureContext._canvas) {
            getTextMeasureContext._canvas = document.createElement("canvas");
            getTextMeasureContext._ctx = getTextMeasureContext._canvas.getContext("2d");
        }
        return getTextMeasureContext._ctx;
    }

    function measureTextPx(text, font) {
        const ctx = getTextMeasureContext();
        if (!ctx) {
            return String(text || "").length * 8;
        }
        ctx.font = font;
        return ctx.measureText(String(text || "")).width;
    }

    function fitTextWithEllipsis(text, maxWidthPx, font) {
        const raw = String(text || "");
        if (measureTextPx(raw, font) <= maxWidthPx) {
            return raw;
        }
        const suffix = "...";
        let out = raw;
        while (out.length > 0 && measureTextPx(`${out}${suffix}`, font) > maxWidthPx) {
            out = out.slice(0, -1);
        }
        return `${out}${suffix}`;
    }

    function splitTokenByWidth(token, maxWidthPx, font) {
        const parts = [];
        let remaining = String(token || "");
        while (remaining.length > 0) {
            let low = 1;
            let high = remaining.length;
            let best = 1;
            while (low <= high) {
                const mid = Math.floor((low + high) / 2);
                const candidate = remaining.slice(0, mid);
                if (measureTextPx(candidate, font) <= maxWidthPx) {
                    best = mid;
                    low = mid + 1;
                } else {
                    high = mid - 1;
                }
            }
            parts.push(remaining.slice(0, best));
            remaining = remaining.slice(best);
        }
        return parts;
    }

    function wrapDescription(value, maxWidthPx = NODE_TEXT_WIDTH, maxLines = NODE_DESCRIPTION_MAX_LINES, font = NODE_DESCRIPTION_FONT) {
        const text = String(value || "").trim();
        if (!text) {
            return { lines: [], truncated: false };
        }

        const tokens = text.split(/\s+/).filter(Boolean);
        const lines = [];
        let current = "";
        let truncated = false;

        function pushCurrent() {
            if (!current) {
                return;
            }
            lines.push(current);
            current = "";
        }

        for (let i = 0; i < tokens.length; i += 1) {
            const token = tokens[i];
            const tokenParts = measureTextPx(token, font) > maxWidthPx ? splitTokenByWidth(token, maxWidthPx, font) : [token];

            for (let j = 0; j < tokenParts.length; j += 1) {
                const part = tokenParts[j];
                const candidate = current ? `${current} ${part}` : part;
                if (measureTextPx(candidate, font) <= maxWidthPx) {
                    current = candidate;
                    continue;
                }

                pushCurrent();
                if (lines.length >= maxLines) {
                    truncated = true;
                    break;
                }
                current = part;
            }

            if (truncated) {
                break;
            }
        }

        if (current) {
            if (lines.length < maxLines) {
                lines.push(current);
            } else {
                truncated = true;
            }
        }

        if (lines.length > maxLines) {
            lines.length = maxLines;
            truncated = true;
        }

        if (truncated && lines.length) {
            lines[lines.length - 1] = fitTextWithEllipsis(lines[lines.length - 1], maxWidthPx, font);
        }

        return { lines, truncated };
    }

    function trimSvgTspanToWidth(tspanNode, maxWidthPx, withEllipsis) {
        if (!tspanNode) {
            return;
        }

        const original = String(tspanNode.textContent || "");
        if (!original) {
            return;
        }

        const suffix = withEllipsis ? "..." : "";
        let content = original;
        let rendered = withEllipsis ? `${content}${suffix}` : content;
        tspanNode.textContent = rendered;

        while (content.length > 0 && tspanNode.getComputedTextLength() > maxWidthPx) {
            content = content.slice(0, -1);
            rendered = withEllipsis ? `${content}${suffix}` : content;
            tspanNode.textContent = rendered;
        }
    }

    function getTooltipElement() {
        return document.getElementById("step-tooltip");
    }

    function positionTooltip(clientX, clientY) {
        const tooltip = getTooltipElement();
        if (!tooltip) {
            return;
        }

        const margin = 16;
        const gap = 14;
        const rect = tooltip.getBoundingClientRect();
        let x = clientX + gap;
        let y = clientY + gap;

        if (x + rect.width + margin > window.innerWidth) {
            x = clientX - rect.width - gap;
        }
        if (y + rect.height + margin > window.innerHeight) {
            y = clientY - rect.height - gap;
        }

        x = Math.max(margin, x);
        y = Math.max(margin, y);

        tooltip.style.left = `${x}px`;
        tooltip.style.top = `${y}px`;
    }

    function showTooltipNow() {
        const tooltip = getTooltipElement();
        if (!tooltip || !tooltipPending) {
            return;
        }

        const title = tooltip.querySelector(".step-tooltip-title");
        const body = tooltip.querySelector(".step-tooltip-body");
        if (!title || !body) {
            return;
        }

        title.textContent = tooltipPending.type;
        body.textContent = getStepTypeHelp(tooltipPending.type);
        positionTooltip(tooltipPending.x, tooltipPending.y);
        tooltip.classList.add("visible");
        tooltip.setAttribute("aria-hidden", "false");
    }

    function scheduleTooltip(type, event) {
        hideTooltip();
        tooltipPending = { type, x: event.clientX, y: event.clientY };
        tooltipAnchor = type;
        tooltipTimer = window.setTimeout(() => {
            tooltipTimer = null;
            showTooltipNow();
        }, 420);
    }

    function moveTooltip(type, event) {
        if (tooltipAnchor !== type) {
            return;
        }

        if (tooltipPending) {
            tooltipPending.x = event.clientX;
            tooltipPending.y = event.clientY;
        }

        const tooltip = getTooltipElement();
        if (tooltip && tooltip.classList.contains("visible")) {
            positionTooltip(event.clientX, event.clientY);
        }
    }

    function hideTooltip() {
        if (tooltipTimer !== null) {
            window.clearTimeout(tooltipTimer);
            tooltipTimer = null;
        }

        tooltipPending = null;
        tooltipAnchor = null;

        const tooltip = getTooltipElement();
        if (!tooltip) {
            return;
        }

        tooltip.classList.remove("visible");
        tooltip.setAttribute("aria-hidden", "true");
    }

    function parseRefSegments(ref) {
        const segments = [];
        const parts = String(ref || "").split(".");
        for (const part of parts) {
            const match = /^([^\[]+)\[(\d+)\]$/.exec(part);
            if (!match) {
                return null;
            }
            segments.push({ key: match[1], index: Number(match[2]) });
        }
        return segments;
    }

    function getStepByRef(ref) {
        const segments = parseRefSegments(ref);
        if (!segments || !segments.length) {
            return null;
        }

        let context = state.sequence;
        for (const segment of segments) {
            if (!context || !Array.isArray(context[segment.key])) {
                return null;
            }
            context = context[segment.key][segment.index];
        }

        if (!context || typeof context !== "object") {
            return null;
        }
        return context;
    }

    function getParentArrayFromRef(ref) {
        const segments = parseRefSegments(ref);
        if (!segments || !segments.length) {
            return null;
        }

        let context = state.sequence;
        for (let i = 0; i < segments.length - 1; i += 1) {
            const segment = segments[i];
            if (!context || !Array.isArray(context[segment.key])) {
                return null;
            }
            context = context[segment.key][segment.index];
        }

        const last = segments[segments.length - 1];
        if (!context || !Array.isArray(context[last.key])) {
            return null;
        }

        return { array: context[last.key], index: last.index };
    }

    function findRefForStep(stepToFind) {
        function walk(steps, arrayRefKey) {
            for (let i = 0; i < steps.length; i += 1) {
                const step = steps[i];
                const ref = `${arrayRefKey}[${i}]`;
                if (step === stepToFind) {
                    return ref;
                }

                const fields = getSubsequenceFields(step);
                for (const field of fields) {
                    const found = walk(field.steps, `${ref}.${field.key}`);
                    if (found) {
                        return found;
                    }
                }
            }
            return null;
        }

        return walk(state.sequence.sequence, "sequence");
    }

    function refIsDescendantOf(ref, possibleAncestorRef) {
        const needle = `${possibleAncestorRef}.`;
        return String(ref || "").startsWith(needle);
    }

    function buildDropOptions(targetNode) {
        const options = [];
        const baseY = targetNode.y + targetNode.height / 2 + 40;
        options.push({
            id: "main",
            kind: "main",
            label: "main",
            x: targetNode.x,
            y: baseY,
        });

        const branches = getSubsequenceFields(targetNode.step);
        if (!branches.length) {
            return options;
        }

        const spacing = 170;
        const preferredSide = {
            OnFalse: -1,
            OnTrue: 1,
            OnTimeout: 1,
            SubSequence: 0,
        };
        const usedSlots = new Set();

        function reserveSlot(preferred) {
            if (typeof preferred === "number" && !usedSlots.has(preferred)) {
                usedSlots.add(preferred);
                return preferred;
            }

            if (preferred === 0) {
                let depth = 1;
                while (usedSlots.has(depth) && usedSlots.has(-depth)) {
                    depth += 1;
                }
                const slot = !usedSlots.has(depth) ? depth : -depth;
                usedSlots.add(slot);
                return slot;
            }

            if (preferred === 1 || preferred === -1) {
                let depth = 1;
                let slot = preferred;
                while (usedSlots.has(slot)) {
                    depth += 1;
                    slot = preferred * depth;
                }
                usedSlots.add(slot);
                return slot;
            }

            let depth = 1;
            while (usedSlots.has(depth) && usedSlots.has(-depth)) {
                depth += 1;
            }
            const slot = !usedSlots.has(depth) ? depth : -depth;
            usedSlots.add(slot);
            return slot;
        }

        branches.forEach((branch, idx) => {
            const preferred = Object.prototype.hasOwnProperty.call(preferredSide, branch.key)
                ? preferredSide[branch.key]
                : null;
            const offset = reserveSlot(preferred);
            options.push({
                id: `branch:${branch.key}`,
                kind: "branch",
                branchKey: branch.key,
                label: branch.key,
                x: targetNode.x + offset * spacing,
                y: baseY,
            });
        });

        return options;
    }

    function chooseActiveDropOption(options, worldPoint) {
        let best = null;
        let bestDist = Number.POSITIVE_INFINITY;
        options.forEach((option) => {
            const dx = option.x - worldPoint.x;
            const dy = option.y - worldPoint.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist < bestDist) {
                bestDist = dist;
                best = option;
            }
        });
        return best;
    }

    function clearDropPreview() {
        state.dropPreview = null;
        if (dropLayer) {
            dropLayer.selectAll("*").remove();
        }
    }

    function renderDropPreview() {
        if (!dropLayer) {
            return;
        }

        dropLayer.selectAll("*").remove();
        if (!state.dropPreview) {
            return;
        }

        const preview = state.dropPreview;
        const targetHalo = dropLayer.append("g").attr("class", "drop-target-halo");
        targetHalo
            .append("rect")
            .attr("x", preview.targetNode.x - LAYOUT.nodeWidth / 2 - 6)
            .attr("y", preview.targetNode.y - preview.targetNode.height / 2 - 6)
            .attr("width", LAYOUT.nodeWidth + 12)
            .attr("height", preview.targetNode.height + 12)
            .attr("rx", 14);

        const optionSel = dropLayer.selectAll("g.drop-option").data(preview.options, (opt) => opt.id);
        const optionEnter = optionSel.enter().append("g").attr("class", "drop-option");
        optionEnter.append("circle").attr("r", 16);
        optionEnter.append("text").attr("class", "drop-option-label").attr("dy", 4);

        optionSel
            .merge(optionEnter)
            .classed("active", (opt) => preview.activeOption && opt.id === preview.activeOption.id)
            .attr("transform", (opt) => `translate(${opt.x},${opt.y})`)
            .select("text.drop-option-label")
            .text((opt) => opt.label);

        optionSel.exit().remove();
    }

    function updateDropPreview(worldPoint, draggedRef) {
        const exclusionRef = String(draggedRef || "");
        const candidates = state.graphData.nodes.filter((node) => {
            if (!exclusionRef) {
                return true;
            }
            if (node.ref === exclusionRef) {
                return false;
            }
            return !refIsDescendantOf(node.ref, exclusionRef);
        });

        if (!candidates.length) {
            clearDropPreview();
            return;
        }

        let targetNode = null;
        let minDist = Number.POSITIVE_INFINITY;
        candidates.forEach((node) => {
            const dx = node.x - worldPoint.x;
            const dy = node.y - worldPoint.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist < minDist) {
                minDist = dist;
                targetNode = node;
            }
        });

        if (!targetNode || minDist > 360) {
            clearDropPreview();
            return;
        }

        const options = buildDropOptions(targetNode);
        const activeOption = chooseActiveDropOption(options, worldPoint);
        const targetParent = getParentArrayFromRef(targetNode.ref);
        state.dropPreview = {
            targetNode,
            targetRef: targetNode.ref,
            targetStep: targetNode.step,
            targetArray: targetParent ? targetParent.array : null,
            targetIndex: targetParent ? targetParent.index : -1,
            options,
            activeOption,
        };
        renderDropPreview();
    }

    function insertStepAtPreview(step, preview) {
        if (!preview || !preview.activeOption) {
            return false;
        }

        const option = preview.activeOption;
        if (option.kind === "main") {
            if (!preview.targetArray || preview.targetIndex < 0) {
                return false;
            }
            preview.targetArray.splice(preview.targetIndex + 1, 0, step);
            return true;
        }

        if (option.kind === "branch") {
            if (!preview.targetStep) {
                return false;
            }
            if (!Array.isArray(preview.targetStep[option.branchKey])) {
                preview.targetStep[option.branchKey] = [];
            }
            preview.targetStep[option.branchKey].push(step);
            return true;
        }

        return false;
    }

    function moveStepByPreview(draggedRef, preview) {
        const source = getParentArrayFromRef(draggedRef);
        if (!source || source.index < 0 || source.index >= source.array.length) {
            return false;
        }
        if (!preview || !preview.activeOption) {
            return false;
        }
        if (preview.targetRef === draggedRef || refIsDescendantOf(preview.targetRef, draggedRef)) {
            return false;
        }

        const movedStep = source.array[source.index];
        const option = preview.activeOption;

        if (option.kind === "main") {
            if (!preview.targetArray || preview.targetIndex < 0) {
                return false;
            }
            source.array.splice(source.index, 1);

            let insertIndex = preview.targetIndex + 1;
            if (source.array === preview.targetArray && source.index < preview.targetIndex) {
                insertIndex -= 1;
            }
            preview.targetArray.splice(insertIndex, 0, movedStep);
        } else if (option.kind === "branch") {
            source.array.splice(source.index, 1);
            if (!preview.targetStep) {
                return false;
            }
            if (!Array.isArray(preview.targetStep[option.branchKey])) {
                preview.targetStep[option.branchKey] = [];
            }
            preview.targetStep[option.branchKey].push(movedStep);
        } else {
            return false;
        }

        state.selectedStepRef = findRefForStep(movedStep);
        return true;
    }

    function isStepArray(value) {
        return Array.isArray(value) && value.every((item) => item && typeof item === "object" && typeof item.Type === "string");
    }

    function getSubsequenceFields(step) {
        if (!step || typeof step !== "object") {
            return [];
        }

        const fields = [];
        Object.keys(step).forEach((key) => {
            if (key === "_ui") {
                return;
            }
            if (isStepArray(step[key])) {
                fields.push({ key, steps: step[key] });
            }
        });

        return fields;
    }

    async function refreshFileList() {
        try {
            const payload = await apiRequest("list_sequences", {});
            state.fileList = Array.isArray(payload.files) ? payload.files : [];
            if (typeof payload.current_directory === "string") {
                state.currentDirectory = payload.current_directory;
                const dirIndicator = document.getElementById("sequence-dir-indicator");
                if (dirIndicator) {
                    dirIndicator.textContent = `Folder: ${state.currentDirectory}`;
                    dirIndicator.title = state.currentDirectory;
                }
            }
            const select = document.getElementById("file-select");
            select.innerHTML = "";

            if (!state.fileList.length) {
                const option = document.createElement("option");
                option.value = "";
                option.textContent = "No sequence files found";
                select.appendChild(option);
                setStatus("No sequence files found.", false);
                return;
            }

            state.fileList.forEach((path) => {
                const option = document.createElement("option");
                option.value = path;
                option.textContent = path;
                select.appendChild(option);
            });

            if (state.currentPath && state.fileList.includes(state.currentPath)) {
                select.value = state.currentPath;
            }
            setStatus(`Loaded ${state.fileList.length} file path(s).`, false);
        } catch (error) {
            setStatus(error.message, true);
        }
    }

    async function browseSequenceDirectory() {
        try {
            const payload = await apiRequest("browse_sequence_directory", {});
            if (payload.cancelled) {
                setStatus("Folder selection cancelled.", false);
                return;
            }
            if (typeof payload.directory === "string") {
                state.currentDirectory = payload.directory;
                const dirIndicator = document.getElementById("sequence-dir-indicator");
                if (dirIndicator) {
                    dirIndicator.textContent = `Folder: ${state.currentDirectory}`;
                    dirIndicator.title = state.currentDirectory;
                }
            }
            await refreshFileList();
            setStatus(`Sequence folder set to ${state.currentDirectory}.`, false);
        } catch (error) {
            setStatus(error.message, true);
        }
    }

    async function loadSelectedSequence() {
        const select = document.getElementById("file-select");
        const path = select.value;
        if (!path) {
            setStatus("Select a file to load.", true);
            return;
        }

        try {
            const payload = await apiRequest("load_sequence", { path });
            state.sequence = payload.sequence;
            state.currentPath = payload.path;
            state.selectedStepRef = null;
            renderAll();
            setDirty(false);
            document.getElementById("save-path").value = state.currentPath;
            setStatus(`Loaded ${state.currentPath}.`, false);
        } catch (error) {
            setStatus(error.message, true);
        }
    }

    async function saveSequence(path, overwrite) {
        const finalPath = String(path || "").trim();
        if (!finalPath) {
            setStatus("Provide a path before saving.", true);
            return;
        }

        try {
            const payload = await apiRequest("save_sequence", {
                path: finalPath,
                sequence: state.sequence,
                overwrite: Boolean(overwrite),
            });
            state.currentPath = payload.path;
            document.getElementById("save-path").value = state.currentPath;
            await refreshFileList();
            setDirty(false);
            setStatus(`Saved ${state.currentPath}.`, false);
        } catch (error) {
            if (String(error.message).toLowerCase().includes("already exists") && !overwrite) {
                const doOverwrite = window.confirm("File exists. Overwrite it?");
                if (doOverwrite) {
                    await saveSequence(finalPath, true);
                }
                return;
            }
            setStatus(error.message, true);
        }
    }

    function buildGraphData() {
        const rect = svg.node().getBoundingClientRect();
        const centerX = Math.max(220, rect.width / 2);
        const nodes = [];
        const edges = [];
        const loopTypes = new Set(["For", "For Each", "While", "Do While"]);

        function layoutSequence(steps, arrayRefKey, x, startY) {
            let y = startY;
            let firstRef = null;
            let incomingRefs = [];
            let maxYUsed = startY;

            for (let index = 0; index < steps.length; index += 1) {
                const step = steps[index];
                const ref = `${arrayRefKey}[${index}]`;
                const descriptionWrap = wrapDescription(step.Description || "", NODE_TEXT_WIDTH, NODE_DESCRIPTION_MAX_LINES, NODE_DESCRIPTION_FONT);
                const descriptionLines = descriptionWrap.lines;
                const descriptionLineCount = Math.max(1, descriptionLines.length);
                const node = {
                    ref,
                    step,
                    x,
                    y,
                    descriptionLines,
                    descriptionTruncated: descriptionWrap.truncated,
                    height: NODE_BASE_HEIGHT + descriptionLineCount * NODE_DESC_LINE_HEIGHT,
                };
                nodes.push(node);

                if (!firstRef) {
                    firstRef = ref;
                }

                if (incomingRefs.length) {
                    incomingRefs.forEach((incomingRef) => {
                        edges.push({ sourceRef: incomingRef, targetRef: ref, label: "", kind: "flow" });
                    });
                }

                let outgoingRefs = [ref];
                let branchBottomY = y;
                const branchFields = getSubsequenceFields(step);
                const isLoopNode = loopTypes.has(step.Type);

                if (branchFields.length) {
                    const populatedBranches = branchFields.filter((branch) => branch.steps.length > 0);
                    if (populatedBranches.length) {
                        const branchStartY = y + LAYOUT.verticalGap;
                        const branchRefs = [];
                        const preferredSide = {
                            OnFalse: -1,
                            OnTrue: 1,
                            OnTimeout: 1,
                            SubSequence: 0,
                        };
                        const usedSlots = new Set();

                        function reserveSlot(preferred) {
                            if (typeof preferred === "number" && !usedSlots.has(preferred)) {
                                usedSlots.add(preferred);
                                return preferred;
                            }

                            if (preferred === 0) {
                                let depth = 1;
                                while (usedSlots.has(depth) && usedSlots.has(-depth)) {
                                    depth += 1;
                                }
                                const slot = !usedSlots.has(depth) ? depth : -depth;
                                usedSlots.add(slot);
                                return slot;
                            }

                            if (preferred === 1 || preferred === -1) {
                                let depth = 1;
                                let slot = preferred;
                                while (usedSlots.has(slot)) {
                                    depth += 1;
                                    slot = preferred * depth;
                                }
                                usedSlots.add(slot);
                                return slot;
                            }

                            let depth = 1;
                            while (usedSlots.has(depth) && usedSlots.has(-depth)) {
                                depth += 1;
                            }
                            const slot = !usedSlots.has(depth) ? depth : -depth;
                            usedSlots.add(slot);
                            return slot;
                        }

                        populatedBranches.forEach((branch, branchIndex) => {
                            const preferred = Object.prototype.hasOwnProperty.call(preferredSide, branch.key)
                                ? preferredSide[branch.key]
                                : null;
                            const offset = reserveSlot(preferred);
                            const branchX = x + offset * LAYOUT.branchGap;
                            const branchLayout = layoutSequence(branch.steps, `${ref}.${branch.key}`, branchX, branchStartY);

                            if (branchLayout.firstRef) {
                                edges.push({ sourceRef: ref, targetRef: branchLayout.firstRef, label: branch.key, kind: "branch" });
                                branchRefs.push(...branchLayout.lastRefs);
                            }
                            branchBottomY = Math.max(branchBottomY, branchLayout.maxY);
                        });

                        if (branchRefs.length) {
                            if (isLoopNode) {
                                branchRefs.forEach((branchRef) => {
                                    edges.push({ sourceRef: branchRef, targetRef: ref, label: "loop", kind: "loopback" });
                                });
                                outgoingRefs = [ref];
                            } else {
                                // For timeout handling, preserve the straight-through request success path
                                // and merge timeout branch endpoints back into downstream flow.
                                if (step.Type === "Request" && populatedBranches.some((branch) => branch.key === "OnTimeout")) {
                                    outgoingRefs = [ref, ...branchRefs];
                                } else {
                                    outgoingRefs = branchRefs;
                                }
                            }
                            y = branchBottomY + LAYOUT.verticalGap;
                        } else {
                            y += LAYOUT.verticalGap;
                        }
                    } else {
                        y += LAYOUT.verticalGap;
                    }
                } else {
                    y += LAYOUT.verticalGap;
                }

                incomingRefs = outgoingRefs;
                maxYUsed = Math.max(maxYUsed, y, branchBottomY);
            }

            return {
                firstRef,
                lastRefs: incomingRefs,
                maxY: maxYUsed,
            };
        }

        layoutSequence(state.sequence.sequence, "sequence", centerX, LAYOUT.startY);
        return { nodes, edges };
    }

    function renderCanvas() {
        state.graphData = buildGraphData();
        const nodesByRef = new Map(state.graphData.nodes.map((node) => [node.ref, node]));

        const linkSel = world
            .selectAll("g.edge")
            .data(state.graphData.edges, (edge) => `${edge.sourceRef}->${edge.targetRef}:${edge.label}`);
        const linkEnter = linkSel.enter().append("g").attr("class", "edge");
        linkEnter.append("path").attr("class", "link");
        linkEnter.append("text").attr("class", "edge-label");

        linkSel
            .merge(linkEnter)
            .each(function (edge) {
                const sourceNode = nodesByRef.get(edge.sourceRef);
                const targetNode = nodesByRef.get(edge.targetRef);
                if (!sourceNode || !targetNode) {
                    return;
                }

                const x1 = sourceNode.x;
                const y1 = sourceNode.y + sourceNode.height / 2;
                const x2 = targetNode.x;
                const y2 = targetNode.y - targetNode.height / 2;
                let path;
                if (edge.kind === "loopback") {
                    const rightX = Math.max(x1, x2) + LAYOUT.branchGap * 0.75;
                    path = `M ${x1},${y1} C ${rightX},${y1} ${rightX},${y2} ${x2},${y2}`;
                } else {
                    const cy = y1 + (y2 - y1) * 0.5;
                    path = `M ${x1},${y1} C ${x1},${cy} ${x2},${cy} ${x2},${y2}`;
                }

                const group = d3.select(this);
                group
                    .select("path.link")
                    .attr("d", path)
                    .classed("branch", edge.kind === "branch")
                    .classed("loopback", edge.kind === "loopback");

                group
                    .select("text.edge-label")
                    .text(edge.label || "")
                    .attr("x", edge.kind === "loopback" ? Math.max(x1, x2) + LAYOUT.branchGap * 0.55 : x1 + (x2 - x1) * 0.5)
                    .attr("y", y1 + (y2 - y1) * 0.38)
                    .style("display", edge.label ? null : "none");
            });
        linkSel.exit().remove();

        const nodeSel = world.selectAll("g.node").data(state.graphData.nodes, (node) => node.ref);
        const nodeEnter = nodeSel.enter().append("g").attr("class", "node");
        nodeEnter
            .append("rect")
            .attr("width", LAYOUT.nodeWidth)
            .attr("x", -LAYOUT.nodeWidth / 2);
        nodeEnter
            .append("text")
            .attr("x", -LAYOUT.nodeWidth / 2 + 12)
            .attr("class", "node-id");
        nodeEnter
            .append("text")
            .attr("x", -LAYOUT.nodeWidth / 2 + 12)
            .attr("class", "node-type");
        nodeEnter
            .append("text")
            .attr("x", -LAYOUT.nodeWidth / 2 + 12)
            .attr("class", "node-description");

        const dragBehavior = d3
            .drag()
            .on("start", function () {
                hideTooltip();
                d3.select(this).classed("dragging", true);
            })
            .on("drag", function (event, node) {
                d3.select(this).attr("transform", `translate(${event.x},${event.y})`);
                updateDropPreview({ x: event.x, y: event.y }, node.ref);
            })
            .on("end", function (_, node) {
                d3.select(this).classed("dragging", false);
                const moved = moveStepByPreview(node.ref, state.dropPreview);
                clearDropPreview();
                if (moved) {
                    setDirty(true);
                }
                renderAll();
            });

        nodeSel
            .merge(nodeEnter)
            .classed("selected", (node) => node.ref === state.selectedStepRef)
            .attr("transform", (node) => `translate(${node.x},${node.y})`)
            .on("click", (event, node) => {
                event.stopPropagation();
                state.selectedStepRef = node.ref;
                renderAll();
            })
            .on("mouseenter", (event, node) => {
                scheduleTooltip(node.step.Type || "Step", event);
            })
            .on("mousemove", (event, node) => {
                moveTooltip(node.step.Type || "Step", event);
            })
            .on("mouseleave", () => {
                hideTooltip();
            })
            .call(dragBehavior);

        nodeSel
            .merge(nodeEnter)
            .select("text.node-id")
            .text((node) => node.step.ID)
            .attr("y", (node) => -node.height / 2 + 17)
            .attr("font-weight", 700);

        nodeSel
            .merge(nodeEnter)
            .select("rect")
            .attr("height", (node) => node.height)
            .attr("y", (node) => -node.height / 2);

        nodeSel
            .merge(nodeEnter)
            .select("text.node-type")
            .text((node) => node.step.Type || "Step")
            .attr("y", (node) => -node.height / 2 + 35);

        nodeSel
            .merge(nodeEnter)
            .select("text.node-description")
            .each(function (node) {
                const selection = d3.select(this);
                selection.attr("y", -node.height / 2 + 53);
                const lines = node.descriptionLines || [];
                selection.selectAll("tspan").remove();

                lines.forEach((line, idx) => {
                    selection
                        .append("tspan")
                        .attr("x", -LAYOUT.nodeWidth / 2 + 12)
                        .attr("dy", idx === 0 ? 0 : 12)
                        .text(line);
                });

                const tspans = selection.selectAll("tspan").nodes();
                tspans.forEach((tspanNode, idx) => {
                    const isLast = idx === tspans.length - 1;
                    const overflowed = tspanNode.getComputedTextLength() > NODE_TEXT_WIDTH;
                    const needsEllipsis = isLast && (node.descriptionTruncated || overflowed);
                    trimSvgTspanToWidth(tspanNode, NODE_TEXT_WIDTH, needsEllipsis);
                });
            });

        nodeSel.exit().remove();
        renderDropPreview();
    }

    function buildField(parent, key, value, onChange) {
        const wrapper = document.createElement("div");
        wrapper.className = "field-row";

        const label = document.createElement("label");
        label.textContent = key;
        wrapper.appendChild(label);

        const isStructured = typeof value === "object" && value !== null;
        const input = isStructured ? document.createElement("textarea") : document.createElement("input");
        input.value = isStructured ? JSON.stringify(value, null, 2) : String(value ?? "");

        input.addEventListener("change", function () {
            let nextValue = input.value;
            if (isStructured) {
                try {
                    nextValue = JSON.parse(input.value);
                } catch (_) {
                    setStatus(`Invalid JSON for ${key}.`, true);
                    return;
                }
            }
            onChange(nextValue);
            setDirty(true);
            renderAll();
        });

        input.addEventListener("dragover", function (event) {
            if (event.dataTransfer && event.dataTransfer.types.includes("text/x-variable-name")) {
                event.preventDefault();
            }
        });

        input.addEventListener("drop", function (event) {
            const variableName = event.dataTransfer.getData("text/x-variable-name");
            if (!variableName) {
                return;
            }
            event.preventDefault();
            const token = `\${${variableName}}`;
            const start = input.selectionStart || input.value.length;
            const end = input.selectionEnd || input.value.length;
            const current = String(input.value || "");
            input.value = `${current.slice(0, start)}${token}${current.slice(end)}`;
            input.dispatchEvent(new Event("change", { bubbles: true }));
        });

        wrapper.appendChild(input);
        parent.appendChild(wrapper);
    }

    function renderStepForm() {
        const form = document.getElementById("step-form");
        const selectedLabel = document.getElementById("selected-step-label");
        const panelRight = document.querySelector(".panel-right");
        form.innerHTML = "";

        const stepRef = state.selectedStepRef;
        const step = getStepByRef(stepRef);
        if (!stepRef || !step) {
            if (panelRight) {
                panelRight.hidden = true;
            }
            selectedLabel.textContent = "No step selected";
            return;
        }

        if (panelRight) {
            panelRight.hidden = false;
        }

        selectedLabel.textContent = `Editing ${step.ID} (${stepRef})`;

        buildField(form, "ID", step.ID, (nextValue) => {
            step.ID = sanitizeStepId(nextValue);
        });
        buildField(form, "Description", step.Description || "", (nextValue) => {
            step.Description = String(nextValue);
        });

        const typeWrap = document.createElement("div");
        typeWrap.className = "field-row";
        const typeLabel = document.createElement("label");
        typeLabel.textContent = "Type";
        typeWrap.appendChild(typeLabel);

        const typeSelect = document.createElement("select");
        STEP_TYPES.forEach((typeName) => {
            const option = document.createElement("option");
            option.value = typeName;
            option.textContent = typeName;
            if (step.Type === typeName) {
                option.selected = true;
            }
            typeSelect.appendChild(option);
        });

        typeSelect.addEventListener("change", function () {
            const nextType = typeSelect.value;
            step.Type = nextType;
            const base = { ID: step.ID, Description: step.Description, Type: nextType };
            Object.assign(step, base, deepClone(STEP_TEMPLATES[nextType] || {}));
            setDirty(true);
            renderAll();
        });

        typeWrap.appendChild(typeSelect);
        form.appendChild(typeWrap);

        Object.keys(step)
            .filter((key) => !["ID", "Description", "Type"].includes(key))
            .filter((key) => !isStepArray(step[key]))
            .forEach((key) => {
                buildField(form, key, step[key], (nextValue) => {
                    step[key] = nextValue;
                });
            });

    }

    function renderVariables() {
        const list = document.getElementById("variable-list");
        list.innerHTML = "";

        const entries = Object.entries(state.sequence.variables || {});
        if (!entries.length) {
            const empty = document.createElement("p");
            empty.textContent = "No variables defined";
            list.appendChild(empty);
            return;
        }

        function parseVariableValue(raw) {
            const text = String(raw || "").trim();
            if (!text) {
                return "";
            }

            try {
                return JSON.parse(text);
            } catch (_) {
                return text;
            }
        }

        entries.forEach(([name, value]) => {
            const row = document.createElement("div");
            row.className = "variable-row";
            row.draggable = true;
            row.addEventListener("dragstart", function (event) {
                event.dataTransfer.setData("text/x-variable-name", name);
                event.dataTransfer.effectAllowed = "copy";
            });

            const nameEl = document.createElement("div");
            nameEl.className = "variable-name";
            nameEl.textContent = name;

            const valueInput = document.createElement("input");
            valueInput.className = "variable-value-input";
            valueInput.type = "text";
            valueInput.value = JSON.stringify(value);
            valueInput.addEventListener("change", function () {
                state.sequence.variables[name] = parseVariableValue(valueInput.value);
                valueInput.value = JSON.stringify(state.sequence.variables[name]);
                setDirty(true);
            });

            const removeBtn = document.createElement("button");
            removeBtn.type = "button";
            removeBtn.textContent = "x";
            removeBtn.addEventListener("click", function () {
                delete state.sequence.variables[name];
                setDirty(true);
                renderAll();
            });

            row.appendChild(nameEl);
            row.appendChild(valueInput);
            row.appendChild(removeBtn);
            list.appendChild(row);
        });
    }

    function renderToolPanel() {
        const toolList = document.getElementById("tool-list");
        toolList.innerHTML = "";
        STEP_TYPES.forEach((type) => {
            const chip = document.createElement("div");
            chip.className = "tool-chip";
            chip.textContent = type;
            chip.draggable = true;
            chip.addEventListener("mouseenter", function (event) {
                scheduleTooltip(type, event);
            });
            chip.addEventListener("mousemove", function (event) {
                moveTooltip(type, event);
            });
            chip.addEventListener("mouseleave", function () {
                hideTooltip();
            });
            chip.addEventListener("dragstart", function (event) {
                hideTooltip();
                event.dataTransfer.setData("text/x-step-type", type);
                event.dataTransfer.effectAllowed = "copy";
            });
            toolList.appendChild(chip);
        });
    }

    function nearestTopLevelIndex(pointX, pointY) {
        let nearestIndex = -1;
        let nearestDistance = Number.POSITIVE_INFINITY;
        state.graphData.nodes
            .filter((node) => /^sequence\[\d+\]$/.test(node.ref))
            .forEach((node) => {
                const match = /^sequence\[(\d+)\]$/.exec(node.ref);
                if (!match) {
                    return;
                }
                const index = Number(match[1]);
                const dx = node.x - pointX;
                const dy = node.y - pointY;
                const distance = Math.sqrt(dx * dx + dy * dy);
                if (distance < nearestDistance) {
                    nearestDistance = distance;
                    nearestIndex = index;
                }
            });
        return nearestIndex;
    }

    function setupCanvas() {
        svg = d3.select("#sequence-canvas");
        world = svg.append("g").attr("class", "world");
        dropLayer = world.append("g").attr("class", "drop-layer");

        const zoomBehavior = d3
            .zoom()
            .scaleExtent([0.25, 2.5])
            .on("zoom", (event) => {
                state.transform = event.transform;
                world.attr("transform", event.transform);
            });

        svg.call(zoomBehavior);

        const svgNode = svg.node();
        svgNode.addEventListener("click", (event) => {
            if (event.target !== svgNode) {
                return;
            }
            if (!state.selectedStepRef) {
                return;
            }
            state.selectedStepRef = null;
            renderAll();
        });

        svgNode.addEventListener("dragover", (event) => {
            if (event.dataTransfer && event.dataTransfer.types.includes("text/x-step-type")) {
                event.preventDefault();
                const pointer = d3.pointer(event, svgNode);
                const worldPoint = state.transform.invert(pointer);
                updateDropPreview({ x: worldPoint[0], y: worldPoint[1] }, null);
            }
        });

        svgNode.addEventListener("drop", (event) => {
            const stepType = event.dataTransfer.getData("text/x-step-type");
            if (!stepType) {
                return;
            }
            event.preventDefault();

            const step = createStep(stepType);

            let placed = insertStepAtPreview(step, state.dropPreview);
            if (!placed) {
                const pointer = d3.pointer(event, svgNode);
                const worldPoint = state.transform.invert(pointer);
                const insertionAnchor = nearestTopLevelIndex(worldPoint[0], worldPoint[1]);
                const insertAt = insertionAnchor >= 0 ? insertionAnchor + 1 : state.sequence.sequence.length;
                state.sequence.sequence.splice(insertAt, 0, step);
                placed = true;
            }

            if (placed) {
                state.selectedStepRef = findRefForStep(step);
            }

            clearDropPreview();
            setDirty(true);
            renderAll();
        });
    }

    function renderAll() {
        renderCanvas();
        renderStepForm();
        renderVariables();
    }

    function bindControls() {
        document.getElementById("btn-refresh").addEventListener("click", refreshFileList);
        document.getElementById("btn-load").addEventListener("click", loadSelectedSequence);
        document.getElementById("btn-browse-sequence-dir").addEventListener("click", function () {
            browseSequenceDirectory();
        });

        document.getElementById("btn-new").addEventListener("click", function () {
            state.sequence = createEmptySequence();
            state.selectedStepRef = null;
            state.currentPath = "";
            document.getElementById("save-path").value = "";
            renderAll();
            setDirty(false);
            setStatus("Created new sequence.", false);
        });

        document.getElementById("btn-save").addEventListener("click", function () {
            const savePath = state.currentPath || document.getElementById("save-path").value;
            saveSequence(savePath, true);
        });

        document.getElementById("btn-save-as").addEventListener("click", function () {
            const savePath = document.getElementById("save-path").value;
            saveSequence(savePath, false);
        });

        document.getElementById("btn-delete-step").addEventListener("click", function () {
            const parent = getParentArrayFromRef(state.selectedStepRef);
            if (!parent || parent.index < 0 || parent.index >= parent.array.length) {
                return;
            }
            parent.array.splice(parent.index, 1);
            state.selectedStepRef = null;
            setDirty(true);
            renderAll();
        });

        document.getElementById("btn-add-variable").addEventListener("click", function () {
            const input = document.getElementById("new-variable-name");
            const name = sanitizeStepId(input.value);
            if (!name) {
                return;
            }
            if (Object.prototype.hasOwnProperty.call(state.sequence.variables, name)) {
                setStatus("Variable already exists.", true);
                return;
            }
            state.sequence.variables[name] = null;
            input.value = "";
            setDirty(true);
            renderAll();
        });
    }

    async function bootstrap() {
        renderToolPanel();
        setupCanvas();
        bindControls();
        renderAll();
        await refreshFileList();
    }

    document.addEventListener("DOMContentLoaded", bootstrap);
})();
