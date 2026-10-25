const form = document.querySelector<HTMLFormElement>("#run-form");
const source = document.querySelector<HTMLTextAreaElement>("#source");
const output = document.querySelector<HTMLElement>("#output");
const runButton = document.querySelector<HTMLButtonElement>("#run");

type RunResult = { stdout: string; stderr: string; durationMs: number };

form?.addEventListener("submit", async (event: SubmitEvent) => {
  event.preventDefault();
  if (!source || !output || !runButton) return;
  runButton.disabled = true;
  output.textContent = "Running in a fresh sandbox…";
  try {
    const response = await fetch("/api/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: source.value }),
    });
    const result = await response.json() as RunResult | { error: string };
    if (!response.ok) throw new Error("error" in result ? result.error : "Run failed");
    const value = result as RunResult;
    output.textContent = `${value.stdout}${value.stderr ? `\n[stderr]\n${value.stderr}` : ""}\n\nFinished in ${value.durationMs} ms.`;
  } catch (error) {
    output.textContent = error instanceof Error ? error.message : "Run failed";
  } finally {
    runButton.disabled = false;
  }
});
