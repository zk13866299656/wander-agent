const threadId = "t" + Math.random().toString(36).slice(2);
const traceEl = document.getElementById("trace");
const cardsEl = document.getElementById("cards");

document.getElementById("send").onclick = async () => {
  const message = document.getElementById("msg").value;
  cardsEl.innerHTML = "";
  traceEl.textContent = "";
  const resp = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ thread_id: threadId, message }),
  });
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  let currentEvent = null;
  let finished = false;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split("\n");
    buf = lines.pop(); // 保留最后一个不完整行，跨 chunk 拼接
    for (const line of lines) {
      if (line.startsWith("event: ")) {
        currentEvent = line.slice(7).trim();
      } else if (line.startsWith("data: ")) {
        const data = line.slice(6).trim();
        if (currentEvent === "node" && !finished) {
          traceEl.textContent = "思考中 → " + data;
        } else if (currentEvent === "cards") {
          finished = true;
          renderCards(JSON.parse(data));
        }
      }
    }
  }
};

function renderCards(cards) {
  cardsEl.innerHTML = cards.map((c) => `
    <div class="card">
      <div class="name">${c.name} ${"★".repeat(Math.round((c.rating || 0))) || ""}</div>
      <div class="meta">评分 ${c.rating ?? "—"} · 人均 ¥${c.avg_price ?? "—"} · ${c.distance_m ?? "—"}m · 综合 ${c.score.toFixed(2)}</div>
    </div>`).join("");
}
