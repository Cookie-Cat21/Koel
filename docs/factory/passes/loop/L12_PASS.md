# Factory Loop Pass L12

**Verdict:** CLEAN_L12  
**Date:** 2026-07-11  

Market-hours unsent uses `_retry_unsent_with_lock` after unlocked `_deliver_pending`. No new >minor outside ACCEPT-DEFER.
