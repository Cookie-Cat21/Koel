# WebSocket / STOMP guide

The cse.lk Next.js app opens a **STOMP** session (via SockJS / `@stomp/stompjs`) against:

```
https://www.cse.lk/api/ws
```

## Topics (subscribe)

| Destination | Typical payload |
|---|---|
| `/topic/aspi` | ASPI index tick |
| `/topic/snp` | S&P SL20 tick |
| `/topic/status` | Market status |
| `/topic/summary` | Market summary |
| `/topic/today-sharePrice` | Share price list slice |
| `/topic/top-gainers` | Top gainers |
| `/topic/top-looses` | Top losers (site spelling) |
| `/topic/most-active-trades` | Most active |
| `/topic/daytrade` | Day trade stream |

User-queue mirrors: `/user/topic/<same>`.

## Request destinations (send)

After connect, the UI sends empty/trigger frames to:

- `/app/request-aspi`
- `/app/request-snp`
- `/app/request-status`
- `/app/request-summary`
- `/app/request-today-sharePrice`
- `/app/request-top-gainers`
- `/app/request-top-looses`
- `/app/request-most-active-trades`
- `/app/request-daytrade`

## Notes

- Raw `curl` WebSocket upgrade may `301`; follow the same SockJS negotiate path the browser uses.
- For **alerting / polite bots**, prefer HTTP `POST /tradeSummary` on an interval.
- Use WS for live dashboards that already mirror the official site behavior.
- Re-verify topics by searching cse.lk JS chunks for `subscribe("/topic/`.

## Minimal JS sketch (illustrative)

```js
// Illustrative only — match current @stomp/stompjs + SockJS versions yourself.
import { Client } from "@stomp/stompjs";
import SockJS from "sockjs-client";

const client = new Client({
  webSocketFactory: () => new SockJS("https://www.cse.lk/api/ws"),
  onConnect: () => {
    client.subscribe("/topic/status", (msg) => console.log(JSON.parse(msg.body)));
    client.publish({ destination: "/app/request-status", body: "" });
  },
});
client.activate();
```
