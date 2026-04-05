import { useState, useEffect } from "react";

export function useTypingCycle(
  messages: readonly string[],
  opts?: { typeMs?: number; deleteMs?: number; holdMs?: number }
) {
  const typeMs = opts?.typeMs ?? 38;
  const deleteMs = opts?.deleteMs ?? 22;
  const holdMs = opts?.holdMs ?? 2600;

  const [line, setLine] = useState("");
  const [i, setI] = useState(0);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    const target = messages[i] ?? "";
    let id: ReturnType<typeof setTimeout>;

    if (!deleting) {
      if (line.length < target.length) {
        id = setTimeout(() => {
          setLine(target.slice(0, line.length + 1));
        }, typeMs);
      } else {
        id = setTimeout(() => setDeleting(true), holdMs);
      }
    } else if (line.length > 0) {
      id = setTimeout(() => setLine((l) => l.slice(0, -1)), deleteMs);
    } else {
      setDeleting(false);
      setI((x) => (x + 1) % messages.length);
    }

    return () => clearTimeout(id);
  }, [line, deleting, i, messages, typeMs, deleteMs, holdMs]);

  return line;
}
