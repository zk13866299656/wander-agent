const threadId = "t" + Math.random().toString(36).slice(2);
const traceEl = document.getElementById("trace");
const cardsEl = document.getElementById("cards");
let currentCards = [];
let currentLnglat = null;

document.getElementById("locate").onclick = () => {
  const status = document.getElementById("loc-status");
  if (!navigator.geolocation) {
    status.textContent = "浏览器不支持定位";
    return;
  }
  status.textContent = "定位中…";
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      currentLnglat = [pos.coords.longitude, pos.coords.latitude];
      status.textContent =
        "已定位 (" +
        pos.coords.longitude.toFixed(4) + ", " +
        pos.coords.latitude.toFixed(4) + ")";
    },
    (err) => {
      currentLnglat = null;
      status.textContent = "定位失败：" + err.message;
    },
    { enableHighAccuracy: true, timeout: 10000 }
  );
};

document.getElementById("send").onclick = async () => {
  const message = document.getElementById("msg").value;
  cardsEl.innerHTML = "";
  traceEl.textContent = "";
  const resp = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ thread_id: threadId, message, lnglat: currentLnglat }),
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
  currentCards = cards;
  cardsEl.innerHTML = cards.map((c, i) => `
    <div class="card">
      <div class="name">${c.name} ${"★".repeat(Math.round((c.rating || 0))) || ""}</div>
      <div class="meta">评分 ${c.rating ?? "—"} · 人均 ¥${c.avg_price ?? "—"} · ${c.distance_m ?? "—"}m · 综合 ${c.score.toFixed(2)}</div>
      <button class="fav" data-fav="${i}">收藏</button>
    </div>`).join("");
}

cardsEl.addEventListener("click", async (e) => {
  const btn = e.target.closest("button.fav");
  if (!btn) return;
  const c = currentCards[Number(btn.dataset.fav)];
  if (!c) return;
  const poi = {
    id: c.id,
    name: c.name,
    source: c.source,
    rating: c.rating,
    avg_price: c.avg_price,
    distance_m: c.distance_m,
    tags: c.tags,
  };
  try {
    const resp = await fetch("/favorite", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ poi }),
    });
    if (resp.ok) {
      btn.textContent = "已收藏";
      btn.disabled = true;
    } else {
      btn.textContent = "收藏失败";
    }
  } catch {
    btn.textContent = "收藏失败";
  }
});
