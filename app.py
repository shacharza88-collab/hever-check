import json, os, datetime
from flask import Flask, request, jsonify, render_template_string
from hever_lite import search

app = Flask(__name__)

# Load bundled JSON — no network request needed
_json_path = os.path.join(os.path.dirname(__file__), "mcccard.json")
with open(_json_path, encoding="utf-8") as f:
    _stores = json.load(f)

_last_updated = datetime.datetime.fromtimestamp(
    os.path.getmtime(_json_path)
).strftime("%d/%m/%Y")
print(f"Loaded {len(_stores)} stores, updated {_last_updated}.")

HTML = """
<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>בדיקת חבר</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: Arial, sans-serif; background: #f0f4f0; min-height: 100vh;
           display: flex; flex-direction: column; align-items: center; padding: 24px 16px; }
    h1 { color: #2d7a2d; margin-bottom: 8px; font-size: 1.6rem; }
    p.sub { color: #666; margin-bottom: 24px; font-size: 0.9rem; }
    .card { background: white; border-radius: 16px; padding: 24px;
            width: 100%; max-width: 480px; box-shadow: 0 2px 12px rgba(0,0,0,0.1); }
    .search-row { display: flex; gap: 8px; margin-bottom: 16px; }
    input { flex: 1; padding: 12px 16px; border: 2px solid #ddd; border-radius: 10px;
            font-size: 1rem; outline: none; }
    input:focus { border-color: #2d7a2d; }
    button { padding: 12px 20px; background: #2d7a2d; color: white; border: none;
             border-radius: 10px; font-size: 1rem; cursor: pointer; white-space: nowrap; }
    button:active { background: #1e5a1e; }
    #result { margin-top: 8px; }
    .badge { display: inline-block; padding: 4px 12px; border-radius: 20px;
             font-weight: bold; font-size: 0.85rem; margin-bottom: 12px; }
    .yes { background: #d4edda; color: #155724; }
    .no  { background: #f8d7da; color: #721c24; }
    .store-name { font-size: 1.2rem; font-weight: bold; margin-bottom: 4px; }
    .row { display: flex; justify-content: space-between; padding: 6px 0;
           border-bottom: 1px solid #f0f0f0; font-size: 0.9rem; }
    .row:last-child { border-bottom: none; }
    .label { color: #888; }
    .terms { background: #f9f9f9; border-radius: 8px; padding: 10px;
             font-size: 0.85rem; line-height: 1.6; margin-top: 8px; }
    .fuzzy { font-size: 0.9rem; color: #555; }
    .fuzzy li { padding: 4px 0; }
    .note { font-size: 0.78rem; color: #aaa; margin-top: 12px; text-align: center; }
    .spinner { display: none; text-align: center; color: #888; }
  </style>
</head>
<body>
  <h1>🟢 בדיקת חבר</h1>
  <p class="sub">חפש חנות לדעת אם מקבלת כרטיס חבר שלי</p>
  <p class="sub" style="font-size:0.75rem; color:#aaa">עודכן לאחרונה: {{ last_updated }}</p>
  <div class="card">
    <div class="search-row">
      <input id="q" type="text" placeholder="שם חנות..." autofocus
             onkeydown="if(event.key==='Enter') check()">
      <button onclick="check()">בדוק</button>
    </div>
    <div class="spinner" id="spinner">מחפש...</div>
    <div id="result"></div>
  </div>

  <script>
    async function check() {
      const q = document.getElementById('q').value.trim();
      if (!q) return;
      document.getElementById('spinner').style.display = 'block';
      document.getElementById('result').innerHTML = '';
      const res = await fetch('/check?q=' + encodeURIComponent(q));
      const data = await res.json();
      document.getElementById('spinner').style.display = 'none';
      document.getElementById('result').innerHTML = render(data);
    }

    function render(d) {
      if (d.found) {
        const s = d.store;
        const terms = s.limitations
          ? `<div class="terms">${s.limitations.replace(/\\n/g,'<br>')}</div>` : '';
        return `
          <div><span class="badge yes">✓ יש הטבה</span></div>
          <div class="store-name">${s.company}</div>
          <div class="row"><span class="label">קטגוריה</span><span>${s.category}</span></div>
          ${s.branches ? `<div class="row"><span class="label">סניפים</span><span>${s.branches}</span></div>` : ''}
          ${s.website ? `<div class="row"><span class="label">אתר</span><span>${s.website}</span></div>` : ''}
          <div class="row"><span class="label">אונליין</span><span>${s.online ? '✓ כן' : '✗ לא'}</span></div>
          ${s.online && s.online_limitations ? `<div class="row"><span class="label">תנאי אונליין</span><span style="font-size:0.85rem">${s.online_limitations}</span></div>` : ''}
          ${terms ? `<div style="margin-top:8px"><div class="label" style="margin-bottom:4px">תנאים</div>${terms}</div>` : ''}
          <p class="note">חבר שלי בלבד · לבדיקת הנחות כרטיס אשראי השתמש ב-hever_check.py</p>`;
      } else if (d.fuzzy && d.fuzzy.length) {
        return `
          <div><span class="badge no">✗ לא נמצא</span></div>
          <p class="fuzzy" style="margin-bottom:8px">אולי התכוונת ל:</p>
          <ul class="fuzzy">
            ${d.fuzzy.map(f => `<li>${f.company} <span style="color:#aaa">(${f.pct}%)</span></li>`).join('')}
          </ul>`;
      } else {
        return `<div><span class="badge no">✗ לא נמצא בתוכנית חבר שלי</span></div>`;
      }
    }
  </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML, last_updated=_last_updated)

@app.route("/debug")
def debug():
    return jsonify({"status": "ok", "store_count": len(_stores), "sample": _stores[0].get("company") if _stores else None})

@app.route("/check")
def check():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"found": False, "fuzzy": []})

    exact, fuzzy = search(q, _stores)

    if exact:
        s = exact[0]
        return jsonify({
            "found": True,
            "store": {
                "company": s.get("company", "").strip(),
                "category": s.get("company_category", "").strip(),
                "website": s.get("website", ""),
                "branches": s.get("branch_qty", ""),
                "online": s.get("is_online") == "Y",
                "online_limitations": s.get("online_limitations", "").replace("<br/>", "\n").strip(),
                "limitations": s.get("limitations", "").replace("<br/>", "\n"),
            }
        })

    return jsonify({
        "found": False,
        "fuzzy": [
            {"company": m.get("company", "").strip(), "pct": int(m["score"] * 100)}
            for m in fuzzy[:5]
        ]
    })

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
