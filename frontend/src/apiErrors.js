function formatLocation(loc) {
  if (!Array.isArray(loc)) return "";
  return loc.filter((part) => part !== "body").join(".");
}

function formatValidationError(item) {
  if (!item || typeof item !== "object") return String(item || "");
  const location = formatLocation(item.loc);
  const message = item.msg || item.message || JSON.stringify(item);
  return location ? `${location}: ${message}` : message;
}

export function formatApiError(payload, fallback = "请求失败") {
  if (!payload) return fallback;
  if (typeof payload === "string") return payload;

  const detail = payload.detail ?? payload.message ?? payload.error;
  if (Array.isArray(detail)) {
    return detail.map(formatValidationError).filter(Boolean).join("；") || fallback;
  }
  if (detail && typeof detail === "object") {
    return formatValidationError(detail);
  }
  if (typeof detail === "string") {
    return detail;
  }
  if (typeof payload === "object") {
    return JSON.stringify(payload);
  }
  return String(payload);
}
