export function updatePayloadState(setState: any, setForm: any, payload: any) {
    setState({
        loading: false,
        error: "",
        payload: payload,
    });
    setForm(payload.employee);
}

export function buildEmployeeUpdatePayload(form: any) {
    const payload = Object.assign({}, form);
    delete payload.chat_id;
    return payload;
}

export function normalizeTimePart(value: any) {
    const match = String(value || "").match(/(\d{1,2}):(\d{2})/);
    if (!match) {
        return "";
    }
    const hours = Number(match[1]);
    const minutes = Number(match[2]);
    if (hours > 23 || minutes > 59) {
        return "";
    }
    return String(hours).padStart(2, "0") + ":" + String(minutes).padStart(2, "0");
}

export function parseWorkHours(value: any) {
    const normalizedValue = String(value || "");
    const rangeMatch = normalizedValue.match(/^\s*(\d{1,2}:\d{2})?\s*[-–—]\s*(\d{1,2}:\d{2})?\s*$/);
    if (rangeMatch) {
        return {
            start: normalizeTimePart(rangeMatch[1]),
            end: normalizeTimePart(rangeMatch[2]),
        };
    }
    const parts = normalizedValue.match(/\d{1,2}:\d{2}/g) || [];
    return {
        start: normalizeTimePart(parts[0]),
        end: normalizeTimePart(parts[1]),
    };
}

export function buildWorkHoursValue(currentValue: any, part: "start" | "end", nextValue: any) {
    const parsed = parseWorkHours(currentValue);
    parsed[part] = normalizeTimePart(nextValue);
    if (parsed.start && parsed.end) {
        return parsed.start + "-" + parsed.end;
    }
    if (parsed.start || parsed.end) {
        return (parsed.start || "") + "-" + (parsed.end || "");
    }
    return "";
}
