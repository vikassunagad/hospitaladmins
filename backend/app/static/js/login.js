const form = document.getElementById("loginForm");
const pw = document.getElementById("password");
document.getElementById("showPw").onclick = (e) => {
  e.preventDefault();
  const show = pw.type === "password";
  pw.type = show ? "text" : "password";
  e.target.textContent = show ? "HIDE" : "SHOW";
};
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = document.getElementById("loginBtn"), err = document.getElementById("loginErr");
  err.hidden = true; btn.disabled = true; btn.textContent = "Signing in...";
  try {
    const r = await fetch("/api/auth/login", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: document.getElementById("username").value.trim(), password: pw.value }) });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Login failed.");
    location.href = "/dashboard";
  } catch (ex) {
    err.textContent = ex.message === "Failed to fetch" ? "Cannot reach the server." : ex.message;
    err.hidden = false; btn.disabled = false; btn.textContent = "LOGIN";
  }
});
