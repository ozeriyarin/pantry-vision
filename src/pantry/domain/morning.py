"""Run-out since the previous morning message (FR-010, research R8)."""

from dataclasses import dataclass
from zoneinfo import ZoneInfo

from pantry.domain.models import Baseline, Location, inventory_id
from pantry.ports import Clock, Store


@dataclass(frozen=True)
class MorningPlan:
    run_out: list[tuple[str, Location]]  # (item key, location)
    next_baseline: Baseline


class MorningService:
    def __init__(self, store: Store, clock: Clock, tz: str):
        self._store, self._clock, self._tz = store, clock, ZoneInfo(tz)

    def plan(self) -> MorningPlan | None:
        """None when today's message was already sent. Save the baseline only after sending."""
        now = self._clock.now()
        today = now.astimezone(self._tz).date().isoformat()
        baseline = self._store.get_baseline()
        if baseline and baseline.last_sent_date == today:
            return None
        current = {inventory_id(e.location, e.key): e.count for e in self._store.get_inventory()}
        run_out = []
        if baseline:
            # Run-out: count > 0 in the stored baseline and count 0 or absent now.
            for ident, count in sorted(baseline.items.items()):
                if count > 0 and current.get(ident, 0) == 0:
                    location, _, key = ident.partition("__")
                    run_out.append((key, Location(location)))
        return MorningPlan(run_out, Baseline(now, current, today))

    def commit(self, plan: MorningPlan) -> None:
        self._store.save_baseline(plan.next_baseline)
