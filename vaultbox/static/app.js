const script = document.currentScript;
const csrf = script?.dataset.csrf || "";
const plain = document.querySelector("#plain");
const encrypted = document.querySelector("#encrypted");
const status = document.querySelector("#status");

async function operation(path, source, target) {
  status.textContent = "Working…";
  try {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "text/plain;charset=utf-8", "X-CSRF-Token": csrf },
      body: source.value,
    });
    const text = await response.text();
    if (!response.ok) throw new Error(response.status === 422 ? "Invalid or unsupported content" : "Operation failed");
    target.value = text;
    status.textContent = "Done";
  } catch (error) {
    status.textContent = error.message;
  }
}

document.querySelector("#encrypt").onclick = () => operation("/api/v1/encrypt", plain, encrypted);
document.querySelector("#decrypt").onclick = () => operation("/api/v1/decrypt", encrypted, plain);
document.querySelector("#clear").onclick = () => { plain.value = ""; encrypted.value = ""; status.textContent = "Cleared"; };
document.querySelectorAll("[data-copy]").forEach((button) => {
  button.onclick = async () => { await navigator.clipboard.writeText(document.querySelector(`#${button.dataset.copy}`).value); status.textContent = "Copied"; };
});
