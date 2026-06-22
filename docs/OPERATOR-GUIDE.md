# Fulfillment Studio — Operator Guide

A desktop app for engraving Flanacom's Amazon jewelry orders. It pulls orders
(and their engraving files) straight from Flanacom's system, opens each design in
**LightBurn**, and reports the processing status back automatically.

---

## First-time setup (once per computer)

1. **Copy the app folder.** Put the `Fulfillment Studio` folder anywhere (e.g. the
   Desktop). Start the app by double-clicking **`Fulfillment Studio.exe`**.

2. **Add the access key.** The first launch creates a settings folder at
   `C:\Users\<you>\.flanacom-tool\`. Inside it you'll find `config.example.json`.
   - Make a copy named **`config.json`** in the same folder.
   - Open it and paste the secret key Flanacom gave you into `"api_key"`:
     ```json
     {
       "api_base_url": "https://puscgcazmnqxazietgvy.supabase.co/functions/v1/engraving-api",
       "api_key": "PASTE-THE-KEY-FROM-FLANACOM-HERE"
     }
     ```
   - Save and restart the app.

   > The key is secret — don't share it or paste it into emails/chat. It stays only
   > in this file on your machine.

3. **Make sure LightBurn is installed** (the standard `C:\Program Files\LightBurn`).
   The app launches it for you when you engrave.

If the key is missing or wrong, the app shows an orange banner at the top — fix
`config.json` and press **Refresh**.

---

## Daily workflow

1. **Dashboard.** Open orders are grouped by product type (bracelets, necklaces,
   keychains, flasks, …), oldest first. Use **Search** for an order number or the
   **To do / Shipped** filters. Press **Refresh** to pull the latest orders.

2. **Open an order.** Click a row. You'll see the product reference photo, the
   order details, the gift-box note, and the engraving tasks.

3. **Engrave each side.** Click **Engrave …** for a coin's Front/Back — the design
   downloads and opens in LightBurn. Position and run the job in LightBurn as
   usual, then come back. The side gets a ✓ and progress moves toward "all done".
   You can re-open a finished side any time.

4. **Ship.** When every side is engraved, **Mark as shipped** (confirm the gift
   box if the order needs one). This reports the order to Flanacom as
   **engraved & shipped**.

5. **A problem?** If a design is wrong or you have a question, use
   **Flag for revision** — Flanacom sees the order needs review.

The shipping label is on the order screen: **Open** to view, **Print** to print.

---

## What the statuses mean

| In the app | Meaning |
|---|---|
| **Open** | Not engraved yet |
| **Needs review** | You flagged it for revision / a question |
| **Engraved & shipped** | Done — reported back to Flanacom |

These three are the only statuses; they're written straight back to Flanacom's
system.

---

## Troubleshooting

- **Orange banner / no orders** → the access key is missing or wrong. Check
  `C:\Users\<you>\.flanacom-tool\config.json`, then press **Refresh**.
- **A design didn't open in LightBurn** → make sure LightBurn is installed; try the
  Engrave button again (it re-downloads a fresh copy each time).
- **An order looks out of date** → press **Refresh** (file links expire after an
  hour and are refreshed automatically when you engrave).
- **The list is empty but you expect orders** → you may be on the **Shipped**
  filter; switch back to **All** or **To do**.

---

*Questions or changes: contact your developer. Status is the only thing the app
writes back; it never edits order contents.*
